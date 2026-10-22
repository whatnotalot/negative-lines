import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import CAMPAIGN_LABELS, STRATEGY_LABELS, bo_savings, campaign, cv_metrics, page_header, replay_summary, replay_traces, show, style, tokens

t = tokens()
page_header("BO replay", "Each patent's example table is a closed pool of experiments. Starting from two random "
                         "examples, how many experiments does each strategy need to reach the inventors' best result?")
traces, summary = replay_traces(), replay_summary()
if traces is None:
    st.warning("Run `python scripts/run_replay.py` first.")
    st.stop()

f1, f2 = st.columns([3, 2])
key = f1.segmented_control("Campaign", list(CAMPAIGN_LABELS), format_func=CAMPAIGN_LABELS.get, default="su8")
c = campaign(key)
modes = sorted(traces.loc[traces.campaign == key, "mode"].unique(), key=lambda m: m != "scalar")
mode_label = {"scalar": f"Single objective: {c.scalar.label}",
              "mo": "Multi-objective: " + ", ".join(o.label for o in c.objectives)}
mode = f2.segmented_control("Target", modes, format_func=mode_label.get, default=modes[0])
tr = traces[(traces.campaign == key) & (traces["mode"] == mode)]
sm = summary[(summary.campaign == key) & (summary["mode"] == mode)]
target_txt = (f"the lowest {c.scalar.label} in the pool" if mode == "scalar"
              else "95% of the pool's full hypervolume")

med = sm.groupby("strategy")["experiments_to_target"].median()
n_pool = len(c.table)
st.markdown("**Experiments needed to reach the target**")
m1, m2, m3, m4 = st.columns(4)
m1.metric("BO (median)", f"{med['bo']:.0f}", border=True, help="Median over 30 seeds.")
m2.metric("Random (median)", f"{med['random']:.0f}", border=True, help="Median over 300 seeds.")
m3.metric("Patent order", f"{med['patent_order']:.0f}", border=True,
          help="Examples run in the order the patent numbers them.")
m4.metric("Saved vs random", f"{1 - med['bo'] / med['random']:.0%}", border=True,
          help=f"Pool size: {n_pool} experiments, including the 2 random starting points.")
st.caption(f"Target: {target_txt}. Pool: {n_pool} experiments.")

# --- trajectories ------------------------------------------------------------------------------
fig = go.Figure()
colors = {"bo": (t["s1"], t["band1"]), "random": (t["s2"], t["band2"]), "patent_order": (t["s3"], None)}
rows = []
for rank, strat in [(2, "random"), (1, "bo"), (3, "patent_order")]:
    s = tr[tr.strategy == strat].groupby("step")["value"]
    q = s.quantile([0.25, 0.5, 0.75]).unstack()
    col, band = colors[strat]
    if band and strat != "patent_order":
        fig.add_scatter(x=list(q.index) + list(q.index[::-1]), y=list(q[0.75]) + list(q[0.25][::-1]),
                        fill="toself", fillcolor=band, line=dict(width=0), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=q.index, y=q[0.5], mode="lines", name=STRATEGY_LABELS[strat], line=dict(color=col, width=2),
                    legendrank=rank, hovertemplate=f"{STRATEGY_LABELS[strat]}: %{{y:.3g}}<extra></extra>")
    rows.append(q.assign(strategy=STRATEGY_LABELS[strat]).reset_index())
if mode == "scalar":
    best = np.nanmin(c.table[c.scalar.key])
    fig.add_hline(y=best, line=dict(color=t["axis"], width=1))
    ytitle = f"Best {c.scalar.label} found so far ({c.scalar.unit})"
else:
    fig.add_hline(y=0.95, line=dict(color=t["axis"], width=1))
    ytitle = "Hypervolume found so far (fraction of pool)"
style(fig, height=420, hovermode="x unified", xaxis_title="Experiments run", yaxis_title=ytitle)
show(fig, pd.concat(rows).rename(columns={0.25: "q25", 0.5: "median", 0.75: "q75"}), key="traj",
     caption="Lines are medians, bands the interquartile range across seeds. The hairline marks the target.")

# --- distribution -------------------------------------------------------------------------------
st.subheader("Chance of having found the target after k experiments")
fig = go.Figure()
ks = np.arange(1, n_pool + 1)
cdf_rows = []
for rank, strat in [(1, "bo"), (2, "random"), (3, "patent_order")]:
    v = sm[sm.strategy == strat]["experiments_to_target"].to_numpy()
    p = np.array([(v <= k).mean() for k in ks])
    fig.add_scatter(x=ks, y=p, mode="lines+markers", name=STRATEGY_LABELS[strat], legendrank=rank,
                    line=dict(color=colors[strat][0], width=2, shape="hv"), marker=dict(size=8, color=colors[strat][0]),
                    hovertemplate=f"{STRATEGY_LABELS[strat]}: %{{y:.0%}}<extra></extra>")
    cdf_rows.append(pd.DataFrame({"experiments": ks, "strategy": STRATEGY_LABELS[strat], "probability": p}))
style(fig, height=320, hovermode="x unified", xaxis_title="Experiments run", yaxis_title="Share of runs at target",
      yaxis_tickformat=".0%", xaxis_dtick=1, yaxis_range=[-0.03, 1.03])
show(fig, pd.concat(cdf_rows), key="cdf", caption="The patent's own order is a single run, so its curve is a step.")

# --- when does BO pay off ----------------------------------------------------------------------
st.subheader("When does BO pay off?")
sav, cv = bo_savings(), cv_metrics()
if sav is not None and cv is not None:
    rows = []
    for _, r in sav[sav["mode"] == "scalar"].iterrows():
        cc = campaign(r.campaign)
        q2 = cv[(cv.campaign == r.campaign) & (cv.objective == cc.scalar.key) & (cv.model == "additive+int")]["Q2"]
        rows.append({"campaign": CAMPAIGN_LABELS[r.campaign], "target": cc.scalar.label,
                     "surrogate Q² (LOO)": float(q2.iloc[0]) if len(q2) else np.nan,
                     "BO median": r.bo, "random median": r.random, "saved vs random": 100 * r.saved_vs_random})
    st.dataframe(pd.DataFrame(rows).sort_values("surrogate Q² (LOO)"), hide_index=True, width="stretch",
                 column_config={"saved vs random": st.column_config.NumberColumn(format="%.0f%%"),
                                "surrogate Q² (LOO)": st.column_config.NumberColumn(format="%.2f")})
    st.caption("The gain tracks surrogate skill. On EUV, LWR varies by a few tenths of a nm and the surrogate cannot "
               "rank it from 18 points, so BO is no better than random there.")

with st.expander("Watch one BO run"):
    seed = st.slider("Seed", 0, int(tr[tr.strategy == "bo"].seed.max()), 0)
    run = tr[(tr.strategy == "bo") & (tr.seed == seed)].sort_values("step")
    tab = c.table.reset_index(drop=True)
    cols = [o.key for o in c.objectives] + ([c.scalar.key] if c.scalar.key not in [o.key for o in c.objectives] else [])
    detail = tab.loc[run.picked_index, ["example_label"] + [f.name for f in c.factors if f.name in tab] + cols]
    detail.insert(0, "step", run.step.to_numpy())
    detail["best so far"] = run.value.to_numpy()
    st.dataframe(detail, hide_index=True, width="stretch")
