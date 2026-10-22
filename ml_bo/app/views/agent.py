import json

import streamlit as st

from ui import active_screener, page_header

from neglines.agent import TOOLS, Toolbox, has_credentials, run_agent, run_planner

page_header("Design agent",
            "Give it a goal. The agent checks which campaigns can answer it, how far each surrogate can be "
            "trusted, runs compliance-aware Bayesian optimization, looks for substitution evidence in the "
            "dataset and writes a brief that cites its sources.")

live = has_credentials()
engines = ["claude", "planner"]
labels = {"claude": "Claude Opus 5.5 (live agent)", "planner": "Rule-based planner (offline, no LLM)"}
engine = st.segmented_control("Engine", engines, format_func=labels.get, default="claude" if live else "planner")
if engine == "claude" and not live:
    st.warning("No Anthropic credentials found. Set `ANTHROPIC_API_KEY` before launching "
               "(`$env:ANTHROPIC_API_KEY = \"sk-ant-...\"; .\\run_app.ps1`) to run the live agent. The rule-based "
               "planner below uses the same tools.", icon=":material/key:")

PRESETS = {
    "PFAS-reduced e-beam resist": "Design a PFAS-free e-beam negative resist with LER at or below the best tested "
                                  "example. Tell me which components are still unverified.",
    "PFAS-free EUV resist": "Find a PFAS-free EUV negative-tone formulation with LWR under 3.3 nm and Eop under "
                            "60 mJ/cm². If none exists in the data, say what to mine or test next.",
    "Crack-free thick SU-8": "Recommend process conditions that minimize via cracking in thick SU-8 films, and "
                             "flag any compliance problems with the formulation.",
}
preset = st.pills("Example goals", list(PRESETS), default=list(PRESETS)[0])
goal = st.text_area("Goal", PRESETS.get(preset, ""), height=90)
go = st.button("Run agent", type="primary", icon=":material/play_arrow:", disabled=not goal.strip() or
               (engine == "claude" and not live))


def summarize(name: str, payload: dict) -> str:
    if "error" in payload:
        return f"error: {payload['error']}"
    out = payload.get("output", {})
    if name == "list_campaigns":
        return f"{len(out['campaigns'])} campaigns: " + ", ".join(c["campaign"] for c in out["campaigns"])
    if name == "surrogate_skill":
        return "LOO Q²: " + ", ".join(f"{m['objective']} {m['Q2']:.2f}" for m in out["metrics"])
    if name == "propose_batch":
        if out["empty"]:
            return f"no compliant candidates ({out['candidates_excluded']} excluded)"
        top = out["proposals"][0]["predicted"]
        return f"{len(out['proposals'])} proposals; #1 " + ", ".join(
            f"{k} {v['median']}" for k, v in list(top.items())[:3])
    if name == "search_dataset":
        return f"{out.get('matches', 0)} component rows matched"
    if name == "data_gaps":
        return f"{len(out['worklist'])} worklist items"
    if name == "find_pag_substitutes":
        return "nearest: " + ", ".join(s["anion"] for s in out["substitutes"][:3])
    if name == "screen_components":
        return f"worst: {out['worst']}, {len(out['flags'])} flags"
    return json.dumps(out)[:120]


def render(ev, box):
    with box:
        if ev.kind == "tool_call":
            args = ", ".join(f"{k}={v!r}" for k, v in ev.content["input"].items())
            st.markdown(f"`{ev.elapsed:5.1f}s` **→ {ev.content['name']}**({args})")
        elif ev.kind == "tool_result":
            with st.expander(f"← {ev.content['name']}: {summarize(ev.content['name'], ev.content)}"):
                st.json(ev.content.get("output", ev.content), expanded=False)
        elif ev.kind == "thinking":
            st.caption(f"💭 {ev.content}")
        elif ev.kind == "text":
            st.markdown(ev.content)
        elif ev.kind == "error":
            st.error(ev.content)


if go:
    toolbox = Toolbox(screener=active_screener())
    with st.status("Working…", expanded=True) as status:
        box = st.container()
        try:
            if engine == "claude":
                run = run_agent(goal, toolbox, on_event=lambda e: render(e, box))
            else:
                run = run_planner(goal, toolbox, on_event=lambda e: render(e, box))
            status.update(label=f"Done: {len(run.tool_calls())} tool calls", state="complete", expanded=False)
            st.session_state["agent_run"] = run
        except Exception as e:  # surface API/auth errors without losing the page
            status.update(label="Failed", state="error")
            st.error(f"{type(e).__name__}: {e}")

run = st.session_state.get("agent_run")
if run is not None:
    st.subheader("Design brief")
    if run.mode == "planner":
        st.caption("Produced by the rule-based planner: same tools, fixed sequence, templated text.")
    elif run.usage:
        st.caption(f"Claude Opus 5.5 · {len(run.tool_calls())} tool calls · "
                   f"{run.usage['input_tokens']:,} input / {run.usage['output_tokens']:,} output tokens")
    with st.container(border=True):
        st.markdown(run.final or "_No final text returned._")
    transcript = [{"kind": e.kind, "t": round(e.elapsed, 2), "content": e.content} for e in run.events]
    c1, c2, _ = st.columns([1, 1, 3])
    c1.download_button("Brief (.md)", run.final, file_name="agent_brief.md", icon=":material/description:")
    c2.download_button("Transcript (.json)", json.dumps({"goal": run.goal, "engine": run.mode, "events": transcript},
                                                        default=str, indent=1),
                       file_name="agent_transcript.json", icon=":material/download:")

with st.expander("Tools the agent can call"):
    for t_ in TOOLS:
        st.markdown(f"**{t_['name']}**: {t_['description']}")
    st.caption("Model: claude-opus-5-5 with adaptive thinking and server-side refusal fallback. Every number in "
               "the brief must come from a tool result.")
