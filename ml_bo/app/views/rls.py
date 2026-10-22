import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import STATUS, STATUS_LABEL, campaign, gold, marker, page_header, record_compliance, show, status_marker, style, tokens

from neglines.rls import hypervolume, pareto_mask, reference_point

t = tokens()
g = gold()
comp = record_compliance()
page_header("RLS frontier & PFAS tax",
            "Resolution, line roughness and sensitivity trade off against each other. Here is where each patent's "
            "examples sit on that frontier, and how much of it survives once PFAS-flagged components are removed.")
st.info("Z-factor = HP³ × roughness² × dose (Wallow et al., SPIE 2008); lower is better. It is only compared "
        "within a dose family: photon (mJ/cm²) and electron (µC/cm²) doses are never mixed.", icon=":material/info:")

tab_euv, tab_eb, tab_ss = st.tabs(["EUV · TOK (US20230314945A1)", "E-beam · FUJIFILM (US7432034B2)",
                                   "E-beam · Shin-Etsu (US9017923B2)"])

# ---------------------------------------------------------------------------------------- EUV
with tab_euv:
    c = campaign("euv")
    d = c.observed.copy()
    d["pareto"] = pareto_mask(d[["Eop", "LWR"]].to_numpy())
    fig = go.Figure()
    # Z iso-curves: LWR = sqrt(Z / (HP^3 * Eop * 1e-6))
    e = np.linspace(d.Eop.min() - 3, d.Eop.max() + 3, 80)
    for z in [2.4, 2.8, 3.2, 3.6, 4.0, 4.4]:
        lw = np.sqrt(z / (16 ** 3 * e * 1e-6))
        fig.add_scatter(x=e, y=lw, mode="lines", line=dict(color=t["grid"], width=1), hoverinfo="skip",
                        showlegend=False)
        fig.add_annotation(x=e[-1], y=lw[-1], text=f"Z {z}", showarrow=False, xanchor="left",
                           font=dict(color=t["muted"], size=11))
    front = d[d.pareto].sort_values("Eop")
    fig.add_scatter(x=front.Eop, y=front.LWR, mode="lines", line=dict(color=t["s1"], width=2, shape="hv"),
                    name="Pareto front", hoverinfo="skip")
    for is_comp, grp in d.groupby("is_comparative"):
        fig.add_scatter(x=grp.Eop, y=grp.LWR, mode="markers", name="Comparative example" if is_comp else "Example",
                        marker=marker(t["s2"] if is_comp else t["s1"], 11, "x" if is_comp else "circle"),
                        customdata=grp[["example_label", "resin", "pag", "crosslinker", "quencher", "Z"]],
                        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]} · "
                                      "%{customdata[3]} · %{customdata[4]}<br>Eop %{x} mJ/cm² · LWR %{y} nm"
                                      "<br>Z %{customdata[5]:.2f}<extra></extra>")
    for _, r in front.iterrows():
        fig.add_annotation(x=r.Eop, y=r.LWR, text=r.example_label.replace("Example ", "Ex "), showarrow=False,
                           yshift=-14, font=dict(color=t["ink2"], size=11))
    style(fig, height=440, xaxis_title="Eop (mJ/cm²), lower = more sensitive", yaxis_title="LWR (nm)")
    st.markdown(f"**{int(d.pareto.sum())} of {len(d)} resolved examples are Pareto-optimal.** One more "
                "(Comparative Example 1, resin A-7) never resolved.")
    show(fig, d[["example_label", "resin", "pag", "crosslinker", "quencher", "Eop", "LWR", "Z", "pareto"]], key="euv_rls")
    n_flag = int(comp.loc[d.record_id, "pfas_pag"].sum())
    st.error(f"PFAS tax for this patent: {n_flag} of {len(d)} examples use a PFAS-flagged PAG (B-1 to B-7, per "
             "the extraction QC sheet). Removing them leaves no frontier at all.", icon=":material/block:")

# ---------------------------------------------------------------------------------------- FUJIFILM
with tab_eb:
    c = campaign("ebeam")
    d = c.observed.copy()
    d = d.join(comp[["pfas_pag", "pag_unverified"]], on="record_id")
    objs = ["LER", "sensitivity", "resolution"]
    Y = d[objs].to_numpy()
    ref = reference_point(Y)
    d["pareto"] = pareto_mask(Y)
    d["pag_status"] = np.where(d.pfas_pag, "block", np.where(d.pag_unverified, "unverified", "clear"))
    hv_all = hypervolume(Y, ref)
    hv_nopag = hypervolume(Y[~d.pfas_pag.to_numpy()], ref)
    m1, m2, m3 = st.columns(3)
    m1.metric("Hypervolume kept without PFAS PAGs", f"{hv_nopag / hv_all:.0%}", border=True,
              help="3-objective hypervolume (LER, sensitivity, resolution) of the examples whose PAG is not "
                   "flagged, relative to all examples. Unflagged PAGs are unverified, not confirmed PFAS-free.")
    m2.metric("Records with a PFAS-flagged PAG", f"{int(d.pfas_pag.sum())} / {len(d)}", border=True)
    m3.metric("Records with a fluorosurfactant", f"{len(d)} / {len(d)}", border=True,
              help="Megafac F176 (W-1) is in every formulation. It is the easier swap: see WO2004107052A1 in "
                   "the anion map page.")
    fig = go.Figure()
    for sev in ["block", "unverified"]:
        grp = d[d.pag_status == sev]
        if grp.empty:
            continue
        fig.add_scatter(x=grp.sensitivity, y=grp.LER, mode="markers", name=f"PAG: {STATUS_LABEL[sev]}",
                        marker=status_marker(sev, 12),
                        customdata=grp[["example_label", "pag", "resolution", "Z", "xl_families"]],
                        hovertemplate="<b>%{customdata[0]}</b><br>PAG %{customdata[1]}<br>sensitivity %{x} µC/cm² · "
                                      "LER %{y} nm<br>resolution %{customdata[2]:.0f} nm · Z %{customdata[3]:.0f}"
                                      "<br>crosslinker families: %{customdata[4]:.0f}<extra></extra>")
    for _, r in d[d.pareto | d.is_comparative].iterrows():
        fig.add_annotation(x=r.sensitivity, y=r.LER, text=r.example_label.replace("Comparative Example", "CEx").replace(
            "Example ", "Ex "), showarrow=False, yshift=14, font=dict(color=t["ink2"], size=11))
    style(fig, height=440, xaxis_title="Sensitivity (µC/cm²), lower = faster", yaxis_title="LER (nm)")
    show(fig, d[["example_label", "pag", "pag_status", "sensitivity", "LER", "resolution", "Z", "pareto"]], key="eb_rls",
         caption="Both comparative examples use a single crosslinker family and sit far above the examples on LER. "
                 "The PAG they share (I-1) is flagged, but so is the best-LER example: the flag does not explain the gap.")

# ---------------------------------------------------------------------------------------- Shin-Etsu
with tab_ss:
    ids = g.records.loc[(g.records.doc_id == "US9017923B2") & (g.records.exposure_family == "e-beam"), "record_id"]
    r = g.results[g.results.record_id.isin(ids)]
    w = r.pivot_table(index="record_id", columns="metric", values="value_num", aggfunc="first")
    w = w.join(g.records.set_index("record_id")[["example_label", "is_comparative"]])
    w["Z"] = w.resolution_min_cd_nm ** 3 * w.lwr_3sigma_nm ** 2 * w.sensitivity_esize * 1e-6
    fig = go.Figure()
    for is_comp, grp in w.groupby("is_comparative"):
        fig.add_scatter(x=grp.sensitivity_esize, y=grp.lwr_3sigma_nm, mode="markers+text",
                        name="Comparative example" if is_comp else "Example",
                        text=grp.example_label.str.replace("Comparative Example", "CEx").str.replace("Example ", "Ex "),
                        textposition="top center", textfont=dict(color=t["ink2"], size=11),
                        marker=marker(t["s2"] if is_comp else t["s1"], 11, "x" if is_comp else "circle"),
                        customdata=grp[["resolution_min_cd_nm", "Z"]],
                        hovertemplate="sensitivity %{x} µC/cm² · LWR %{y} nm<br>resolution %{customdata[0]:.0f} nm"
                                      " · Z %{customdata[1]:.0f}<extra></extra>")
    style(fig, height=380, xaxis_title="Sensitivity (µC/cm²)", yaxis_title="LWR (nm)")
    show(fig, w.reset_index(drop=True), key="ss_rls",
         caption="Eight records is too few for a campaign. Example 1-6 has no separate PAG listed and still has the "
                 "best LWR, which suggests a polymer-bound acid generator. Its structure is worth extracting.")
