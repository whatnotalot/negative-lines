import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import gold, marker, page_header, record_compliance, show, style, tokens

from neglines.data import dataset_stats

g = gold()
t = tokens()
page_header("Dataset atlas", "Every record with its source evidence, components, results and reconciliation trail.")

docs = g.documents.set_index("doc_id")
f1, f2, f3 = st.columns([3, 2, 2], vertical_alignment="bottom")
sel_docs = f1.multiselect("Patents", docs.index.tolist(), placeholder="All patents",
                          format_func=lambda d: f"{d} · {docs.loc[d, 'applicant_or_inventor']}")
fams = sorted(g.records["exposure_family"].unique())
sel_fam = f2.multiselect("Exposure family", fams, placeholder="All families")
only_comp = f3.toggle("Comparatives only", help="Show only the examples the source reports as failures or baselines.")

rec = g.records.copy()
if sel_docs:
    rec = rec[rec.doc_id.isin(sel_docs)]
if sel_fam:
    rec = rec[rec.exposure_family.isin(sel_fam)]
if only_comp:
    rec = rec[rec.is_comparative]

# --- where is the signal -----------------------------------------------------------------------
series = dataset_stats(g)["metric_series"]
series["informative"] = (series["n_unique"] > 1) | (series["n_qual_classes"] > 1)
per_doc = series.groupby("doc_id")["informative"].agg(informative="sum", total="size")
per_doc["constant"] = per_doc["total"] - per_doc["informative"]
per_doc = per_doc.loc[[d for d in docs.index if d in per_doc.index]]
if sel_docs:
    per_doc = per_doc.loc[[d for d in sel_docs if d in per_doc.index]]
per_doc = per_doc.sort_values("informative")
fig = go.Figure()
fig.add_bar(y=per_doc.index, x=per_doc["informative"], orientation="h", name="Varies across examples",
            marker=dict(color=t["s1"], cornerradius=4, line=dict(width=2, color=t["surface"])),
            hovertemplate="%{y}<br>%{x} metric series vary<extra></extra>")
fig.add_bar(y=per_doc.index, x=per_doc["constant"], orientation="h", name="Constant (no signal)",
            marker=dict(color=t["grid"], cornerradius=4, line=dict(width=2, color=t["surface"])),
            hovertemplate="%{y}<br>%{x} metric series constant<extra></extra>")
style(fig, height=60 + 34 * len(per_doc), barmode="stack", bargap=0.35,
      xaxis_title="Metric series (one metric within one patent)")
st.subheader("Where the signal is")
show(fig, per_doc.reset_index(), key="signal",
     caption="WO2004107052A1 and US20080241753A1 report one value for all their examples, so they cannot train a "
             "regression model. They remain useful for compliance and substitution evidence.")

# --- record browser ----------------------------------------------------------------------------
st.subheader(f"Records ({len(rec)})")
comp = record_compliance()
view = rec[["record_id", "doc_id", "example_label", "is_comparative", "exposure_family", "labeler_confidence"]].merge(
    comp[["worst", "summary"]], left_on="record_id", right_index=True, how="left")
view = view.rename(columns={"worst": "compliance", "summary": "compliance detail"})
event = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                     height=320, column_config={"is_comparative": st.column_config.CheckboxColumn("comparative")})
rows = event.selection.rows if event and event.selection else []
rid = view.iloc[rows[0]]["record_id"] if rows else (view.iloc[0]["record_id"] if len(view) else None)

if rid:
    r = g.records.set_index("record_id").loc[rid]
    st.markdown(f"#### {rid}")
    a, b = st.columns([3, 2])
    with a:
        st.markdown(f"**{r['example_label']}** · {docs.loc[r['doc_id'], 'title']}")
        st.markdown(f"Location in source: `{r['location']}`")
        st.markdown("Evidence snippet")
        st.code(r["evidence_snippet"], language=None, wrap_lines=True)
        if isinstance(r["labeler_note"], str):
            st.caption(f"Labeler note: {r['labeler_note']}")
    with b:
        proc = {k: r[k] for k in ["exposure_family", "exposure_tool", "dose", "dose_unit", "film_thickness",
                                  "film_thickness_unit", "softbake_temp", "peb_temp", "developer_name"]
                if isinstance(r[k], str) or pd.notna(r[k])}
        st.dataframe(pd.DataFrame(proc.items(), columns=["process field", "value"]), hide_index=True,
                     width="stretch")
    c = g.components[g.components.record_id == rid][["component_no", "role", "name", "amount_raw", "amount_unit",
                                                      "amount_basis", "amount_phr", "labeler_confidence"]]
    res = g.results[g.results.record_id == rid][["metric", "metric_as_written", "value", "unit", "value_num",
                                                 "value_qualitative", "outcome_class"]]
    tc, tr, tq = st.tabs([f"Components ({len(c)})", f"Results ({len(res)})", "Reconciliation & QC"])
    tc.dataframe(c, hide_index=True, width="stretch")
    tr.dataframe(res, hide_index=True, width="stretch")
    with tq:
        recon = g.reconciliation[g.reconciliation.record_id == rid]
        if len(recon):
            st.dataframe(recon, hide_index=True, width="stretch")
        else:
            st.caption("No reconciliation items for this record.")
        qc = g.qc[g.qc.doc_id == r["doc_id"]]
        if len(qc):
            st.markdown("QC issues for this patent")
            st.dataframe(qc, hide_index=True, width="stretch")

# --- data quality --------------------------------------------------------------------------------
st.subheader("Data quality checks")
st.caption("Computed by the loader on every run. Send these back to the extraction team.")
st.dataframe(pd.DataFrame(g.issues), hide_index=True, width="stretch")
causes = g.reconciliation["cause"].value_counts().sort_values()
fig = go.Figure(go.Bar(y=causes.index, x=causes.values, orientation="h",
                       marker=dict(color=t["s1"], cornerradius=4), text=causes.values, textposition="outside",
                       textfont=dict(color=t["ink2"]), hovertemplate="%{y}: %{x} items<extra></extra>"))
style(fig, height=300, legend=False, xaxis_title="Reconciliation items (labeler A vs B disagreements)")
show(fig, causes.rename_axis("cause").reset_index(name="items"), key="causes")
