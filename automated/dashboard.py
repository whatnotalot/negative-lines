"""
Automated Engine dashboard (UI layer).

Shared by `automated/app.py` (standalone) and the root `app.py` portal so both
render the same interface. Call `render_automated_dashboard()` after
`st.set_page_config(...)`.
"""

import os
import sys
import json

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dataset import load_ebeam_dataset  # noqa: E402
from surrogate import GaussianProcessSurrogate  # noqa: E402
from optimizer import vectorize_candidate, run_retrospective_simulation  # noqa: E402
from orchestrator import FormulationOrchestrator  # noqa: E402


# -----------------------------------------------------------------------------
# Design tokens
# -----------------------------------------------------------------------------
NAVY = "#0B1F3A"
PRIMARY = "#1D4ED8"
ACCENT = "#0EA5E9"
SLATE_900 = "#0F172A"
SLATE_500 = "#64748B"
SLATE_300 = "#CBD5E1"
SLATE_200 = "#E2E8F0"
GREEN = "#15803D"
RED = "#B91C1C"
AMBER = "#B45309"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, button, input, textarea, select {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
.stApp {{ background: #F6F8FB; }}
#MainMenu, footer {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1320px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {SLATE_200}; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
.nl-side-brand {{ font-weight: 700; font-size: 1.02rem; color: {SLATE_900}; letter-spacing: -0.01em; }}
.nl-side-sub {{ font-size: 0.78rem; color: {SLATE_500}; margin-bottom: 0.6rem; }}
.nl-side-h {{ font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
             color: {SLATE_500}; margin: 1.1rem 0 0.35rem 0; }}
.nl-kv {{ display: flex; justify-content: space-between; font-size: 0.8rem; padding: 0.28rem 0;
          border-bottom: 1px dashed {SLATE_200}; color: {SLATE_900}; }}
.nl-kv span:first-child {{ color: {SLATE_500}; }}

/* Hero */
.nl-hero {{ background: linear-gradient(120deg, {NAVY} 0%, #12305C 55%, #1E3A8A 100%);
            border-radius: 14px; padding: 1.6rem 1.9rem; color: #F8FAFC; margin-bottom: 1.1rem;
            box-shadow: 0 6px 24px rgba(11,31,58,0.18); }}
.nl-eyebrow {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
               color: #93C5FD; }}
.nl-hero-title {{ font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; margin: 0.25rem 0 0.3rem 0; }}
.nl-hero-sub {{ font-size: 0.95rem; color: #CBD5E1; max-width: 860px; }}
.nl-tags {{ margin-top: 0.9rem; display: flex; flex-wrap: wrap; gap: 0.45rem; }}
.nl-tag {{ font-size: 0.72rem; font-weight: 500; padding: 0.22rem 0.65rem; border-radius: 999px;
           background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18); color: #E2E8F0; }}

/* KPI strip */
.nl-kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.85rem; margin-bottom: 1.2rem; }}
.nl-kpi {{ background: #FFFFFF; border: 1px solid {SLATE_200}; border-radius: 12px; padding: 0.95rem 1.1rem; }}
.nl-kpi-label {{ font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {SLATE_500}; }}
.nl-kpi-value {{ font-family: 'JetBrains Mono', monospace; font-size: 1.55rem; font-weight: 500; color: {SLATE_900};
                 margin-top: 0.2rem; letter-spacing: -0.02em; }}
.nl-kpi-unit {{ font-size: 0.85rem; color: {SLATE_500}; margin-left: 0.2rem; }}
.nl-kpi-sub {{ font-size: 0.76rem; color: {SLATE_500}; margin-top: 0.1rem; }}

/* Sections & cards */
.nl-h2 {{ font-size: 1.08rem; font-weight: 650; color: {SLATE_900}; letter-spacing: -0.01em; margin: 0.4rem 0 0.1rem 0; }}
.nl-h2-sub {{ font-size: 0.85rem; color: {SLATE_500}; margin-bottom: 0.9rem; }}
.nl-card {{ background: #FFFFFF; border: 1px solid {SLATE_200}; border-radius: 12px; padding: 1.15rem 1.35rem;
            margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }}
.nl-card-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem; }}
.nl-card-title {{ font-weight: 650; font-size: 1rem; color: {SLATE_900}; }}
.nl-card-title small {{ font-weight: 500; color: {SLATE_500}; margin-left: 0.5rem; font-size: 0.8rem; }}
.nl-metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.7rem; margin-bottom: 0.9rem; }}
.nl-metric {{ background: #F8FAFC; border: 1px solid #EEF2F7; border-radius: 10px; padding: 0.65rem 0.8rem; }}
.nl-metric-label {{ font-size: 0.66rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: {SLATE_500}; }}
.nl-metric-value {{ font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; color: {SLATE_900}; margin-top: 0.15rem; }}
.nl-metric-sub {{ font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; color: {SLATE_500}; }}

.nl-pill {{ display: inline-block; padding: 0.18rem 0.65rem; border-radius: 999px; font-size: 0.7rem;
            font-weight: 700; letter-spacing: 0.04em; }}
.nl-pill-pass {{ background: #DCFCE7; color: {GREEN}; border: 1px solid #BBF7D0; }}
.nl-pill-flag {{ background: #FEE2E2; color: {RED}; border: 1px solid #FECACA; }}
.nl-pill-warn {{ background: #FEF3C7; color: {AMBER}; border: 1px solid #FDE68A; }}

.nl-note {{ font-size: 0.8rem; color: #334155; background: #F1F5F9; border-left: 3px solid {PRIMARY};
            padding: 0.55rem 0.8rem; border-radius: 0 8px 8px 0; margin: 0.4rem 0 0.8rem 0; }}
.nl-note-warn {{ border-left-color: {AMBER}; background: #FFFBEB; }}

table.nl-table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; }}
table.nl-table th {{ text-align: left; color: {SLATE_500}; font-weight: 700; font-size: 0.66rem; text-transform: uppercase;
                     letter-spacing: 0.07em; border-bottom: 1px solid {SLATE_200}; padding: 0.45rem 0.5rem; }}
table.nl-table td {{ border-bottom: 1px solid #F1F5F9; padding: 0.5rem 0.5rem; color: {SLATE_900}; vertical-align: top; }}
table.nl-table td.num {{ font-family: 'JetBrains Mono', monospace; text-align: right; white-space: nowrap; }}
table.nl-table th.num {{ text-align: right; }}
table.nl-table td.role {{ color: {SLATE_500}; white-space: nowrap; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.25rem; border-bottom: 1px solid {SLATE_200}; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 500; font-size: 0.9rem; padding: 0.6rem 0.9rem; color: {SLATE_500}; }}
.stTabs [aria-selected="true"] {{ color: {PRIMARY}; }}

/* Native widgets */
[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; }}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
    border-radius: 8px; font-weight: 600; }}
.nl-footer {{ font-size: 0.75rem; color: {SLATE_500}; text-align: center; margin-top: 2rem;
              padding-top: 1rem; border-top: 1px solid {SLATE_200}; }}

@media (max-width: 900px) {{
  .nl-kpis, .nl-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
</style>
"""


def _html(markup: str):
    """Render raw HTML (no leading indentation, so Markdown won't treat it as code)."""
    st.markdown("\n".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def _altair_theme():
    return {
        "config": {
            "font": "Inter",
            "background": "#FFFFFF",
            "view": {"stroke": "transparent"},
            "axis": {
                "labelFont": "Inter", "titleFont": "Inter", "labelColor": SLATE_500, "titleColor": "#334155",
                "titleFontWeight": 600, "titleFontSize": 12, "labelFontSize": 11,
                "gridColor": "#EEF2F7", "domainColor": SLATE_300, "tickColor": SLATE_300,
            },
            "legend": {"labelFont": "Inter", "titleFont": "Inter", "labelColor": "#334155", "labelFontSize": 11,
                       "orient": "top", "title": None},
            "title": {"font": "Inter", "fontSize": 13, "fontWeight": 600, "color": SLATE_900, "anchor": "start"},
        }
    }


alt.themes.register("negative_lines", _altair_theme)
alt.themes.enable("negative_lines")


# -----------------------------------------------------------------------------
# Cached back-end calls
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Fitting Gaussian-process surrogate…")
def _orchestrator():
    return FormulationOrchestrator()


@st.cache_data(show_spinner=False)
def _dataset():
    X, y_lwr, y_dose, fnames, df = load_ebeam_dataset()
    return X, y_lwr, y_dose, fnames, df


@st.cache_data(show_spinner="Running leave-one-out cross-validation…")
def _loocv():
    X, y_lwr, y_dose, _, _ = load_ebeam_dataset()
    lwr = GaussianProcessSurrogate().evaluate_leave_one_out(X, y_lwr)
    dose = GaussianProcessSurrogate().evaluate_leave_one_out(X, y_dose)
    return {
        "lwr": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in lwr.items()},
        "dose": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in dose.items()},
    }


@st.cache_data(show_spinner="Simulating Bayesian optimization vs. random search…")
def _simulation(n_trials: int = 25):
    return run_retrospective_simulation(n_trials=n_trials)


@st.cache_data(show_spinner="Searching formulation space…")
def _run_pipeline(target_lwr: float, target_dose: float, pfas_free: bool, n_candidates: int):
    return _orchestrator().run_pipeline(
        target_lwr=target_lwr, target_dose=target_dose, pfas_free=pfas_free, n_candidates=n_candidates
    )


# -----------------------------------------------------------------------------
# Page sections
# -----------------------------------------------------------------------------
def _sidebar(show_brand: bool):
    sb = st.sidebar
    if show_brand:
        sb.markdown(
            '<div class="nl-side-brand">Negative Lines</div>'
            '<div class="nl-side-sub">Automated formulation engine</div>',
            unsafe_allow_html=True,
        )

    with sb.form("nl_spec_form", border=False):
        st.markdown('<div class="nl-side-h">Target specification</div>', unsafe_allow_html=True)
        target_lwr = st.slider("Line-width roughness, 3σ (nm)", 4.0, 7.0, 4.5, 0.1)
        target_dose = st.slider("Sensitivity, E_size (µC/cm²)", 4.5, 7.0, 5.5, 0.1)

        st.markdown('<div class="nl-side-h">Constraints</div>', unsafe_allow_html=True)
        pfas_free = st.toggle("Require PFAS-free PAG", value=True)
        n_candidates = st.select_slider("Candidates to return", options=[1, 2, 3, 4, 5], value=3)

        submitted = st.form_submit_button("Run optimization", type="primary", use_container_width=True)

    sb.markdown('<div class="nl-side-h">Process window (fixed)</div>', unsafe_allow_html=True)
    rows = [
        ("Exposure", "E-beam, 50 keV"),
        ("Substrate", "6-in Si, HMDS"),
        ("Film", "300 nm"),
        ("Soft bake", "120 °C / 90 s"),
        ("PEB", "110 °C / 90 s"),
        ("Develop", "2.38% TMAH / 60 s"),
    ]
    sb.markdown("".join(f'<div class="nl-kv"><span>{k}</span><span>{v}</span></div>' for k, v in rows),
                unsafe_allow_html=True)
    sb.markdown('<div class="nl-side-h">Source</div>', unsafe_allow_html=True)
    sb.caption("Training data: US7432034B2, Examples 1–12 and Comparative Examples 1–2.")

    params = dict(target_lwr=float(target_lwr), target_dose=float(target_dose),
                  pfas_free=bool(pfas_free), n_candidates=int(n_candidates))
    if submitted or "nl_params" not in st.session_state:
        st.session_state["nl_params"] = params
    return st.session_state["nl_params"]


def _hero():
    _html("""
    <div class="nl-hero">
      <div class="nl-eyebrow">Project Negative Lines &middot; Automated Engine</div>
      <div class="nl-hero-title">Negative-Tone Resist Formulation Design</div>
      <div class="nl-hero-sub">Gaussian-process surrogate modelling and Bayesian optimization over a dual-crosslinker
      chemically amplified resist, with every candidate screened for PFAS and restricted solvents before it is ranked.</div>
      <div class="nl-tags">
        <span class="nl-tag">Dataset &middot; US7432034B2</span>
        <span class="nl-tag">50 keV electron beam</span>
        <span class="nl-tag">GP &middot; Matérn 5/2 + white noise</span>
        <span class="nl-tag">Acquisition &middot; Expected Improvement</span>
        <span class="nl-tag">Screening &middot; OECD PFAS / REACH / TSCA</span>
      </div>
    </div>
    """)


def _kpis(df, loocv):
    best = df["ler_3sigma_nm"].min()
    dual = int(df["has_dual_crosslinker"].sum())
    _html(f"""
    <div class="nl-kpis">
      <div class="nl-kpi"><div class="nl-kpi-label">Training records</div>
        <div class="nl-kpi-value">{len(df)}</div>
        <div class="nl-kpi-sub">{dual} dual-crosslinker &middot; {len(df) - dual} single</div></div>
      <div class="nl-kpi"><div class="nl-kpi-label">Best observed LWR</div>
        <div class="nl-kpi-value">{best:.1f}<span class="nl-kpi-unit">nm</span></div>
        <div class="nl-kpi-sub">Range {df['ler_3sigma_nm'].min():.1f}–{df['ler_3sigma_nm'].max():.1f} nm</div></div>
      <div class="nl-kpi"><div class="nl-kpi-label">Surrogate MAE (LOOCV)</div>
        <div class="nl-kpi-value">{loocv['lwr']['mae']:.2f}<span class="nl-kpi-unit">nm</span></div>
        <div class="nl-kpi-sub">LWR &middot; R² {loocv['lwr']['r2']:.2f}</div></div>
      <div class="nl-kpi"><div class="nl-kpi-label">Dose MAE (LOOCV)</div>
        <div class="nl-kpi-value">{loocv['dose']['mae']:.2f}<span class="nl-kpi-unit">µC/cm²</span></div>
        <div class="nl-kpi-sub">Sensitivity &middot; R² {loocv['dose']['r2']:.2f}</div></div>
    </div>
    """)


def _section(title, subtitle=""):
    _html(f'<div class="nl-h2">{title}</div>' + (f'<div class="nl-h2-sub">{subtitle}</div>' if subtitle else ""))


def _tab_recommendations(params):
    results = _run_pipeline(**params)
    cands = results["candidates"]

    _section(
        "Recommended formulations",
        f"Target LWR ≤ {params['target_lwr']:.1f} nm at ≈ {params['target_dose']:.1f} µC/cm²"
        f" &middot; {'PFAS-free PAG required' if params['pfas_free'] else 'PFAS PAG permitted'}"
        f" &middot; ranked by Expected Improvement with a dose-deviation penalty",
    )

    summary = pd.DataFrame([{
        "Candidate": c["candidate_id"],
        "Pred. LWR (nm)": c["predicted_performance"]["ler_3sigma_lwr_nm"],
        "± σ (nm)": c["predicted_performance"]["lwr_uncertainty_nm"],
        "Pred. dose (µC/cm²)": c["predicted_performance"]["sensitivity_dose_uc_cm2"],
        "EI": c["predicted_performance"]["ei_acquisition_score"],
        "Resin (g)": c["formulation_loadings_grams"]["resin_amt_g"],
        "MM (g)": c["formulation_loadings_grams"]["mm_crosslinker_amt_g"],
        "CL (g)": c["formulation_loadings_grams"]["cl_crosslinker_amt_g"],
        "PAG (g)": c["formulation_loadings_grams"]["pag_amt_g"],
        "Quencher (g)": c["formulation_loadings_grams"]["quencher_amt_g"],
        "Compliance": c["compliance"]["status"],
    } for c in cands])
    st.dataframe(
        summary, hide_index=True, use_container_width=True,
        column_config={
            "Pred. LWR (nm)": st.column_config.NumberColumn(format="%.2f"),
            "± σ (nm)": st.column_config.NumberColumn(format="%.2f"),
            "Pred. dose (µC/cm²)": st.column_config.NumberColumn(format="%.1f"),
            "EI": st.column_config.ProgressColumn(format="%.3f", min_value=0.0,
                                                  max_value=float(max(summary["EI"].max(), 1e-6))),
            "Quencher (g)": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    for c in cands:
        perf, load, ratios, comp, chem = (c["predicted_performance"], c["formulation_loadings_grams"],
                                          c["chemical_ratios"], c["compliance"], c["formulation_chemicals"])
        pill = ('<span class="nl-pill nl-pill-pass">COMPLIANT</span>' if comp["status"] == "PASS"
                else '<span class="nl-pill nl-pill-flag">FLAGGED</span>')
        rows = [
            ("Resin", chem["resin"], f"{load['resin_amt_g']:.3f}", "Matrix polymer"),
            ("Crosslinker 1", chem["crosslinker_primary"], f"{load['mm_crosslinker_amt_g']:.3f}",
             f"{ratios['mm_to_total_crosslinker_ratio']:.0%} of crosslinker"),
            ("Crosslinker 2", chem["crosslinker_secondary"], f"{load['cl_crosslinker_amt_g']:.3f}", "Dual system"),
            ("PAG", chem["photoacid_generator"], f"{load['pag_amt_g']:.3f}",
             f"{ratios['pag_to_resin_percent']:.1f}% on resin"),
            ("Quencher", chem["basic_quencher"], f"{load['quencher_amt_g']:.4f}",
             f"{ratios['quencher_to_pag_percent']:.1f}% on PAG"),
            ("Solvent", chem["solvent_1"], f"{load['solvent_pgmea_g']:.2f}", "Casting solvent"),
            ("Co-solvent", chem["solvent_2"], f"{load['solvent_pgme_g']:.2f}", ""),
            ("Surfactant", chem["surfactant"], f"{load['surfactant_g']:.4f}", ""),
        ]
        table = "".join(
            f'<tr><td class="role">{r}</td><td>{n}</td><td class="num">{m}</td><td class="role">{note}</td></tr>'
            for r, n, m, note in rows
        )
        uncertain = perf["lwr_uncertainty_nm"] > 2.0
        note_html = (
            '<div class="nl-note nl-note-warn"><b>Exploratory candidate.</b> Predictive uncertainty is high, which means '
            'this point lies outside the region covered by the 14 training formulations. Expected Improvement selects '
            'it because it could beat the best known result, not because the model is confident it will.</div>'
            if uncertain else ""
        )
        _html(f"""
        <div class="nl-card">
          <div class="nl-card-head">
            <div class="nl-card-title">{c['candidate_id']}<small>Rank {c['rank']}</small></div>{pill}
          </div>
          <div class="nl-metrics">
            <div class="nl-metric"><div class="nl-metric-label">Predicted LWR</div>
              <div class="nl-metric-value">{perf['ler_3sigma_lwr_nm']:.2f} nm</div>
              <div class="nl-metric-sub">± {perf['lwr_uncertainty_nm']:.2f} (1σ)</div></div>
            <div class="nl-metric"><div class="nl-metric-label">Predicted dose</div>
              <div class="nl-metric-value">{perf['sensitivity_dose_uc_cm2']:.1f} µC/cm²</div>
              <div class="nl-metric-sub">± {perf['dose_uncertainty_uc_cm2']:.1f} (1σ)</div></div>
            <div class="nl-metric"><div class="nl-metric-label">Expected improvement</div>
              <div class="nl-metric-value">{perf['ei_acquisition_score']:.3f}</div>
              <div class="nl-metric-sub">nm below best observed</div></div>
            <div class="nl-metric"><div class="nl-metric-label">Regulatory</div>
              <div class="nl-metric-value">{'PFAS-free' if comp['is_pfas_free'] else 'Contains PFAS'}</div>
              <div class="nl-metric-sub">{comp['regulatory_clearance']}</div></div>
          </div>
          {note_html}
          <table class="nl-table">
            <thead><tr><th>Role</th><th>Component</th><th class="num">Mass (g)</th><th>Note</th></tr></thead>
            <tbody>{table}</tbody>
          </table>
          <div class="nl-note">{comp['pag_audit_note']}</div>
        </div>
        """)
        st.download_button(
            f"Download {c['candidate_id']} recipe (JSON)", data=json.dumps(c, indent=2),
            file_name=f"{c['candidate_id']}_recipe.json", mime="application/json", key=f"dl_{c['candidate_id']}",
        )


def _tab_whatif(orch, df):
    _section("What-if simulator",
             "Adjust component loadings and read the surrogate's prediction with its 95% interval. "
             "Shaded bands show the range spanned by the training data.")
    left, right = st.columns([1, 1.35], gap="large")
    with left:
        w_resin = st.slider("Resin (g)", 0.60, 0.75, 0.68, 0.01)
        w_mm = st.slider("Crosslinker 1 · melamine MM-1 (g)", 0.00, 0.30, 0.20, 0.01)
        w_cl = st.slider("Crosslinker 2 · glycoluril CL-1 (g)", 0.00, 0.20, 0.08, 0.01)
        w_pag = st.slider("PAG (g)", 0.03, 0.10, 0.06, 0.005)
        w_q = st.slider("Quencher (g)", 0.001, 0.008, 0.004, 0.0005, format="%.4f")

    pred = orch.surrogate.predict(vectorize_candidate(w_resin, w_mm, w_cl, w_pag, w_q))
    lwr, lwr_s = float(pred["lwr_mean"][0]), float(pred["lwr_std"][0])
    dose, dose_s = float(pred["dose_mean"][0]), float(pred["dose_std"][0])

    with right:
        if w_mm == 0.0 or w_cl == 0.0:
            _html('<div class="nl-note nl-note-warn"><b>Single-crosslinker formulation.</b> In US7432034B2 the two '
                  'single-crosslinker comparative examples gave 10.5 and 13.8 nm LWR versus 4.5–6.2 nm for '
                  'dual-crosslinker examples.</div>')
        c1, c2 = st.columns(2)
        c1.metric("Predicted LWR (3σ)", f"{lwr:.2f} nm", f"± {lwr_s:.2f} nm (1σ)", delta_color="off")
        c2.metric("Predicted dose", f"{dose:.2f} µC/cm²", f"± {dose_s:.2f} (1σ)", delta_color="off")

        def gauge(label, mean, sd, lo, hi, train_lo, train_hi, unit, color):
            d = pd.DataFrame({"m": [label], "mean": [mean], "lo": [max(0.0, mean - 1.96 * sd)],
                              "hi": [mean + 1.96 * sd], "tlo": [train_lo], "thi": [train_hi]})
            base = alt.Chart(d).encode(y=alt.Y("m:N", title=None, axis=alt.Axis(labels=False, ticks=False)))
            band = base.mark_bar(color="#E2E8F0", height=26).encode(
                x=alt.X("tlo:Q", scale=alt.Scale(domain=[lo, hi]), title=unit), x2="thi:Q")
            ci = base.mark_rule(color=color, strokeWidth=3).encode(x="lo:Q", x2="hi:Q")
            pt = base.mark_point(color=color, filled=True, size=140).encode(
                x="mean:Q", tooltip=[alt.Tooltip("mean:Q", format=".2f"), alt.Tooltip("lo:Q", format=".2f"),
                                     alt.Tooltip("hi:Q", format=".2f")])
            return (band + ci + pt).properties(height=70, title=label)

        st.altair_chart(gauge("LWR, 3σ", lwr, lwr_s, 0, 20, df["ler_3sigma_nm"].min(), df["ler_3sigma_nm"].max(),
                              "nm", PRIMARY), use_container_width=True)
        st.altair_chart(gauge("Sensitivity, E_size", dose, dose_s, 3, 8, df["sensitivity_esize_uc_cm2"].min(),
                              df["sensitivity_esize_uc_cm2"].max(), "µC/cm²", ACCENT), use_container_width=True)


def _tab_benchmark():
    sim = _simulation(25)
    _section("Retrospective benchmark",
             "Starting from 3 random formulations, each strategy picks the next experiment from the remaining "
             "patent examples. Curves show the best LWR found so far, averaged over 25 random starts (band = ±1 SD).")
    steps = sim["steps"]
    d = pd.concat([
        pd.DataFrame({"Experiments": [s + 2 for s in steps], "Mean": sim["bo_mean"], "SD": sim["bo_std"],
                      "Strategy": "Bayesian optimization (EI)"}),
        pd.DataFrame({"Experiments": [s + 2 for s in steps], "Mean": sim["rand_mean"], "SD": sim["rand_std"],
                      "Strategy": "Random selection"}),
    ])
    d["Lo"], d["Hi"] = d["Mean"] - d["SD"], d["Mean"] + d["SD"]
    color = alt.Color("Strategy:N", scale=alt.Scale(domain=["Bayesian optimization (EI)", "Random selection"],
                                                     range=[PRIMARY, "#94A3B8"]))
    base = alt.Chart(d).encode(x=alt.X("Experiments:Q", title="Experiments run (including 3 seed points)",
                                       axis=alt.Axis(tickMinStep=1)))
    band = base.mark_area(opacity=0.14).encode(y=alt.Y("Lo:Q", title="Best LWR found (nm)",
                                                        scale=alt.Scale(zero=False)), y2="Hi:Q", color=color)
    line = base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=45, filled=True)).encode(
        y="Mean:Q", color=color,
        tooltip=["Strategy", "Experiments", alt.Tooltip("Mean:Q", format=".2f"), alt.Tooltip("SD:Q", format=".2f")])
    rule = alt.Chart(pd.DataFrame({"y": [4.5]})).mark_rule(strokeDash=[4, 4], color=RED).encode(y="y:Q")

    left, right = st.columns([2.1, 1], gap="large")
    with left:
        st.altair_chart((band + line + rule).properties(height=360), use_container_width=True)
    with right:
        k = min(2, len(steps) - 1)
        bo_k, rd_k = sim["bo_mean"][k], sim["rand_mean"][k]

        def first_hit(series, thr=4.5 + 1e-6):
            return next((i + 3 for i, v in enumerate(series) if v <= thr), None)

        bo_hit, rd_hit = first_hit(sim["bo_mean"]), first_hit(sim["rand_mean"])
        _html(f"""
        <div class="nl-card">
          <div class="nl-metric-label">After {k + 3} experiments</div>
          <div class="nl-metric-value" style="font-size:1.3rem">{bo_k:.2f} nm <span style="color:{SLATE_500};font-size:.85rem">BO</span></div>
          <div class="nl-metric-value" style="font-size:1.3rem;color:{SLATE_500}">{rd_k:.2f} nm <span style="font-size:.85rem">Random</span></div>
          <div style="height:.8rem"></div>
          <div class="nl-metric-label">Mean curve reaches 4.5 nm at</div>
          <div class="nl-metric-value" style="font-size:1.1rem">BO: {bo_hit if bo_hit else '—'} &nbsp;·&nbsp; Random: {rd_hit if rd_hit else '—'}</div>
        </div>
        <div class="nl-note">With only 14 historical formulations, half of them already within 1 nm of the optimum,
        the margin between strategies is necessarily small. The benchmark becomes more informative as more
        comparable records are added.</div>
        """)


def _tab_data(df, loocv, orch):
    _section("Training data", "US7432034B2 e-beam examples, standardised to grams per formulation.")
    show = df[["example_label", "is_comparative", "resin_amt", "mm_crosslinker_amt", "cl_crosslinker_amt",
               "pag_amt", "quencher_amt", "ler_3sigma_nm", "sensitivity_esize_uc_cm2"]].rename(columns={
        "example_label": "Example", "is_comparative": "Comparative", "resin_amt": "Resin (g)",
        "mm_crosslinker_amt": "MM (g)", "cl_crosslinker_amt": "CL (g)", "pag_amt": "PAG (g)",
        "quencher_amt": "Quencher (g)", "ler_3sigma_nm": "LWR (nm)", "sensitivity_esize_uc_cm2": "Dose (µC/cm²)"})
    st.dataframe(show, hide_index=True, use_container_width=True,
                 column_config={"Comparative": st.column_config.CheckboxColumn(),
                                "Quencher (g)": st.column_config.NumberColumn(format="%.4f")})

    _section("Surrogate validation", "Leave-one-out predictions: each point is predicted by a model that never saw it.")
    c1, c2 = st.columns(2, gap="large")
    for col, key, label, unit in [(c1, "lwr", "LWR", "nm"), (c2, "dose", "Sensitivity", "µC/cm²")]:
        r = loocv[key]
        pdf = pd.DataFrame({"Measured": r["y_true"], "Predicted": r["y_pred"], "Example": df["example_label"]})
        lo = float(min(pdf.min(numeric_only=True))) * 0.95
        hi = float(max(pdf.max(numeric_only=True))) * 1.05
        scale = alt.Scale(domain=[lo, hi])
        diag = alt.Chart(pd.DataFrame({"a": [lo, hi]})).mark_line(color=SLATE_300, strokeDash=[4, 4]).encode(
            x=alt.X("a:Q", scale=scale), y=alt.Y("a:Q", scale=scale))
        pts = alt.Chart(pdf).mark_circle(size=80, color=PRIMARY, opacity=0.85).encode(
            x=alt.X("Measured:Q", scale=scale, title=f"Measured ({unit})"),
            y=alt.Y("Predicted:Q", scale=scale, title=f"Predicted ({unit})"),
            tooltip=["Example", alt.Tooltip("Measured:Q", format=".2f"), alt.Tooltip("Predicted:Q", format=".2f")])
        with col:
            st.altair_chart((diag + pts).properties(
                height=300, title=f"{label} · MAE {r['mae']:.2f} {unit} · RMSE {r['rmse']:.2f} · R² {r['r2']:.2f}"),
                use_container_width=True)

    _section("Restricted-substance registry", "Entries the compliance agent screens against, with suggested replacements.")
    reg = orch.compliance_agent.registry
    st.dataframe(pd.DataFrame([{
        "Substance": i["name"], "Formula": i["formula"],
        "Listed under": ", ".join(i["regulatory_lists"]), "Concern": i["concern"],
        "Suggested substitutes": ", ".join(s["name"] for s in i["recommended_substitutes"]),
    } for i in reg.get("pfas_anions", [])]), hide_index=True, use_container_width=True)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def render_automated_dashboard(show_sidebar_brand: bool = True):
    st.markdown(CSS, unsafe_allow_html=True)
    params = _sidebar(show_sidebar_brand)

    orch = _orchestrator()
    _, _, _, _, df = _dataset()
    loocv = _loocv()

    _hero()
    _kpis(df, loocv)

    t1, t2, t3, t4 = st.tabs(["Recommendations", "What-if simulator", "Benchmark", "Data & model"])
    with t1:
        _tab_recommendations(params)
    with t2:
        _tab_whatif(orch, df)
    with t3:
        _tab_benchmark()
    with t4:
        _tab_data(df, loocv, orch)

    _html('<div class="nl-footer">Project Negative Lines &middot; OSI Hackathon 2026 &middot; '
          'Compliance output is a screening aid, not legal advice.</div>')
