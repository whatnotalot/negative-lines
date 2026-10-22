from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ui import CAMPAIGN_LABELS, STATUS_LABEL, active_screener, campaign, marker, page_header, rules_text, screener_for, show, style, tokens

from neglines.bo import best_observed

t = tokens()
SILICONE_SWAP = {'Megafac F176 ("W-1")': "BYK-333 (polyether-modified PDMS)"}
page_header("Design studio", "Compliance-aware batch Bayesian optimization over each patent's design space. "
                             "Proposals are the next experiments worth running, with uncertainty and a citation "
                             "to the closest tested example.")

key = st.segmented_control("Campaign", list(CAMPAIGN_LABELS), format_func=CAMPAIGN_LABELS.get, default="euv")
c = campaign(key)
st.caption(c.blurb)

with st.form("design"):
    a, b, d, e = st.columns([2, 1, 2, 2])
    modes = ["mo", "scalar"] if len(c.objectives) > 1 else ["scalar"]
    mode = a.radio("Acquisition", modes, horizontal=True,
                   format_func=lambda m: "qLogNEHVI: " + " + ".join(o.label for o in c.objectives) if m == "mo"
                   else f"qLogNEI: {c.scalar.label}")
    q = b.number_input("Batch size", 1, 8, 5)
    policy = d.radio("Compliance policy", ["penalize", "exclude", "ignore"], horizontal=True,
                     format_func={"penalize": "Penalize", "exclude": "Exclude blocked", "ignore": "Ignore"}.get,
                     help="Penalize multiplies the acquisition by (1 − w·penalty): block = 1, SVHC = 0.5, watch = 0.1.")
    weight = e.slider("Penalty weight w", 0.0, 1.0, 0.5, 0.05)
    swap = False
    if key == "ebeam":
        swap = st.checkbox("Swap the fluorosurfactant (Megafac F176) for a silicone surfactant", value=False,
                           help="Evidence: in WO2004107052A1 the ten BYK silicone-surfactant embodiments coat as well as "
                                "the fluorosurfactant ones. It is an assumption for this resist, not a measurement.")
    st.form_submit_button("Propose batch", type="primary", icon=":material/science:")


@st.cache_data(show_spinner="Fitting surrogates and optimizing the acquisition…", max_entries=24, persist="disk")
def run(key, mode, q, policy, weight, swap, rules):
    from neglines.bo import propose
    return propose(campaign(key), mode=mode, q=int(q), exclude_blocked=policy == "exclude",
                   penalty_weight=0.0 if policy == "ignore" else weight, swaps=SILICONE_SWAP if swap else None,
                   screener=screener_for(rules))


p = run(key, mode, q, policy, weight, swap, rules_text())
for n in p.notes:
    st.caption(f"ⓘ {n}")

keys = [c.scalar.key] if mode == "scalar" else [o.key for o in c.objectives]
factor_cols = [f.name for f in c.factors]
if p.batch.empty:
    st.error("No compliant candidate exists in this patent's design space: every PAG it tested is PFAS-flagged. "
             "Better optimization cannot fix this. The fix is new data with non-fluorinated PAGs.", icon=":material/block:")
    st.page_link("views/gaps.py", label="See what to mine next", icon=":material/travel_explore:")
    st.page_link("views/anions.py", label="Screen PFAS-free PAG anions", icon=":material/hub:")
    st.stop()

# --- proposal table -----------------------------------------------------------------------------
batch = p.batch.copy()
best_obs = {k: best_observed(c, k) for k in keys}
show_cols = ["rank"] + factor_cols
cfg = {}
for k in keys:
    o = c.objective(k)
    batch[f"{o.label} ({o.unit})"] = [f"{m:.3g}  [{lo:.3g}, {hi:.3g}]" for m, lo, hi in
                                      zip(batch[f"{k}_pred"], batch[f"{k}_lo"], batch[f"{k}_hi"])]
    show_cols.append(f"{o.label} ({o.unit})")
if "Z_pred" in batch:
    batch["Z (pred)"] = batch["Z_pred"].round(2)
    show_cols.append("Z (pred)")
batch["status"] = batch["worst"].map(STATUS_LABEL)
show_cols += ["status", "compliance", "nearest_record"]
st.subheader("Proposed batch")
st.dataframe(batch[show_cols], hide_index=True, width="stretch",
             column_config={"nearest_record": "closest tested example", "compliance": st.column_config.TextColumn(width="large")})
st.caption("Predictions are posterior medians with 95% intervals. "
           + " · ".join(f"best observed {c.objective(k).label}: {v:.3g}" for k, v in best_obs.items()))

# --- objective space / process window ----------------------------------------------------------
cand, obs = p.candidates, c.observed
if key in ("euv", "ebeam"):
    xk, yk = ("Eop", "LWR") if key == "euv" else ("sensitivity", "LER")
    xo, yo = c.objective(xk), c.objective(yk)
    fig = go.Figure()
    cloud = cand.sample(min(len(cand), 3000), random_state=0)
    fig.add_scattergl(x=cloud[f"{xk}_pred"], y=cloud[f"{yk}_pred"], mode="markers", name="Untested candidates (predicted)",
                      marker=dict(color=t["muted"], size=5, opacity=0.25), hoverinfo="skip")
    fig.add_scatter(x=obs[xk], y=obs[yk], mode="markers", name="Tested examples", marker=marker(t["s1"], 10),
                    customdata=obs[["example_label"]], hovertemplate="<b>%{customdata[0]}</b><br>"
                    f"{xo.label} %{{x:.3g}} · {yo.label} %{{y:.3g}}<extra></extra>")
    fig.add_scatter(x=batch[f"{xk}_pred"], y=batch[f"{yk}_pred"], mode="markers+text", name="Proposed batch",
                    marker=marker(t["s2"], 14, "diamond"), text=[f"#{r}" for r in batch["rank"]],
                    textposition="top center", textfont=dict(color=t["ink"], size=12),
                    error_x=dict(type="data", symmetric=False, array=batch[f"{xk}_hi"] - batch[f"{xk}_pred"],
                                 arrayminus=batch[f"{xk}_pred"] - batch[f"{xk}_lo"], color=t["s2"], thickness=1, width=0),
                    error_y=dict(type="data", symmetric=False, array=batch[f"{yk}_hi"] - batch[f"{yk}_pred"],
                                 arrayminus=batch[f"{yk}_pred"] - batch[f"{yk}_lo"], color=t["s2"], thickness=1, width=0),
                    hovertemplate=f"{xo.label} %{{x:.3g}} · {yo.label} %{{y:.3g}}<extra>proposal</extra>")
    style(fig, height=460, xaxis_title=f"{xo.label} ({xo.unit})", yaxis_title=f"{yo.label} ({yo.unit})")
    show(fig, cand[factor_cols + [f"{k}_pred" for k in keys] + ["compliance"]].head(2000), key="space",
         caption="Down and to the left is better. Grey points are the surrogate's predictions for every untested "
                 "combination; the proposals balance predicted gain against uncertainty.")
else:
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=["Unmodified SU-8", "Modified SU-8 (+DOP, +GPTMS)"],
                        horizontal_spacing=0.06)
    for j, form in enumerate(["unmodified", "modified"], start=1):
        for ramp, col, band in [("fast", t["s2"], t["band2"]), ("slow", t["s1"], t["band1"])]:
            s = cand[(cand.formulation == form) & (cand.ramp == ramp)].sort_values("dose")
            fig.add_scatter(x=list(s.dose) + list(s.dose[::-1]), y=list(s.cracking_hi.clip(0, 100)) +
                            list(s.cracking_lo.clip(0, 100)[::-1]), fill="toself", fillcolor=band, line=dict(width=0),
                            hoverinfo="skip", showlegend=False, row=1, col=j)
            fig.add_scatter(x=s.dose, y=s.cracking_pred.clip(0, 100), mode="lines", line=dict(color=col, width=2),
                            name=f"{ramp} bake ramp", legendgroup=ramp, showlegend=j == 1,
                            hovertemplate=f"{ramp}: %{{y:.0f}}% at %{{x:.0f}} mJ/cm²<extra></extra>", row=1, col=j)
            o_ = obs[(obs.formulation == form) & (obs.ramp == ramp)]
            fig.add_scatter(x=o_.dose, y=o_.cracking, mode="markers", marker=marker(col, 10), legendgroup=ramp,
                            showlegend=False, customdata=o_[["wafer_values"]],
                            hovertemplate="observed %{y:.1f}%<br>%{customdata[0]}<extra></extra>", row=1, col=j)
        pb = batch[batch.formulation == form]
        if len(pb):
            fig.add_scatter(x=pb.dose, y=pb.cracking_pred.clip(0, 100), mode="markers+text", text=[f"#{r}" for r in pb["rank"]],
                            textposition="bottom center", textfont=dict(color=t["ink"]), marker=marker(t["ink"], 12, "diamond"),
                            name="Proposed batch", showlegend=j == 2, hovertemplate="proposal: %{y:.0f}% at %{x:.0f}<extra></extra>",
                            row=1, col=j)
    style(fig, height=420, yaxis_title="Vias cracked (%)", hovermode="x unified")
    fig.update_xaxes(title_text="Exposure dose (mJ/cm²)")
    fig.update_annotations(font=dict(color=t["ink2"], size=13))
    show(fig, cand[["formulation", "ramp", "dose", "cracking_pred", "cracking_lo", "cracking_hi", "compliance"]], key="window",
         caption="Process window from the GP with noise taken from the quadrant spread. A slow ramp at high dose "
                 "is the only region under 20% cracking, and the plasticized formulation is the one that gets there. "
                 "It relies on DOP, a phthalate.")

# --- design brief -------------------------------------------------------------------------------
def brief() -> str:
    screener = active_screener()
    lines = [f"# Design brief · {c.title}", "",
             f"Generated {date.today().isoformat()} by the Negative Lines ML & BO module. Source: {c.doc_id} "
             f"(reconciled gold set). Acquisition: {'qLogNEHVI' if mode == 'mo' else 'qLogNEI'}; compliance policy: "
             f"{policy}" + (f" (w = {weight})" if policy == "penalize" else "") +
             ("; fluorosurfactant swapped for silicone (assumption)" if swap else "") + ".", ""]
    for _, r in batch.iterrows():
        lines.append(f"## Proposal {r['rank']}")
        lines.append(", ".join(f"{f.label}: {r[f.name]:.3g}" if f.kind == "cont" else f"{f.label}: {r[f.name]}"
                               for f in c.factors))
        lines.append("")
        for k in keys:
            o = c.objective(k)
            lines.append(f"- Predicted {o.label}: {r[f'{k}_pred']:.3g} {o.unit} (95% interval "
                         f"{r[f'{k}_lo']:.3g} to {r[f'{k}_hi']:.3g}); best observed {best_obs[k]:.3g}")
        near = c.table[c.table.example_label == r["nearest_record"]].iloc[0]
        lines.append(f"- Closest tested example: {r['nearest_record']} ({c.doc_id}, {near['location']})")
        res = screener.screen([{**x, "name": (SILICONE_SWAP.get(x["name"], x["name"]) if swap else x["name"])}
                               for x in c.components_of(r)], c.doc_id)
        for fl in res.flags:
            if fl.severity == "clear":
                continue
            sub = f" Substitutes to evaluate: {', '.join(fl.substitutes)}." if fl.substitutes else ""
            lines.append(f"- Compliance {fl.severity.upper()} ({fl.rule}, {fl.source}, confidence {fl.confidence}): "
                         f"{fl.component}. {fl.rationale}{sub}")
        if res.unverified:
            lines.append(f"- Structures not in the dataset, compliance unverified: {', '.join(res.unverified)}")
        lines.append("")
    lines += ["## Caveats", *[f"- {cv}" for cv in c.caveats],
              "- Compliance output is a screening aid, not legal advice; verify against current official lists."]
    return "\n".join(lines)


d1, d2, _ = st.columns([1, 1, 3])
d1.download_button("Design brief (.md)", brief(), file_name=f"design_brief_{key}.md", icon=":material/description:")
d2.download_button("Proposals (.csv)", p.batch.to_csv(index=False), file_name=f"proposals_{key}.csv",
                   icon=":material/download:")
with st.expander("Preview the design brief"):
    st.markdown(brief())
