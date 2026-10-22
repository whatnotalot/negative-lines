import numpy as np
import pandas as pd
import streamlit as st

from ui import bo_savings, campaign, cv_metrics, gold, page_header, record_compliance

from neglines.data import dataset_stats

g = gold()
stats = dataset_stats(g)
comp = record_compliance().join(g.records.set_index("record_id")[["doc_id"]])

page_header("Negative Lines · ML & Bayesian optimization",
            "Surrogate models and compliance-aware Bayesian optimization on the team's reconciled gold set "
            "of negative-tone photoresist patents.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Patents", stats["n_docs"], border=True)
c2.metric("Formulation records", stats["n_records"], border=True)
c3.metric("Comparative examples", stats["n_comparative"], border=True,
          help="The 'negative lines': the only records where the source reports a failure.")
c4.metric("Metric series that vary", f"{stats['n_informative_series']} / {stats['n_metric_series']}",
          border=True, help="A series is one metric within one patent. Constant series carry no signal.")

st.subheader("What the data says")

pos_share = 1 - stats["n_comparative"] / stats["n_records"]
cv = cv_metrics()
sav = bo_savings()


def q2(camp, obj, model):
    if cv is None:
        return np.nan
    r = cv[(cv.campaign == camp) & (cv.objective == obj) & (cv.model == model)]
    return float(r["Q2"].iloc[0]) if len(r) else np.nan


def med(camp, mode, strat):
    if sav is None:
        return np.nan
    r = sav[(sav.campaign == camp) & (sav["mode"] == mode)]
    return float(r[strat].iloc[0]) if len(r) else np.nan


euv_pfas = int(comp.loc[comp.doc_id == "US20230314945A1", "pfas_pag"].sum())
euv_n = int((comp.doc_id == "US20230314945A1").sum())
fuji_surf = int(comp.loc[comp.doc_id == "US7432034B2", "summary"].str.contains("Megafac").sum())
fuji_n = int((comp.doc_id == "US7432034B2").sum())
wo = g.components.merge(g.records[["record_id", "doc_id"]], on="record_id")
wo = wo[(wo.doc_id == "WO2004107052A1") & (wo.role == "surfactant")]
n_silicone = int(wo["name"].str.contains("BYK", case=False).sum())
n_fluoro = len(wo) - n_silicone

findings = [
    ("Patents only publish their wins",
     f"{pos_share:.0%} of records are positive examples and {stats['n_metric_series'] - stats['n_informative_series']} "
     f"of {stats['n_metric_series']} metric series never vary. The {stats['n_comparative']} comparative examples carry "
     "most of the information, so every model here keeps them.", "views/atlas.py", "Open the atlas"),
    ("Structure-aware kernels beat the default GP",
     f"On FUJIFILM e-beam LER, an additive GP reaches leave-one-out Q² = {q2('ebeam', 'LER', 'additive+int'):.2f} "
     f"against {q2('ebeam', 'LER', 'ard'):.2f} for a standard ARD GP and {q2('ebeam', 'LER', 'rf'):.2f} for a random "
     "forest. Its largest relevance weight is on mixing two crosslinker families, which is the patent's own claim.",
     "views/surrogate.py", "Open the surrogate lab"),
    ("BO pays off where the surrogate is skillful",
     f"Replaying each patent's example table, BO reaches the best SU-8 condition in a median of {med('su8', 'scalar', 'bo'):.0f} "
     f"experiments against {med('su8', 'scalar', 'random'):.0f} at random, and the best e-beam Z-factor in "
     f"{med('ebeam', 'scalar', 'bo'):.0f} against {med('ebeam', 'scalar', 'random'):.0f}. On EUV, where LWR is not "
     f"predictable from 18 points, it gives no gain ({med('euv', 'scalar', 'bo'):.0f} vs {med('euv', 'scalar', 'random'):.0f}).",
     "views/replay.py", "Open the BO replay"),
    ("PFAS sits exactly where the performance is",
     f"{euv_pfas} of {euv_n} EUV records use a PFAS-flagged PAG, and {fuji_surf} of {fuji_n} FUJIFILM e-beam records "
     "contain a fluorosurfactant (Megafac F176) that the QC sheet did not flag. A PFAS-free EUV design in this "
     "dataset's chemical space is empty: that is a data gap, not a design.", "views/rls.py", "Open the RLS frontier"),
    ("The data already holds one substitution result",
     f"In WO2004107052A1, {n_silicone} slit-coating embodiments use silicone (BYK) surfactants and {n_fluoro} use "
     "fluorosurfactants, and every one is rated good. For PAG anions there is no such evidence. The best "
     "fluorine-free sulfonate reaches about a third of nonaflate's electron-withdrawing pull.",
     "views/anions.py", "Open the anion map"),
]
cols = st.columns(2)
for i, (title, body, page, link) in enumerate(findings):
    with cols[i % 2].container(border=True):
        st.markdown(f"**{title}**")
        st.write(body)
        st.page_link(page, label=link, icon=":material/arrow_forward:")

st.subheader("How this plugs into the team pipeline")
st.markdown(
    """
| Stage | Owner | This module |
|---|---|---|
| Extraction agent → gold set | Data & extraction | `neglines.data` loads the reconciled workbook, normalizes units and flags issues |
| Surrogate model | **ML & BO** | `neglines.gp`: additive GPs per campaign, leave-one-out validated |
| Design agent | **ML & BO** | `neglines.bo`: replay benchmark and qLogNEHVI batch proposals over each patent's design space |
| Compliance agent | Compliance | `neglines.compliance.Screener`: any object with `screen(components, doc_id)` can replace the default rules |
| Orchestrator report | Integration | The Design studio exports a ranked brief with citations and compliance rationale |
"""
)
st.caption("Compliance output is a screening aid, not legal advice. Verify against current official lists and SDS.")
