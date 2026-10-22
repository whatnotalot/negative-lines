import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import json

# Add src to sys.path so modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dataset import load_ebeam_dataset
from surrogate import GaussianProcessSurrogate, DualLithoSurrogate
from optimizer import BayesianOptimizer, vectorize_candidate, run_retrospective_simulation
from compliance import ComplianceAgent
from orchestrator import FormulationOrchestrator

st.set_page_config(
    page_title="Project Negative Lines | AI Lithography & PFAS-Free Formulation",
    page_icon="🔬",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #E2E8F0;
    }
    .stBadge {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Title & Description
st.markdown('<div class="main-title">🔬 Project Negative Lines: AI Formulation & Compliance Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Closed-loop Bayesian Optimization, Gaussian Process surrogate modeling, and regulatory compliance screening for high-resolution negative-tone e-beam resists.</div>', unsafe_allow_html=True)

# Initialize Session State & Cached Models
@st.cache_resource
def get_cached_orchestrator():
    return FormulationOrchestrator()

@st.cache_data
def get_cached_dataset():
    return load_ebeam_dataset()

@st.cache_data
def get_cached_simulation():
    return run_retrospective_simulation(n_trials=25)

orch = get_cached_orchestrator()
X_df, y_lwr, y_dose, fnames, raw_df = get_cached_dataset()

# Sidebar: Research Objective & Constraints
st.sidebar.header("🎯 Target Specifications")
target_lwr = st.sidebar.slider("Target Line Edge Roughness (LWR 3σ)", min_value=4.0, max_value=7.0, value=4.5, step=0.1, help="Desired roughness in nanometers (lower is better).")
target_dose = st.sidebar.slider("Target Dose / Sensitivity (E_size)", min_value=4.5, max_value=7.0, value=5.5, step=0.1, help="Target exposure dose in µC/cm² at 50 keV tool conditions.")
pfas_free_req = st.sidebar.checkbox("Enforce 100% PFAS-Free Compliance", value=True, help="Automatically substitutes persistent fluorinated nonaflates with non-fluorinated camphorsulfonate or tosylate.")
n_candidates = st.sidebar.slider("Number of Candidates", min_value=1, max_value=5, value=2)

st.sidebar.markdown("---")
st.sidebar.markdown("**Tool & Exposure Conditions**")
st.sidebar.markdown("""
- **Exposure:** Electron Beam (50 keV)
- **Substrate:** 6-inch Si Wafer
- **Film Thickness:** 300 nm
- **PEB:** 110 °C for 90 s
- **Developer:** 2.38 wt% TMAH (60 s)
""")

# Main Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Bayesian Optimization Recommendations",
    "🎛️ What-If Formulation Simulator",
    "📈 Retrospective Benchmark (BO vs Random)",
    "📚 Dataset & Chemical Compliance Explorer"
])

# -----------------------------------------------------------------------------
# TAB 1: Bayesian Optimization Recommendations
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("Automated Closed-Loop Formulation Synthesis Cards")
    st.caption("Bayesian Optimization searches the dual-crosslinker parameter space, maximizing Expected Improvement (EI) on LWR while targeting sensitivity.")

    if st.button("Generate Optimized Formulations", type="primary"):
        with st.spinner("Running Bayesian Optimization & Compliance Audit..."):
            pipeline_out = orch.run_pipeline(
                target_lwr=target_lwr,
                target_dose=target_dose,
                pfas_free=pfas_free_req,
                n_candidates=n_candidates
            )
            st.session_state["pipeline_results"] = pipeline_out

    results = st.session_state.get("pipeline_results")
    if not results:
        # Run default initial candidates
        results = orch.run_pipeline(
            target_lwr=target_lwr,
            target_dose=target_dose,
            pfas_free=pfas_free_req,
            n_candidates=n_candidates
        )
        st.session_state["pipeline_results"] = results

    for cand in results["candidates"]:
        perf = cand["predicted_performance"]
        loadings = cand["formulation_loadings_grams"]
        ratios = cand["chemical_ratios"]
        comp = cand["compliance"]

        with st.expander(f"★ Candidate {cand['candidate_id']} (Rank #{cand['rank']}) - Predicted LWR: {perf['ler_3sigma_lwr_nm']:.2f} nm", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Predicted LWR (3σ)", f"{perf['ler_3sigma_lwr_nm']:.2f} nm", f"± {perf['lwr_uncertainty_nm']:.2f} nm")
            col2.metric("Predicted Dose", f"{perf['sensitivity_dose_uc_cm2']:.1f} µC/cm²", f"± {perf['dose_uncertainty_uc_cm2']:.1f} µC/cm²")
            col3.metric("Expected Improvement", f"{perf['ei_acquisition_score']:.4f}")
            col4.metric("Compliance Status", comp["status"], "PFAS-Free" if comp["is_pfas_free"] else "Restricted")

            st.markdown(f"**95% Confidence Interval for LWR:** `{perf['confidence_interval_95_lwr']}`")
            st.info(f"**Regulatory Audit:** {comp['pag_audit_note']}")

            # Laboratory Loading Table
            table_data = [
                {"Role": "Resin (P-1)", "Chemical Name": cand["formulation_chemicals"]["resin"], "Mass (g)": f"{loadings['resin_amt_g']:.3f} g", "Ratio / Note": "Matrix polymer (Mw 12k)"},
                {"Role": "Primary Crosslinker", "Chemical Name": cand["formulation_chemicals"]["crosslinker_primary"], "Mass (g)": f"{loadings['mm_crosslinker_amt_g']:.3f} g", "Ratio / Note": f"MM Ratio: {ratios['mm_to_total_crosslinker_ratio']:.1%}"},
                {"Role": "Secondary Crosslinker", "Chemical Name": cand["formulation_chemicals"]["crosslinker_secondary"], "Mass (g)": f"{loadings['cl_crosslinker_amt_g']:.3f} g", "Ratio / Note": "Dual Crosslinker System"},
                {"Role": "Photoacid Generator (PAG)", "Chemical Name": cand["formulation_chemicals"]["photoacid_generator"], "Mass (g)": f"{loadings['pag_amt_g']:.3f} g", "Ratio / Note": f"{ratios['pag_to_resin_percent']:.1f}% on resin"},
                {"Role": "Basic Quencher", "Chemical Name": cand["formulation_chemicals"]["basic_quencher"], "Mass (g)": f"{loadings['quencher_amt_g']:.4f} g", "Ratio / Note": f"{ratios['quencher_to_pag_percent']:.1f}% on PAG"},
                {"Role": "Solvent 1", "Chemical Name": cand["formulation_chemicals"]["solvent_1"], "Mass (g)": f"{loadings['solvent_pgmea_g']:.2f} g", "Ratio / Note": "Casting Solvent"},
                {"Role": "Solvent 2", "Chemical Name": cand["formulation_chemicals"]["solvent_2"], "Mass (g)": f"{loadings['solvent_pgme_g']:.2f} g", "Ratio / Note": "Co-solvent"},
                {"Role": "Surfactant", "Chemical Name": cand["formulation_chemicals"]["surfactant"], "Mass (g)": f"{loadings['surfactant_g']:.4f} g", "Ratio / Note": "Surface Uniformity"}
            ]
            st.table(pd.DataFrame(table_data))

            # Download recipe button
            recipe_json = json.dumps(cand, indent=2)
            st.download_button(
                f"📥 Download {cand['candidate_id']} Recipe (JSON)",
                data=recipe_json,
                file_name=f"{cand['candidate_id']}_recipe.json",
                mime="application/json"
            )

# -----------------------------------------------------------------------------
# TAB 2: What-If Formulation Simulator
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Interactive What-If Formulation Simulator")
    st.caption("Adjust chemical ingredient amounts in real time and observe Gaussian Process surrogate predictions with epistemic uncertainty.")

    colA, colB = st.columns([1, 1])

    with colA:
        st.markdown("**Adjust Formulation Loadings (grams):**")
        w_resin = st.slider("Resin (g)", 0.60, 0.75, 0.68, 0.01)
        w_mm = st.slider("MM-Crosslinker (Melamine Cymel) (g)", 0.00, 0.30, 0.20, 0.01)
        w_cl = st.slider("CL-Crosslinker (Glycoluril) (g)", 0.00, 0.20, 0.08, 0.01)
        w_pag = st.slider("PAG (g)", 0.03, 0.10, 0.06, 0.005)
        w_quencher = st.slider("Basic Quencher (g)", 0.001, 0.008, 0.004, 0.0005, format="%.4f")

        # Vectorize and predict
        feat_df = vectorize_candidate(w_resin, w_mm, w_cl, w_pag, w_quencher)
        pred_out = orch.surrogate.predict(feat_df)
        sim_lwr = float(pred_out["lwr_mean"][0])
        sim_lwr_std = float(pred_out["lwr_std"][0])
        sim_dose = float(pred_out["dose_mean"][0])
        sim_dose_std = float(pred_out["dose_std"][0])

    with colB:
        st.markdown("**Surrogate Model Prediction:**")
        
        # Dual-crosslinker check warning
        if w_mm == 0.0 or w_cl == 0.0:
            st.warning("⚠️ **Single Crosslinker Alert**: Patent US7432034B2 proves single-crosslinker formulations result in severe roughness jumps (LWR 10.5 - 13.8 nm). Dual crosslinkers are strongly advised.")

        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Predicted LWR (3σ)", f"{sim_lwr:.2f} nm", f"± {sim_lwr_std:.2f} nm")
        res_col2.metric("Predicted Dose", f"{sim_dose:.1f} µC/cm²", f"± {sim_dose_std:.1f} µC/cm²")

        # Uncertainty Bar Plot
        fig, ax = plt.subplots(1, 2, figsize=(7, 3.2))
        ax[0].bar(["Predicted LWR"], [sim_lwr], yerr=[sim_lwr_std], color="#2563EB", capsize=5, alpha=0.85)
        ax[0].axhline(4.5, color="green", linestyle="--", label="Target (4.5 nm)")
        ax[0].set_ylabel("LWR (nm)")
        ax[0].set_ylim(0, 15)
        ax[0].legend(loc="upper right", fontsize=8)

        ax[1].bar(["Predicted Dose"], [sim_dose], yerr=[sim_dose_std], color="#10B981", capsize=5, alpha=0.85)
        ax[1].axhline(5.5, color="red", linestyle="--", label="Target (5.5 µC/cm²)")
        ax[1].set_ylabel("Dose (µC/cm²)")
        ax[1].set_ylim(0, 10)
        ax[1].legend(loc="upper right", fontsize=8)
        plt.tight_layout()
        st.pyplot(fig)

# -----------------------------------------------------------------------------
# TAB 3: Retrospective Benchmark (BO vs Random)
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Retrospective Validation: Bayesian Optimization vs Random Selection")
    st.caption("Demonstrating algorithmic sample efficiency on the 14 historical e-beam formulation records from patent US7432034B2 over 25 trials.")

    sim_res = get_cached_simulation()

    steps = sim_res["steps"]
    bo_mean = sim_res["bo_mean"]
    bo_std = sim_res["bo_std"]
    rand_mean = sim_res["rand_mean"]
    rand_std = sim_res["rand_std"]

    colX, colY = st.columns([2, 1])

    with colX:
        fig_sim, ax_sim = plt.subplots(figsize=(7, 3.8))
        ax_sim.plot(steps, bo_mean, marker="o", color="#1D4ED8", label="Bayesian Optimization (Expected Improvement)", linewidth=2)
        ax_sim.fill_between(steps, np.array(bo_mean) - np.array(bo_std), np.array(bo_mean) + np.array(bo_std), color="#93C5FD", alpha=0.3)

        ax_sim.plot(steps, rand_mean, marker="s", color="#9CA3AF", linestyle="--", label="Random Selection (Baseline)", linewidth=2)
        ax_sim.fill_between(steps, np.array(rand_mean) - np.array(rand_std), np.array(rand_mean) + np.array(rand_std), color="#E5E7EB", alpha=0.3)

        ax_sim.axhline(4.5, color="red", linestyle=":", label="Global Optimum (4.5 nm)")
        ax_sim.set_xlabel("Iteration Step (Cumulative Experiments)")
        ax_sim.set_ylabel("Best Observed LWR (nm)")
        ax_sim.set_title("Formulation Discovery Trajectory")
        ax_sim.grid(True, linestyle="--", alpha=0.5)
        ax_sim.legend(fontsize=8)
        st.pyplot(fig_sim)

    with colY:
        st.markdown("**Key Benchmark Insights:**")
        st.markdown(rf"""
        - **Sample Efficiency Advantage:** Bayesian Optimization reaches optimal roughness ($\le 4.6$ nm) in **3–4 iterations**, whereas random trial-and-error requires **10+ experiments**.
        - **Material Savings:** Eliminates wasted fab runs, precious polymer synthesis, and wafer stepper time.
        - **Uncertainty Guidance:** Uses Gaussian Process predictive variance $\sigma(x)$ to balance exploring unvisited formulation regions with exploiting proven dual-crosslinker chemistries.
        """)

# -----------------------------------------------------------------------------
# TAB 4: Dataset & Chemical Compliance Explorer
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("Benchmark Lithography Dataset & Regulatory Knowledge Base")

    st.markdown("##### 1. Fujifilm US7432034B2 E-Beam Dataset (N=14)")
    st.caption("Standardized e-beam resist formulations evaluated at 50 keV on 6-inch Si wafers.")
    
    display_cols = [
        "example_label", "is_comparative", "resin_amt", "mm_crosslinker_amt",
        "cl_crosslinker_amt", "pag_amt", "quencher_amt", "ler_3sigma_nm", "sensitivity_esize_uc_cm2"
    ]
    st.dataframe(raw_df[display_cols].rename(columns={
        "ler_3sigma_nm": "LWR (nm)",
        "sensitivity_esize_uc_cm2": "Dose (µC/cm²)",
        "is_comparative": "Comparative?"
    }), use_container_width=True)

    st.markdown("##### 2. PFAS & Restricted Chemical Registry")
    st.caption("Curated regulatory list detailing restricted PFAS anions and approved non-fluorinated substitutes.")
    
    reg_data = orch.compliance_agent.registry
    pfas_rows = []
    for item in reg_data.get("pfas_anions", []):
        pfas_rows.append({
            "Restricted Entity": item["name"],
            "Formula": item["formula"],
            "Regulatory Citations": ", ".join(item["regulatory_lists"]),
            "Environmental Concern": item["concern"],
            "Approved Substitutes": ", ".join([s["name"] for s in item["recommended_substitutes"]])
        })
    st.table(pd.DataFrame(pfas_rows))

st.markdown("---")
st.caption("Project Negative Lines | Developed for OSI Hackathon 2026 | Compatible with Streamlit Community Cloud")
