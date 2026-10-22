"""Design agent: Claude plans and calls the surrogate, BO and compliance tools, then writes a cited brief.

`run_agent` drives a manual tool-use loop on the Claude API so every step can be rendered live and the
client can be replaced in tests. `run_planner` is a fixed, rule-based sequence over the same tools for
when no API credentials are available; it is labeled as such wherever it is shown.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .anions import library_table, substitutes
from .anions import describe as describe_smiles
from .bo import best_observed, propose
from .campaigns import BUILDERS, Campaign, get_campaign
from .compliance import DefaultScreener, screen_records
from .data import GoldSet, load_gold
from .gaps import extraction_worklist

MODEL = "claude-opus-5-5"
SILICONE = "BYK-333 (polyether-modified PDMS)"

SYSTEM = """You are the design agent of Project Negative Lines, an open dataset of negative-tone photoresist \
formulations extracted from patents. You help a chemist choose the next formulations to test.

Work with the tools. Every number you report (predictions, intervals, best observed values, counts) must come \
from a tool result in this conversation; never estimate or recall values yourself. Cite tested examples as \
"<doc_id>, <location>".

Compliance results are a screening aid, not legal advice. "Unverified structure" means the dataset has no \
structure for that component, which is not the same as PFAS-free: say which components are unverified. If the \
compliant design space is empty, say so plainly and use data_gaps and find_pag_substitutes to recommend what \
to mine or test instead. If a surrogate's leave-one-out Q² is near or below zero, say its predictions for that \
objective are not reliable.

Finish with a design brief in Markdown, under 450 words, with these sections: Goal, Recommendation (a ranked \
table of at most 3 proposals with predicted values and 95% intervals), Evidence (citations), Compliance, \
Next steps (what to verify or extract)."""

TOOLS = [
    {"name": "list_campaigns",
     "description": "List the design campaigns: each is one patent's example table turned into a design space. "
                    "Returns factors, objectives with units and best observed values, experiment counts and caveats.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "surrogate_skill",
     "description": "Leave-one-out validation of the campaign's surrogate model for each objective (Q², Spearman, "
                    "95% interval coverage). Call before trusting predictions.",
     "input_schema": {"type": "object", "properties": {"campaign": {"type": "string"}},
                      "required": ["campaign"], "additionalProperties": False}},
    {"name": "propose_batch",
     "description": "Run compliance-aware batch Bayesian optimization on a campaign and return ranked proposals "
                    "with predicted medians and 95% intervals, compliance flags and the closest tested example. "
                    "compliance_policy: 'exclude' drops candidates with a blocking flag (PFAS or restricted), "
                    "'penalize' down-weights flagged candidates, 'ignore' skips compliance. "
                    "swap_fluorosurfactant replaces fluorinated surfactants with a silicone surfactant (an assumption "
                    "backed by WO2004107052A1 coating data; verify for the target resist).",
     "input_schema": {"type": "object", "properties": {
         "campaign": {"type": "string"},
         "mode": {"type": "string", "enum": ["mo", "scalar"],
                  "description": "'mo' = multi-objective (all objectives), 'scalar' = the campaign's single target"},
         "batch_size": {"type": "integer", "minimum": 1, "maximum": 6},
         "compliance_policy": {"type": "string", "enum": ["exclude", "penalize", "ignore"]},
         "swap_fluorosurfactant": {"type": "boolean"}},
         "required": ["campaign", "mode", "batch_size", "compliance_policy", "swap_fluorosurfactant"],
         "additionalProperties": False}},
    {"name": "screen_components",
     "description": "Screen a list of components (role + name as written in the patent) against PFAS, REACH and "
                    "metal rules. Returns flags with rule, severity, rationale, source and suggested substitutes.",
     "input_schema": {"type": "object", "properties": {
         "components": {"type": "array", "items": {"type": "object", "properties": {
             "role": {"type": "string"}, "name": {"type": "string"}}, "required": ["role", "name"],
             "additionalProperties": False}},
         "doc_id": {"type": "string"}}, "required": ["components"], "additionalProperties": False}},
    {"name": "check_structure",
     "description": "Check a SMILES string against the OECD 2021 PFAS definition and compute anion size and "
                    "electron-withdrawing pull at the acid site.",
     "input_schema": {"type": "object", "properties": {"smiles": {"type": "string"}},
                      "required": ["smiles"], "additionalProperties": False}},
    {"name": "find_pag_substitutes",
     "description": "Nearest non-PFAS PAG anions to a fluorinated reference anion, from a structure-only map "
                    "(size and acid-site pull). A shortlist of what to test, not a prediction of performance.",
     "input_schema": {"type": "object", "properties": {
         "reference_anion": {"type": "string"},
         "allow_aryl_fluorine": {"type": "boolean"}},
         "required": ["reference_anion"], "additionalProperties": False}},
    {"name": "search_dataset",
     "description": "Find records whose components match a name fragment (case-insensitive), with their patents, "
                    "outcomes and source locations. Use it to find substitution evidence.",
     "input_schema": {"type": "object", "properties": {
         "name_contains": {"type": "string"}, "role": {"type": "string"}},
         "required": ["name_contains"], "additionalProperties": False}},
    {"name": "data_gaps",
     "description": "The prioritized extraction worklist: gaps no model trained on this dataset can answer, with "
                    "evidence counts and suggested search queries.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


# ================================================================================================
# Tools
# ================================================================================================
def _r(x, n=3):
    try:
        return float(np.round(float(x), n))
    except (TypeError, ValueError):
        return x


class Toolbox:
    def __init__(self, gold: GoldSet | None = None, screener=None, extra_campaigns: dict | None = None):
        self.g = gold or load_gold()
        self.screener = screener or DefaultScreener()
        self.extra = extra_campaigns or {}

    # -- helpers ---------------------------------------------------------------------------------
    def campaign(self, key: str) -> Campaign:
        if key in self.extra:
            return self.extra[key]
        if key in BUILDERS:
            return get_campaign(key)
        if key.startswith("auto:"):
            from .autocampaign import build_auto_campaign
            self.extra[key] = build_auto_campaign(self.g, key.split(":", 1)[1])
            return self.extra[key]
        raise KeyError(f"unknown campaign '{key}'; call list_campaigns")

    def fluorosurfactant_swaps(self, c: Campaign) -> dict:
        comps = list(c.constant_components)
        swaps = {}
        for comp in comps:
            if comp["role"] != "surfactant":
                continue
            res = self.screener.screen([comp], c.doc_id)
            if res.pfas:
                swaps[comp["name"]] = SILICONE
        return swaps

    # -- tool implementations --------------------------------------------------------------------
    def list_campaigns(self) -> dict:
        out = []
        for key in [*BUILDERS, *self.extra]:
            c = self.campaign(key)
            out.append({
                "campaign": key, "title": c.title, "doc_id": c.doc_id, "exposure": c.exposure,
                "experiments": int(len(c.observed)),
                "factors": [f.label for f in c.factors],
                "objectives": [{"key": o.key, "label": o.label, "unit": o.unit, "direction": o.direction,
                                "best_observed": _r(best_observed(c, o.key))}
                               for o in [*c.objectives, *([c.scalar] if c.scalar.key not in
                                                          [o.key for o in c.objectives] else [])]],
                "caveats": c.caveats,
            })
        return {"campaigns": out,
                "note": "Other patents report constant or qualitative results and cannot support a campaign."}

    def surrogate_skill(self, campaign: str) -> dict:
        from .paths import RESULTS
        c = self.campaign(campaign)
        p = RESULTS / "cv" / "metrics.csv"
        keys = list(dict.fromkeys([o.key for o in c.objectives] + [c.scalar.key]))
        if campaign in BUILDERS and p.exists():
            m = pd.read_csv(p)
            m = m[(m.campaign == campaign) & (m.model == "additive+int") & m.objective.isin(keys)]
            rows = m[["objective", "n", "Q2", "Spearman", "Coverage95"]].round(3).to_dict("records")
        else:
            from .gp import loo_gp, transform_y
            from .bo import target_var
            X = c.encode(c.observed)
            rows = []
            for k in keys:
                o = c.objective(k)
                r = loo_gp(X, transform_y(c.y(k), o.log), c.groups(), "additive+int", target_var(c, k, c.observed))
                rows.append({"objective": k, "n": len(c.observed), **{a: _r(v) for a, v in r.metrics().items()
                                                                      if a in ("Q2", "Spearman", "Coverage95")}})
        return {"campaign": campaign, "model": "GP, additive kernel + interactions",
                "validation": "leave-one-out", "metrics": rows,
                "reading": "Q2 > 0.5 useful; 0-0.5 weak; below 0 no better than the mean."}

    def propose_batch(self, campaign: str, mode: str, batch_size: int, compliance_policy: str,
                      swap_fluorosurfactant: bool) -> dict:
        c = self.campaign(campaign)
        if mode == "mo" and len(c.objectives) < 2:
            mode = "scalar"
        swaps = self.fluorosurfactant_swaps(c) if swap_fluorosurfactant else None
        p = propose(c, mode=mode, q=int(batch_size), exclude_blocked=compliance_policy == "exclude",
                    penalty_weight=0.0 if compliance_policy == "ignore" else 0.5, swaps=swaps,
                    screener=self.screener)
        keys = [c.scalar.key] if mode == "scalar" else [o.key for o in c.objectives]
        extra_keys = ["Z"] if "Z_pred" in p.batch and "Z" not in keys else []
        props = []
        for _, r in p.batch.iterrows():
            res = c.screen(pd.DataFrame([r]), swaps, self.screener)[0]
            near = c.table[c.table.example_label == r["nearest_record"]].iloc[0]
            pred = {}
            for k in keys:
                o = c.objective(k)
                pred[o.label] = {"median": _r(r[f"{k}_pred"]), "lo95": _r(r[f"{k}_lo"]), "hi95": _r(r[f"{k}_hi"]),
                                 "unit": o.unit, "direction": o.direction}
            for k in extra_keys:
                pred["Z-factor (derived from predicted medians)"] = {"median": _r(r["Z_pred"]),
                                                                     "unit": c.scalar.unit}
            props.append({
                "rank": int(r["rank"]),
                "formulation": {f.label: (_r(r[f.name]) if f.kind == "cont" else r[f.name]) for f in c.factors},
                "predicted": pred,
                "compliance": [{"component": f.component, "rule": f.rule, "severity": f.severity,
                                "rationale": f.rationale, "source": f.source, "substitutes": list(f.substitutes)}
                               for f in res.flags if f.severity != "clear"],
                "unverified_structures": res.unverified,
                "closest_tested_example": {"label": r["nearest_record"], "doc_id": c.doc_id,
                                           "location": near["location"]},
            })
        best = {c.objective(k).label: _r(best_observed(c, k)) for k in keys}
        return {"campaign": campaign, "mode": mode, "compliance_policy": compliance_policy,
                "surfactant_swaps": swaps or {}, "notes": p.notes, "candidates_excluded": p.n_excluded,
                "best_observed": best, "proposals": props,
                "empty": len(props) == 0}

    def screen_components(self, components: list, doc_id: str | None = None) -> dict:
        res = self.screener.screen(components, doc_id)
        return {"flags": [{"component": f.component, "rule": f.rule, "severity": f.severity,
                           "rationale": f.rationale, "source": f.source, "confidence": f.confidence,
                           "substitutes": list(f.substitutes)} for f in res.flags],
                "unverified_structures": res.unverified, "worst": res.worst}

    def check_structure(self, smiles: str) -> dict:
        d = describe_smiles(smiles)
        if d is None:
            raise ValueError("RDKit could not parse that SMILES")
        return {k: _r(v) for k, v in d.items()}

    def find_pag_substitutes(self, reference_anion: str, allow_aryl_fluorine: bool = False) -> dict:
        lib = library_table()
        names = lib["anion"].tolist()
        match = next((n for n in names if reference_anion.lower() in n.lower()), None)
        if match is None:
            raise ValueError(f"unknown anion; choose from {lib[lib.pfas_oecd].anion.tolist()}")
        ref = lib[lib.anion == match].iloc[0]
        subs = substitutes(lib, match, k=5, allow_fluorine=allow_aryl_fluorine)
        return {"reference": {"anion": match, "size_A2": _r(ref.size_ASA, 1), "acid_site_pull": _r(ref.ewg_pull)},
                "substitutes": [{"anion": s.anion, "class": s["class"], "size_A2": _r(s.size_ASA, 1),
                                 "acid_site_pull": _r(s.ewg_pull), "distance": _r(s.distance), "smiles": s.smiles,
                                 "note": s.note} for _, s in subs.iterrows()],
                "method": "structure-only proxies (Labute ASA size; electron-withdrawing pull); not fit to data"}

    def search_dataset(self, name_contains: str, role: str | None = None) -> dict:
        c = self.g.components
        hit = c[c["name"].str.contains(re.escape(name_contains), case=False, na=False)]
        if role:
            hit = hit[hit["role"] == role]
        if hit.empty:
            return {"matches": 0}
        rec = self.g.records.set_index("record_id")
        res = self.g.results
        out = []
        for (rid_doc, name), grp in hit.assign(doc_id=hit.record_id.map(rec["doc_id"])).groupby(["doc_id", "name"]):
            rids = grp.record_id.unique()
            r = res[res.record_id.isin(rids)]
            classes = r["outcome_class"].value_counts().to_dict()
            out.append({"doc_id": rid_doc, "component": name, "role": grp.role.iloc[0], "records": len(rids),
                        "examples": rec.loc[rids, "example_label"].head(4).tolist(),
                        "location": rec.loc[rids[0], "location"],
                        "qualitative_outcomes": classes,
                        "numeric_results": r[r.value_num.notna()].groupby("metric_as_written")["value_num"]
                        .agg(["min", "max", "count"]).round(3).head(6).reset_index().to_dict("records")})
        return {"matches": int(len(hit)), "groups": out[:12]}

    def data_gaps(self) -> dict:
        comp = screen_records(self.g.components, self.g.records, self.screener)
        return {"worklist": extraction_worklist(self.g, comp).to_dict("records")}

    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if name not in {t["name"] for t in TOOLS} or fn is None:
            raise ValueError(f"unknown tool {name}")
        return fn(**(args or {}))


# ================================================================================================
# Agent loop
# ================================================================================================
@dataclass
class Event:
    kind: str               # thinking | tool_call | tool_result | text | error | info
    content: object
    elapsed: float = 0.0


@dataclass
class AgentRun:
    goal: str
    mode: str               # "claude" | "planner"
    events: list[Event] = field(default_factory=list)
    final: str = ""
    usage: dict = field(default_factory=dict)

    def tool_calls(self) -> list[Event]:
        return [e for e in self.events if e.kind == "tool_call"]


def _validate(name: str, args: dict) -> dict:
    spec = next((t for t in TOOLS if t["name"] == name), None)
    if spec is None:
        raise ValueError(f"unknown tool '{name}'")
    spec = spec["input_schema"]
    props, req = spec.get("properties", {}), spec.get("required", [])
    if not isinstance(args, dict):
        raise ValueError("tool input must be an object")
    missing = [k for k in req if k not in args]
    extra = [k for k in args if k not in props]
    if missing or extra:
        raise ValueError(f"missing {missing}, unexpected {extra}")
    for k, v in args.items():
        enum = props[k].get("enum")
        if enum and v not in enum:
            raise ValueError(f"{k} must be one of {enum}")
    return args


def has_credentials() -> bool:
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def run_agent(goal: str, toolbox: Toolbox | None = None, client=None, max_turns: int = 14,
              on_event: Callable[[Event], None] | None = None, effort: str = "high") -> AgentRun:
    toolbox = toolbox or Toolbox()
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    run = AgentRun(goal, "claude")
    t0 = time.time()

    def emit(kind, content):
        ev = Event(kind, content, time.time() - t0)
        run.events.append(ev)
        if on_event:
            on_event(ev)

    messages = [{"role": "user", "content": goal}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    for _ in range(max_turns):
        response = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages,
            thinking={"type": "adaptive", "display": "summarized"}, output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        u = getattr(response, "usage", None)
        for k in usage:
            usage[k] += int(getattr(u, k, 0) or 0)
        if response.stop_reason == "refusal":
            emit("error", "The model declined this request.")
            break
        for block in response.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                emit("thinking", block.thinking)
            elif block.type == "text" and block.text.strip():
                emit("text", block.text)
        if response.stop_reason == "max_tokens":
            emit("error", "The response hit max_tokens before finishing.")
            break
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            run.final = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for tu in tool_uses:
            args = tu.input if isinstance(tu.input, dict) else json.loads(tu.input)
            emit("tool_call", {"name": tu.name, "input": args})
            try:
                out = toolbox.call(tu.name, _validate(tu.name, args))
                emit("tool_result", {"name": tu.name, "output": out})
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": json.dumps(out, default=str)})
            except Exception as e:  # tool errors go back to the model, not up the stack
                emit("tool_result", {"name": tu.name, "error": str(e)})
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": f"Error: {e}",
                                "is_error": True})
        messages.append({"role": "user", "content": results})
    else:
        emit("error", f"Stopped after {max_turns} turns.")
    run.usage = usage
    return run


# ================================================================================================
# Rule-based planner (no LLM)
# ================================================================================================
def _pick_campaign(goal: str) -> str:
    g = goal.lower()
    if "euv" in g or "13.5" in g:
        return "euv"
    if any(w in g for w in ("su-8", "su8", "thick", "plating", "crack")):
        return "su8"
    return "ebeam"


def run_planner(goal: str, toolbox: Toolbox | None = None,
                on_event: Callable[[Event], None] | None = None) -> AgentRun:
    toolbox = toolbox or Toolbox()
    run = AgentRun(goal, "planner")
    t0 = time.time()

    def emit(kind, content):
        ev = Event(kind, content, time.time() - t0)
        run.events.append(ev)
        if on_event:
            on_event(ev)

    def step(name, **args):
        emit("tool_call", {"name": name, "input": args})
        out = toolbox.call(name, args)
        emit("tool_result", {"name": name, "output": out})
        return out

    pfas_free = "pfas" in goal.lower() or "fluor" in goal.lower()
    key = _pick_campaign(goal)
    step("list_campaigns")
    skill = step("surrogate_skill", campaign=key)
    c = toolbox.campaign(key)
    mode = "mo" if len(c.objectives) > 1 else "scalar"
    batch = step("propose_batch", campaign=key, mode=mode, batch_size=3,
                 compliance_policy="exclude" if pfas_free else "penalize", swap_fluorosurfactant=pfas_free)
    evidence = step("search_dataset", name_contains="BYK", role="surfactant") if batch["surfactant_swaps"] else None
    gaps = subs = None
    if batch["empty"]:
        gaps = step("data_gaps")
        subs = step("find_pag_substitutes", reference_anion="nonaflate", allow_aryl_fluorine=False)
    run.final = _planner_brief(goal, c, skill, batch, evidence, gaps, subs)
    return run


def _planner_brief(goal, c, skill, batch, evidence, gaps, subs) -> str:
    q2 = {m["objective"]: m["Q2"] for m in skill["metrics"]}
    lines = ["*Rule-based planner (no LLM): a fixed sequence of the same tools the agent uses.*", "",
             "## Goal", goal, ""]
    if batch["empty"]:
        lines += ["## Recommendation",
                  f"No candidate in {c.doc_id}'s design space passes the compliance filter: every PAG it tested is "
                  "PFAS-flagged. Optimization cannot fix this; new data can.", ""]
        if subs:
            lines += ["Non-PFAS PAG anions closest to nonaflate (structure-only shortlist):", ""]
            lines += [f"- {s['anion']} (size {s['size_A2']} Å², acid-site pull {s['acid_site_pull']} vs "
                      f"{subs['reference']['acid_site_pull']})" for s in subs["substitutes"][:3]]
            lines.append("")
    else:
        lines += ["## Recommendation", "", "| Rank | Formulation | " +
                  " | ".join(batch["proposals"][0]["predicted"]) + " |",
                  "|---|---|" + "---|" * len(batch["proposals"][0]["predicted"])]
        for p in batch["proposals"]:
            form = ", ".join(f"{k}: {v}" for k, v in p["formulation"].items())
            preds = " | ".join(f"{v['median']}" + (f" [{v['lo95']}, {v['hi95']}]" if "lo95" in v else "")
                               for v in p["predicted"].values())
            lines.append(f"| {p['rank']} | {form} | {preds} |")
        lines += ["", "Best observed: " + ", ".join(f"{k} {v}" for k, v in batch["best_observed"].items()), ""]
        weak = [k for k, v in q2.items() if v is not None and v < 0.2]
        if weak:
            lines += [f"Surrogate skill is weak for {', '.join(weak)} (leave-one-out Q² < 0.2): treat those "
                      "predictions as rough.", ""]
    lines += ["## Evidence"]
    if not batch["empty"]:
        lines += [f"- Closest tested example for #{p['rank']}: {p['closest_tested_example']['label']} "
                  f"({p['closest_tested_example']['doc_id']}, {p['closest_tested_example']['location']})"
                  for p in batch["proposals"]]
    if evidence and evidence.get("groups"):
        g0 = evidence["groups"]
        pos = sum(x["qualitative_outcomes"].get("positive", 0) for x in g0)
        rated = sum(sum(x["qualitative_outcomes"].values()) for x in g0)
        lines.append(f"- Surfactant swap: {sum(x['records'] for x in g0)} records use silicone surfactants "
                     f"({', '.join(sorted({x['doc_id'] for x in g0}))}, {g0[0]['location']}); {pos} of {rated} "
                     "coating ratings are positive. Evidence for coating quality, not yet for lithography.")
    lines += ["", "## Compliance"]
    if batch["surfactant_swaps"]:
        lines.append("- Assumed swap: " + "; ".join(f"{a} → {b}" for a, b in batch["surfactant_swaps"].items()))
    if not batch["empty"]:
        for p in batch["proposals"]:
            flags = "; ".join(f"{f['severity']} {f['rule']}: {f['component']}" for f in p["compliance"]) or "no flags"
            unv = ", ".join(p["unverified_structures"])
            lines.append(f"- #{p['rank']}: {flags}" + (f"; structure unverified: {unv}" if unv else ""))
    lines.append("- Screening aid only; confirm identities on SDS/CAS.")
    lines += ["", "## Next steps"]
    if gaps:
        lines += [f"- P{w['priority']} {w['gap']}: {w['extract']}" for w in gaps["worklist"][:3]]
    else:
        subs_by_comp = {f["component"]: f["substitutes"] for p in batch["proposals"] for f in p["compliance"]
                        if f["substitutes"]}
        lines += [f"- Evaluate substitutes for {comp}: {', '.join(s)}." for comp, s in subs_by_comp.items()]
        if any(p["unverified_structures"] for p in batch["proposals"]):
            lines.append("- Obtain structures for the unverified components above to confirm they are PFAS-free.")
        lines.append("- Run the top proposal and its closest tested example side by side as a control.")
    return "\n".join(lines)
