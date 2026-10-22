import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import STATUS, STATUS_LABEL, campaign, gold, marker, page_header, record_compliance, rules_text, \
    screener_for, show, status_marker, style, tokens

from neglines.bo import best_observed

t = tokens()
g = gold()
comp = record_compliance()
SWAP = {'Megafac F176 ("W-1")': "BYK-333 (polyether-modified PDMS)"}
FLAG_III1 = "role,name_pattern,rule,severity,rationale,source,confidence,substitutes\n" \
            "pag,^III-1$,OECD_PFAS,block,Simulated compliance-agent finding: fluorinated anion,compliance_agent,high," \
            "camphorsulfonate onium salt\n"

page_header("Demo tour: a PFAS-reduced e-beam resist",
            "Five steps from 'the best resist in the data is not compliant' to a ranked, cited proposal, and an "
            "honest account of where the data runs out.")


@st.cache_data(show_spinner="Running compliance-aware BO…", max_entries=8, persist="disk")
def batch(key, policy, swap, rules):
    from neglines.bo import propose
    return propose(campaign(key), mode="mo", q=3, exclude_blocked=policy == "exclude",
                   swaps=SWAP if swap else None, screener=screener_for(rules))


c = campaign("ebeam")
obs = c.observed.join(comp[["pfas_pag", "pag_unverified", "summary"]], on="record_id")
obs["pag_status"] = np.where(obs.pfas_pag, "block", "unverified")
best_z = best_observed(c, "Z")
best_row = obs.loc[obs.Z.idxmin()]

# ------------------------------------------------------------------------------------------- step 1
st.subheader("1 · The best e-beam resist in the data is not PFAS-free")
a, b, d = st.columns(3)
a.metric("Best tested Z-factor", f"{best_z:.0f}", help="×10⁻⁸ µC·nm³, lower is better", border=True)
b.metric("Its PAG", best_row.pag, help="Structure not in the dataset: PFAS status unverified", border=True)
d.metric("E-beam records with fluorosurfactant", f"{len(obs)} / {len(obs)}", border=True,
         help="Megafac F176 (W-1) is in every formulation.")
st.markdown(f"**{best_row.example_label}** of US7432034B2 has the lowest Z-factor (source: {best_row.location}). Like every "
            "example in this patent it contains **Megafac F176, a fluorosurfactant**. Its best-LER sibling, "
            "Example 1, also uses **I-1, a perfluorobutanesulfonate PAG**.")

# ------------------------------------------------------------------------------------------- step 2
st.subheader("2 · One PFAS source already has a tested substitute")
wo = g.components.merge(g.records[["record_id", "doc_id"]], on="record_id")
wo = wo[(wo.doc_id == "WO2004107052A1") & (wo.role == "surfactant")]
wo["family"] = np.where(wo.name.str.contains("BYK", case=False), "silicone (BYK-3xx)", "fluorinated (Megaface / Fluorad)")
res = g.results[g.results.record_id.isin(wo.record_id)].merge(wo[["record_id", "family"]], on="record_id")
ev = res.groupby("family").agg(records=("record_id", "nunique"),
                               good=("outcome_class", lambda s: int((s == "positive").sum())),
                               rated=("outcome_class", lambda s: int(s.notna().sum())))
cols = st.columns(len(ev))
for col, (fam, r) in zip(cols, ev.iterrows()):
    col.metric(f"{fam} surfactant", f"{r.records} embodiments", f"{r.good}/{r.rated} coating ratings good",
               delta_color="off", delta_arrow="off", border=True)
st.caption("WO2004107052A1 (ADMS Technology) varies the surfactant in embodiments 20 to 51 of a slit-coated negative "
           "resist. That is evidence for the swap in coating quality, not yet in lithographic performance.")

# ------------------------------------------------------------------------------------------- step 3
st.subheader("3 · BO designs around the PAG, with the surfactant swapped")
flag_iii1 = st.toggle("Simulate the compliance agent flagging PAG III-1 as PFAS", value=False,
                      help="Adds one rule, as if the team's compliance agent returned it. BO re-plans immediately.")
rules = rules_text()
if flag_iii1:
    import io
    frames = [pd.read_csv(io.StringIO(FLAG_III1))] + ([pd.read_csv(io.StringIO(rules))] if rules else [])
    rules = pd.concat(frames, ignore_index=True).to_csv(index=False)
p = batch("ebeam", "exclude", True, rules)
top = p.batch.iloc[0]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Proposal #1 Z-factor (pred.)", f"{top.Z_pred:.0f}", f"{top.Z_pred - best_z:+.0f} vs best tested",
          delta_color="inverse", border=True)
m2.metric("LER (pred.)", f"{top.LER_pred:.2f} nm", f"95%: {top.LER_lo:.2f}–{top.LER_hi:.2f}", delta_color="off", delta_arrow="off", border=True)
m3.metric("Sensitivity (pred.)", f"{top.sensitivity_pred:.2f} µC/cm²",
          f"95%: {top.sensitivity_lo:.2f}–{top.sensitivity_hi:.2f}", delta_color="off", delta_arrow="off", border=True)
m4.metric("Resolution (pred.)", f"{top.resolution_pred:.0f} nm",
          f"95%: {top.resolution_lo:.0f}–{top.resolution_hi:.0f}", delta_color="off", delta_arrow="off", border=True)
st.markdown(f"**Proposal #1:** PAG **{top.pag}** at {top.pag_phr:g} phr, MM-type crosslinker {top.xl_MM_phr:g} phr + "
            f"CL-type {top.xl_CL_phr:g} phr, quencher {top.quencher} at {top.quencher_phr:g} phr, silicone surfactant. "
            f"Closest tested example: {top.nearest_record}. Compliance: {top['compliance']}.")

fig = go.Figure()
tested = obs.sort_values("Z").head(10)
for sev in ["block", "unverified"]:
    grp = tested[tested.pag_status == sev]
    fig.add_scatter(x=grp.Z, y=grp.example_label, mode="markers", name=f"Tested, PAG {STATUS_LABEL[sev]}",
                    marker=status_marker(sev, 12), customdata=grp[["pag"]],
                    hovertemplate="%{y} · PAG %{customdata[0]}<br>Z %{x:.0f}<extra>tested (fluorosurfactant)</extra>")
lab = [f"Proposal #{r}" for r in p.batch["rank"]]
fig.add_scatter(x=p.batch.Z_pred, y=lab, mode="markers", name="Proposed (silicone surfactant)",
                marker=marker(t["s2"], 14, "diamond"), customdata=p.batch[["pag"]],
                hovertemplate="%{y} · PAG %{customdata[0]}<br>predicted Z %{x:.0f}<extra></extra>")
fig.add_vline(x=best_z, line=dict(color=t["axis"], width=1))
style(fig, height=440, xaxis_title="Z-factor (×10⁻⁸ µC·nm³, log scale), lower is better", xaxis_type="log")
fig.update_yaxes(categoryorder="array", categoryarray=list(tested.example_label[::-1]) + lab[::-1], showgrid=False)
show(fig, p.batch[["rank", "pag", "pag_phr", "xl_MM_phr", "xl_CL_phr", "quencher", "LER_pred", "sensitivity_pred",
                   "resolution_pred", "Z_pred", "compliance", "nearest_record"]], key="demo_z",
     caption="Proposal Z-factors are computed from predicted medians; the hairline is the best tested example. The batch spreads across the trade-off rather than repeating #1, so a later proposal can buy sensitivity at the cost of LER.")

# ------------------------------------------------------------------------------------------- step 4
st.subheader("4 · What it takes to make it real")
unv = c.screen(pd.DataFrame([top]), SWAP, screener_for(rules))[0].unverified
st.markdown(
    f"- **Verify the structures** of {', '.join(unv) or 'the proposed components'}: the dataset has codes, not "
    "SMILES. This is the top item on the extraction worklist.\n"
    "- **Confirm the surfactant swap** in a lithographic test, not only coating: run proposal #1 with BYK-333 "
    f"next to {top.nearest_record} as the control.\n"
    "- **Let the compliance agent decide**: toggle the switch above to see BO re-plan when one PAG is flagged.")

# ------------------------------------------------------------------------------------------- step 5
st.subheader("5 · Where the data runs out: EUV")
pe = batch("euv", "exclude", False, rules_text())
n_cand = len(pe.candidates)
st.error(f"0 of {n_cand:,} EUV candidate formulations pass the PFAS screen: every PAG TOK tested (B-1 to B-7) carries a "
         "fluorinated anion. No optimizer can design around missing chemistry, so the agent turns this into an "
         "extraction query and a shortlist of fluorine-free anions to test.", icon=":material/block:")
l1, l2, l3 = st.columns(3)
l1.page_link("views/gaps.py", label="Extraction worklist", icon=":material/travel_explore:")
l2.page_link("views/anions.py", label="Fluorine-free anion shortlist", icon=":material/hub:")
l3.page_link("views/agent.py", label="Ask the design agent", icon=":material/smart_toy:")

with st.expander("Presenter notes (about 3 minutes)"):
    st.markdown("""
1. **Hook (20 s).** "Patents only publish wins, and the best-performing resists in our open dataset are the ones
   regulators are coming for." Point at step 1.
2. **Evidence (30 s).** Step 2: one PFAS source, the fluorosurfactant, already has a tested silicone substitute in
   another patent in our own dataset.
3. **Design (60 s).** Step 3: compliance-aware BO proposes a formulation predicted to beat the best tested example,
   with 95% intervals and a citation. Flip the toggle: the compliance agent flags a PAG and BO re-plans in seconds.
4. **Honesty (30 s).** Step 5: on EUV the PFAS-free design space is empty. We say so, and the agent turns it into
   an extraction query. Mention the BO replay: BO saves experiments where the surrogate is skillful, and we show
   where it is not.
5. **Close (20 s).** Everything is open: the dataset, the code, and the agent's transcript with every tool call.
""")
