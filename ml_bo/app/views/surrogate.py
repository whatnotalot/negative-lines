import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import CAMPAIGN_LABELS, MODEL_LABELS, campaign, cv_metrics, cv_predictions, marker, page_header, show, style, tokens

t = tokens()
page_header("Surrogate lab", "Leave-one-out validation of every model on every objective. With 13 to 18 experiments "
                             "per campaign, honest validation matters more than model size.")
cv, preds = cv_metrics(), cv_predictions()
if cv is None:
    st.warning("Run `python scripts/run_cv.py` first to precompute the cross-validation results.")
    st.stop()

f1, f2, f3 = st.columns([3, 2, 2])
key = f1.segmented_control("Campaign", list(CAMPAIGN_LABELS), format_func=CAMPAIGN_LABELS.get, default="ebeam")
c = campaign(key)
objs = list(dict.fromkeys([o.key for o in c.objectives] + [c.scalar.key]))
obj = f2.selectbox("Objective", objs, format_func=lambda k: f"{c.objective(k).label} ({c.objective(k).unit})")
m = cv[(cv.campaign == key) & (cv.objective == obj)].copy()
best = m.sort_values("Q2", ascending=False).iloc[0]["model"]
model = f3.selectbox("Model for the parity plot", list(MODEL_LABELS), format_func=MODEL_LABELS.get,
                     index=list(MODEL_LABELS).index(best))

left, right = st.columns([2, 3])
with left:
    st.markdown("**Leave-one-out Q²** (1 = perfect, 0 = no better than the mean)")
    m["label"] = m.model.map(MODEL_LABELS)
    m = m.sort_values("Q2")
    fig = go.Figure(go.Bar(
        y=m.label, x=m.Q2.clip(lower=-1), orientation="h",
        marker=dict(color=[t["s1"] if mm == model else t["grid"] for mm in m.model], cornerradius=4),
        text=[f"{v:.2f}" for v in m.Q2], textposition="outside", textfont=dict(color=t["ink2"]),
        cliponaxis=False, hovertemplate="%{y}<br>Q² %{x:.2f}<extra></extra>"))
    style(fig, height=280, legend=False, xaxis_range=[min(-0.45, m.Q2.clip(lower=-1).min() - 0.3), 1.12])
    fig.add_vline(x=0, line=dict(color=t["axis"], width=1))
    show(fig, m[["label", "Q2", "RMSE", "Spearman", "Coverage95", "NLPD", "n"]].rename(columns={"label": "model"}),
         key="q2bar", caption="Coverage95 is the share of held-out points inside the 95% predictive interval. "
                              "Near 0.95 means the error bars can be trusted.")

with right:
    p = preds[(preds.campaign == key) & (preds.objective == obj) & (preds.model == model)].copy()
    o = c.objective(obj)
    back = np.exp if o.log else (lambda v: v)
    p["obs"], p["pred"] = back(p.y), back(p.mu)
    p["lo"], p["hi"] = back(p.mu - 1.96 * p.sd), back(p.mu + 1.96 * p.sd)
    lims = [min(p.obs.min(), p.lo.min()), max(p.obs.max(), p.hi.max())]
    fig = go.Figure()
    fig.add_scatter(x=lims, y=lims, mode="lines", line=dict(color=t["axis"], width=1), hoverinfo="skip",
                    showlegend=False)
    fig.add_scatter(x=p.obs, y=p.pred, mode="markers", name="held-out prediction", marker=marker(t["s1"], 10),
                    error_y=dict(type="data", symmetric=False, array=p.hi - p.pred, arrayminus=p.pred - p.lo,
                                 color=t["s1"], thickness=1.5, width=0),
                    customdata=p[["example_label", "lo", "hi"]],
                    hovertemplate="<b>%{customdata[0]}</b><br>observed %{x:.3g}<br>predicted %{y:.3g} "
                                  "[%{customdata[1]:.3g}, %{customdata[2]:.3g}]<extra></extra>")
    style(fig, height=380, legend=False, xaxis_title=f"Observed {o.label} ({o.unit})",
          yaxis_title=f"Predicted, leave-one-out ({o.unit})")
    if o.log:
        fig.update_xaxes(type="log")
        fig.update_yaxes(type="log")
    show(fig, p[["example_label", "obs", "pred", "lo", "hi"]], key="parity",
         caption=f"{MODEL_LABELS[model]}: each point is predicted by a model that never saw it. Bars are 95% intervals.")


@st.cache_resource(show_spinner="Fitting the additive GP…")
def relevance(key, obj):
    from neglines.bo import fit_objectives
    from neglines.gp import group_relevance
    cc = campaign(key)
    models, _ = fit_objectives(cc, cc.observed, [obj], "additive+int")
    return group_relevance(models[0], cc.groups(), [f.label for f in cc.factors])


st.subheader("What the additive GP thinks matters")
rel = pd.Series(relevance(key, obj)).sort_values()
fig = go.Figure(go.Bar(y=rel.index, x=rel.values, orientation="h", marker=dict(color=t["s1"], cornerradius=4),
                       text=[f"{v:.0%}" for v in rel.values], textposition="outside", textfont=dict(color=t["ink2"]),
                       hovertemplate="%{y}: %{x:.1%} of prior variance<extra></extra>"))
style(fig, height=60 + 32 * len(rel), legend=False, xaxis_tickformat=".0%",
      xaxis_title="Share of the kernel's output scale (fit on all observed data)")
show(fig, rel.rename_axis("factor").reset_index(name="share"), key="rel",
     caption="Output-scale shares of the additive components. They describe how the model explains these "
             "examples, not causal effect sizes.")
with st.expander("Campaign caveats"):
    for cav in c.caveats:
        st.markdown(f"- {cav}")
