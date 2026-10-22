import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import STATUS, STATUS_LABEL, campaign, gold, page_header, record_compliance, show, style, tokens

from neglines.gaps import extraction_worklist, pag_states

t = tokens()
g = gold()
comp = record_compliance()
page_header("Data gaps & what to mine next",
            "What the models cannot answer yet, turned into an extraction worklist for the extraction agent.")


def outcome_family(metric: str, written: str) -> str:
    w = (written or "").lower()
    if metric == "sensitivity_esize":
        return "Sensitivity"
    if metric == "resolution_min_cd_nm":
        return "Resolution"
    if metric in ("ler_3sigma_nm", "lwr_3sigma_nm"):
        return "Roughness"
    if metric == "adhesion":
        return "Adhesion"
    if metric == "profile":
        return "Profile"
    if "crack" in w or "bow" in w:
        return "Cracking / stress"
    if "etch" in w:
        return "Etch"
    if any(k in w for k in ("thickness", "uniform", "u %", "viscosity", "coating", "film forming")):
        return "Coating"
    return "Other"


res = g.results.merge(g.records[["record_id", "doc_id", "exposure_family"]], on="record_id")
res["family"] = [outcome_family(m, w) for m, w in zip(res.metric, res.metric_as_written)]
has = res[res.value_num.notna() | res.outcome_class.notna()].copy()
has["key"] = has.value_num.astype(str).where(has.value_num.notna(), has.outcome_class)
var = has.groupby(["doc_id", "metric_as_written"])["key"].transform("nunique") > 1
inf = has[var]
fams = ["EUV", "e-beam", "X-ray", "UV", "visible", "none (coating only)"]
cols = ["Sensitivity", "Resolution", "Roughness", "Profile", "Adhesion", "Cracking / stress", "Coating", "Etch"]
mat = inf.groupby(["exposure_family", "family"])["record_id"].nunique().unstack(fill_value=0)
mat = mat.reindex(index=[f for f in fams if f in g.records.exposure_family.unique()], columns=cols, fill_value=0)

st.subheader("Records with an informative result, by exposure and outcome")
seq = t["seq"]
fig = go.Figure(go.Heatmap(
    z=mat.values, x=mat.columns, y=mat.index, colorscale=[[0, "rgba(0,0,0,0)"], [1e-9, seq[0]], [0.35, seq[1]],
                                                          [0.7, seq[2]], [1, seq[3]]],
    text=mat.values, texttemplate="%{text}", textfont=dict(size=13), xgap=2, ygap=2, showscale=False,
    hovertemplate="%{y} · %{x}: %{z} records<extra></extra>"))
style(fig, height=320, legend=False)
fig.update_xaxes(showgrid=False, side="top")
fig.update_yaxes(showgrid=False, autorange="reversed")
show(fig, mat.reset_index(), key="cov",
     caption="An informative result varies across the patent's examples. Empty cells are questions no model "
             "trained on this set can answer: there is no EUV adhesion or profile data, and no process sweep anywhere.")

# --- PAG status -------------------------------------------------------------------------------------
st.subheader("PAG compliance coverage by exposure family")
r = pag_states(g, comp)
cnt = r[r.exposure_family.isin(["EUV", "e-beam", "X-ray", "UV", "visible"])].groupby(
    ["exposure_family", "pag_state"]).size().unstack(fill_value=0)
fig = go.Figure()
for state in ["block", "watch", "unverified", "clear", "no PAG listed"]:
    if state not in cnt:
        continue
    color = STATUS.get(state, t["grid"])
    fig.add_bar(y=cnt.index, x=cnt[state], orientation="h", name=STATUS_LABEL.get(state, "– no PAG listed"),
                marker=dict(color=color, cornerradius=4, line=dict(width=2, color=t["surface"])),
                hovertemplate="%{y}: %{x} records<extra>" + state + "</extra>")
style(fig, height=260, barmode="stack", bargap=0.35, xaxis_title="Records")
show(fig, cnt.reset_index(), key="pagcov",
     caption="No exposure family has a single high-performance record with a PAG verified to be PFAS-free. "
             "'Clear' records come from UV and visible patents that report no sensitivity or LER. 'Watch' is the "
             "SU-8 antimonate PAG: not PFAS, but an antimony compound.")

# --- worklist -----------------------------------------------------------------------------------------
st.subheader("Extraction worklist")
work = extraction_worklist(g, comp)
cols = st.columns(2)
for i, w in enumerate(work.itertuples()):
    with cols[i % 2].container(border=True):
        st.markdown(f"**P{w.priority} · {w.gap}**")
        st.caption(w.evidence)
        st.markdown(f"Extract: {w.extract}")
        st.code(w.query, language=None, wrap_lines=True)
st.download_button("Worklist (.csv)", work.to_csv(index=False), file_name="extraction_worklist.csv",
                   icon=":material/download:")


# --- most informative experiments --------------------------------------------------------------------
@st.cache_data(show_spinner="Scoring candidate uncertainty…")
def uncertainty(key: str) -> pd.DataFrame:
    from neglines.bo import _known_failure_levels, fit_objectives, to_target
    from neglines.gp import predict
    c = campaign(key)
    cand = c.candidates()
    for name, levels in _known_failure_levels(c).items():
        cand = cand[~cand[name].isin(levels)]
    impute = {c.scalar.key: np.nanmin(to_target(c, c.scalar.key, c.observed[c.scalar.key]))} if c.table.failed.any() else None
    models, _ = fit_objectives(c, c.table if impute else c.observed, [c.scalar.key], impute=impute)
    _, sd = predict(models[0], c.encode(cand))
    return cand.assign(posterior_sd=sd).reset_index(drop=True)


st.subheader("Where the surrogate knows least")
key = st.segmented_control("Campaign", ["euv", "ebeam", "su8"], default="euv",
                           format_func={"euv": "EUV", "ebeam": "E-beam", "su8": "SU-8"}.get, key="unc")
cu = campaign(key)
u = uncertainty(key)
rows = []
for f in cu.factors:
    if f.name not in u:
        continue
    for lvl, grp in u.groupby(f.name):
        label = f"{f.label} = {lvl:g}" if f.kind == "cont" else f"{f.label} = {lvl}"
        n_obs = int((cu.observed[f.name] == lvl).sum()) if f.kind == "cat" else "n/a (continuous)"
        rows.append({"factor level": label, "mean posterior sd": grp.posterior_sd.mean(), "tested examples": n_obs})
lv = pd.DataFrame(rows).sort_values("mean posterior sd", ascending=False).head(10).iloc[::-1]
fig = go.Figure(go.Bar(y=lv["factor level"], x=lv["mean posterior sd"], orientation="h",
                       marker=dict(color=t["s1"], cornerradius=4), customdata=lv[["tested examples"]],
                       hovertemplate="%{y}<br>mean sd %{x:.3f}<br>tested in %{customdata[0]} examples<extra></extra>"))
style(fig, height=60 + 30 * len(lv), legend=False,
      xaxis_title=f"Mean posterior sd of {cu.scalar.label} (model space) over candidates with this level")
show(fig, lv.iloc[::-1], key="unc_levels",
     caption="Levels tested once or never dominate, as expected for one-factor-at-a-time data. Sources that "
             "report these levels would shrink the surrogate's uncertainty the most. Known-failure levels are excluded.")
with st.expander("Single most uncertain candidates"):
    st.dataframe(u.sort_values("posterior_sd", ascending=False).head(8)[[f.name for f in cu.factors] + ["posterior_sd"]],
                 hide_index=True, width="stretch")
