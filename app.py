import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import json

# Ensure automated and manual src paths are available
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, os.path.join(ROOT_DIR, "automated", "src"))
sys.path.insert(0, os.path.join(ROOT_DIR, "manual", "src"))

st.set_page_config(
    page_title="Project Negative Lines | AI & Manual Lithography Platform",
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
        margin-bottom: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Track Selector
st.sidebar.title("🔬 Project Negative Lines")
system_track = st.sidebar.radio(
    "Select Workflow Track:",
    [
        "🤖 Automated Engine (AI, GP Surrogate & BO)",
        "✍️ Manual Workbench (Chemist Calculator & Rules)"
    ],
    index=0,
    help="Toggle between the fully automated closed-loop AI engine and the manual laboratory formulation workbench."
)
st.sidebar.markdown("---")

# =============================================================================
# TRACK 1: AUTOMATED AI ENGINE
# =============================================================================
if system_track.startswith("🤖"):
    from dataset import load_ebeam_dataset
    from surrogate import GaussianProcessSurrogate, DualLithoSurrogate
    from optimizer import BayesianOptimizer, vectorize_candidate, run_retrospective_simulation
    from compliance import ComplianceAgent
    from orchestrator import FormulationOrchestrator

    st.markdown('<div class="main-title">🤖 Automated AI Formulation & Compliance Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Closed-loop Bayesian Optimization, Gaussian Process surrogate modeling, and regulatory compliance screening for high-resolution negative-tone e-beam resists.</div>', unsafe_allow_html=True)

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

    # Sidebar: Target Specs
    st.sidebar.header("🎯 Target Specifications")
    target_lwr = st.sidebar.slider("Target Line Edge Roughness (LWR 3σ)", min_value=4.0, max_value=7.0, value=4.5, step=0.1)
    target_dose = st.sidebar.slider("Target Dose / Sensitivity", min_value=4.5, max_value=7.0, value=5.5, step=0.1)
    pfas_free_req = st.sidebar.checkbox("Enforce 100% PFAS-Free Compliance", value=True)
    n_candidates = st.sidebar.slider("Number of Candidates", min_value=1, max_value=5, value=2)

    st.sidebar.markdown("**Tool & Exposure Conditions**")
    st.sidebar.markdown("""
    - **Exposure:** Electron Beam (50 keV)
    - **Substrate:** 6-inch Si Wafer
    - **Film Thickness:** 300 nm
    - **PEB:** 110 °C for 90 s
    - **Developer:** 2.38 wt% TMAH (60 s)
    """)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Bayesian Optimization Recommendations",
        "🎛️ What-If Formulation Simulator",
        "📈 Retrospective Benchmark (BO vs Random)",
        "📚 Dataset & Chemical Compliance Explorer"
    ])

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

                recipe_json = json.dumps(cand, indent=2)
                st.download_button(
                    f"📥 Download {cand['candidate_id']} Recipe (JSON)",
                    data=recipe_json,
                    file_name=f"{cand['candidate_id']}_recipe.json",
                    mime="application/json"
                )

    with tab2:
        st.subheader("Interactive What-If Formulation Simulator")
        colA, colB = st.columns([1, 1])

        with colA:
            st.markdown("**Adjust Formulation Loadings (grams):**")
            w_resin = st.slider("Resin (g)", 0.60, 0.75, 0.68, 0.01)
            w_mm = st.slider("MM-Crosslinker (Melamine Cymel) (g)", 0.00, 0.30, 0.20, 0.01)
            w_cl = st.slider("CL-Crosslinker (Glycoluril) (g)", 0.00, 0.20, 0.08, 0.01)
            w_pag = st.slider("PAG (g)", 0.03, 0.10, 0.06, 0.005)
            w_quencher = st.slider("Basic Quencher (g)", 0.001, 0.008, 0.004, 0.0005, format="%.4f")

            feat_df = vectorize_candidate(w_resin, w_mm, w_cl, w_pag, w_quencher)
            pred_out = orch.surrogate.predict(feat_df)
            sim_lwr = float(pred_out["lwr_mean"][0])
            sim_lwr_std = float(pred_out["lwr_std"][0])
            sim_dose = float(pred_out["dose_mean"][0])
            sim_dose_std = float(pred_out["dose_std"][0])

        with colB:
            st.markdown("**Surrogate Model Prediction:**")
            if w_mm == 0.0 or w_cl == 0.0:
                st.warning("⚠️ **Single Crosslinker Alert**: US7432034B2 proves single-crosslinker formulations result in severe roughness jumps (LWR 10.5 - 13.8 nm). Dual crosslinkers are required.")

            res_col1, res_col2 = st.columns(2)
            res_col1.metric("Predicted LWR (3σ)", f"{sim_lwr:.2f} nm", f"± {sim_lwr_std:.2f} nm")
            res_col2.metric("Predicted Dose", f"{sim_dose:.1f} µC/cm²", f"± {sim_dose_std:.1f} µC/cm²")

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

    with tab3:
        st.subheader("Retrospective Validation: Bayesian Optimization vs Random Selection")
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

    with tab4:
        st.subheader("Benchmark Lithography Dataset & Regulatory Knowledge Base")
        display_cols = ["example_label", "is_comparative", "resin_amt", "mm_crosslinker_amt", "cl_crosslinker_amt", "pag_amt", "quencher_amt", "ler_3sigma_nm", "sensitivity_esize_uc_cm2"]
        st.dataframe(raw_df[display_cols].rename(columns={"ler_3sigma_nm": "LWR (nm)", "sensitivity_esize_uc_cm2": "Dose (µC/cm²)", "is_comparative": "Comparative?"}), use_container_width=True)

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

# =============================================================================
# TRACK 2: MANUAL FORMULATION WORKBENCH
# =============================================================================
else:
    from validator import validate_manual_formulation
    from manual_calculator import estimate_film_thickness, estimate_baseline_sensitivity

    st.markdown('<div class="main-title">✍️ Manual Formulation Workbench & Lab Calculator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Human-in-the-loop formulation workbench for semiconductor photoresists. Validate mass balances, calculate solid wt%, check empirical spin thickness, and generate lab dispensing cards.</div>', unsafe_allow_html=True)

    tab_m1, tab_m2, tab_m3 = st.tabs([
        "🧮 Formulation Mass Balance & Validator",
        "📥 Manual Entry Template & CSV Upload",
        "📋 Lab Safety & Compliance Checklist"
    ])

    with tab_m1:
        st.subheader("Component Loading Inputs (Grams)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**1. Polymeric Resin**")
            resin_name = st.text_input("Resin Name", value="P-1 (Poly[PHS-co-HPS], Mw 12k)")
            resin_amt = st.number_input("Resin Mass (g)", min_value=0.0, max_value=5.0, value=0.700, step=0.01, format="%.3f")
            st.markdown("**2. Crosslinker System**")
            mm_name = st.text_input("Primary Crosslinker", value="MM-1 (Melamine / Cymel 300)")
            mm_amt = st.number_input("Primary Crosslinker Mass (g)", min_value=0.0, max_value=1.0, value=0.200, step=0.01, format="%.3f")
            cl_name = st.text_input("Secondary Crosslinker", value="CL-1 (Glycoluril / Powderlink 1174)")
            cl_amt = st.number_input("Secondary Crosslinker Mass (g)", min_value=0.0, max_value=1.0, value=0.100, step=0.01, format="%.3f")

        with col2:
            st.markdown("**3. Photoacid Generator & Quencher**")
            pag_name = st.text_input("PAG Name", value="Triphenylsulfonium Camphorsulfonate (PFAS-Free)")
            pag_amt = st.number_input("PAG Mass (g)", min_value=0.0, max_value=0.5, value=0.060, step=0.005, format="%.3f")
            quencher_name = st.text_input("Basic Quencher", value="D-1 (Trioctylamine)")
            quencher_amt = st.number_input("Quencher Mass (g)", min_value=0.0, max_value=0.05, value=0.0050, step=0.0005, format="%.4f")
            surf_amt = st.number_input("Surfactant Mass (g)", min_value=0.0, max_value=0.01, value=0.0010, step=0.0005, format="%.4f")

        with col3:
            st.markdown("**4. Casting Solvents**")
            solv1_name = st.text_input("Solvent 1", value="PGMEA (Propylene glycol monomethyl ether acetate)")
            solv1_amt = st.number_input("Solvent 1 Mass (g)", min_value=0.0, max_value=20.0, value=7.50, step=0.25, format="%.2f")
            solv2_name = st.text_input("Solvent 2", value="PGME (Propylene glycol monomethyl ether)")
            solv2_amt = st.number_input("Solvent 2 Mass (g)", min_value=0.0, max_value=10.0, value=1.50, step=0.25, format="%.2f")
            spin_rpm = st.slider("Target Spin Speed (RPM)", 800, 3000, 1500, 50)

        inputs = {
            "resin_amt": resin_amt,
            "primary_crosslinker_amt": mm_amt,
            "secondary_crosslinker_amt": cl_amt,
            "pag_amt": pag_amt,
            "quencher_amt": quencher_amt,
            "solvent_1_amt": solv1_amt,
            "solvent_2_amt": solv2_amt,
            "surfactant_amt": surf_amt
        }
        val_res = validate_manual_formulation(inputs)
        props = val_res["calculated_properties"]
        est_thick = estimate_film_thickness(props["solids_wt_percent"], spin_rpm)
        est_dose = estimate_baseline_sensitivity(props["pag_to_resin_percent"], props["quencher_to_pag_percent"])

        st.markdown("---")
        st.subheader("Calculated Physical Properties & Fab Feasibility")
        colM1, colM2, colM3, colM4 = st.columns(4)
        colM1.metric("Total Solids Content", f"{props['solids_wt_percent']:.2f} wt%", f"Total: {props['total_mass_g']:.2f} g")
        colM2.metric("Crosslinker : Resin", f"{props['crosslinker_to_resin_percent']:.1f} %", f"MM Ratio: {props['mm_crosslinker_percent']:.0f}%")
        colM3.metric("Estimated Film Thickness", f"{est_thick:.0f} nm", f"@ {spin_rpm} RPM")
        colM4.metric("Empirical Dose Estimate", f"{est_dose:.1f} µC/cm²", "50 keV E-beam")

        if val_res["errors"]:
            for e in val_res["errors"]:
                st.error(f"❌ {e}")
        if val_res["warnings"]:
            for w in val_res["warnings"]:
                st.warning(f"⚠️ {w}")
        if not val_res["errors"] and not val_res["warnings"]:
            st.success("✓ Formulation passes all standard mass-balance and stoichiometry validation rules.")

        recipe_dict = {
            "track": "manual_bench_formulation",
            "resin": {"name": resin_name, "mass_g": resin_amt},
            "primary_crosslinker": {"name": mm_name, "mass_g": mm_amt},
            "secondary_crosslinker": {"name": cl_name, "mass_g": cl_amt},
            "pag": {"name": pag_name, "mass_g": pag_amt},
            "quencher": {"name": quencher_name, "mass_g": quencher_amt},
            "solvents": [{"name": solv1_name, "mass_g": solv1_amt}, {"name": solv2_name, "mass_g": solv2_amt}],
            "surfactant_g": surf_amt,
            "calculated_properties": props,
            "process_conditions": {
                "spin_speed_rpm": spin_rpm,
                "est_film_thickness_nm": est_thick,
                "recommended_softbake": "120 °C for 90 s",
                "recommended_peb": "110 °C for 90 s",
                "developer": "2.38 wt% TMAH (60 s)"
            }
        }
        st.download_button("📥 Download Manual Recipe Card (JSON)", data=json.dumps(recipe_dict, indent=2), file_name="manual_recipe_card.json", mime="application/json")

    with tab_m2:
        st.subheader("Manual Data Template & Batch Upload")
        template_path = os.path.join(ROOT_DIR, "manual", "data", "manual_formulation_template.csv")
        if os.path.exists(template_path):
            with open(template_path, "r") as f:
                csv_bytes = f.read()
            st.download_button("📥 Download Blank Formulation Template (CSV)", data=csv_bytes, file_name="negative_lines_manual_template.csv", mime="text/csv")
        uploaded = st.file_uploader("Upload Completed Manual Formulations (CSV)", type=["csv"])
        if uploaded is not None:
            user_df = pd.read_csv(uploaded)
            st.dataframe(user_df, use_container_width=True)
            st.success(f"Successfully loaded {len(user_df)} manual formulation records.")

    with tab_m3:
        st.subheader("Pre-Fab Laboratory Safety & Compliance Checklist")
        c1 = st.checkbox("Non-Fluorinated Anion Confirmed (Free of restricted PFAS perfluoroalkyl chains)")
        c2 = st.checkbox("Green Solvent Verification (PGMEA/PGME; zero NMP, 2-methoxyethanol, or benzene derivatives)")
        c3 = st.checkbox("Substrate Surface Preparation (HMDS dehydration prime completed on 6-inch Si wafer)")
        c4 = st.checkbox("Post-Exposure Bake Temperature Calibration (PEB hotplate verified at 110.0 ± 0.3 °C)")
        c5 = st.checkbox("Developer Freshness Verified (Aqueous 2.38 wt% TMAH, temperature controlled at 23 °C)")
        if c1 and c2 and c3 and c4 and c5:
            st.success("✅ Batch Certified for Fab Processing by Laboratory Chemist.")
        else:
            st.info("Complete all checklist items above before dispensing formulation onto wafer track.")

st.markdown("---")
st.caption("Project Negative Lines | Dual-Track Architecture: Automated AI Engine & Manual Formulation Workbench")
