import streamlit as st
import pandas as pd
import json
import os
import sys

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from validator import validate_manual_formulation
from manual_calculator import estimate_film_thickness, estimate_baseline_sensitivity

st.set_page_config(
    page_title="Project Negative Lines | Manual Formulation Workbench",
    page_icon="✍️",
    layout="wide"
)

st.title("✍️ Manual Formulation Workbench & Lab Calculator")
st.caption("Human-in-the-loop formulation workbench for semiconductor photoresists. Validate mass balances, calculate solid wt%, check empirical spin thickness, and generate lab dispensing cards.")

tab_calc, tab_template, tab_audit = st.tabs([
    "🧮 Formulation Mass Balance & Validator",
    "📥 Manual Entry Template & CSV Upload",
    "📋 Lab Safety & Compliance Checklist"
])

with tab_calc:
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

        spin_rpm = st.slider("Target Spin Coating Speed (RPM)", 800, 3000, 1500, 50)

    # Perform Validation
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

    # Display Warnings/Errors
    if val_res["errors"]:
        for e in val_res["errors"]:
            st.error(f"❌ {e}")
    if val_res["warnings"]:
        for w in val_res["warnings"]:
            st.warning(f"⚠️ {w}")
    if not val_res["errors"] and not val_res["warnings"]:
        st.success("✓ Formulation passes all standard mass-balance and stoichiometry validation rules.")

    # Lab Recipe Card Download
    recipe_dict = {
        "track": "manual_bench_formulation",
        "resin": {"name": resin_name, "mass_g": resin_amt},
        "primary_crosslinker": {"name": mm_name, "mass_g": mm_amt},
        "secondary_crosslinker": {"name": cl_name, "mass_g": cl_amt},
        "pag": {"name": pag_name, "mass_g": pag_amt},
        "quencher": {"name": quencher_name, "mass_g": quencher_amt},
        "solvents": [
            {"name": solv1_name, "mass_g": solv1_amt},
            {"name": solv2_name, "mass_g": solv2_amt}
        ],
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
    st.download_button(
        "📥 Download Manual Recipe Card (JSON)",
        data=json.dumps(recipe_dict, indent=2),
        file_name="manual_recipe_card.json",
        mime="application/json"
    )

with tab_template:
    st.subheader("Manual Data Template & Batch Upload")
    st.write("Bench chemists and annotators can download the standardized CSV template matching `vocab.yaml`, record manual experimental results, and upload them here.")
    
    template_path = os.path.join(os.path.dirname(__file__), "data", "manual_formulation_template.csv")
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            csv_bytes = f.read()
        st.download_button("📥 Download Blank Formulation Template (CSV)", data=csv_bytes, file_name="negative_lines_manual_template.csv", mime="text/csv")

    uploaded = st.file_uploader("Upload Completed Manual Formulations (CSV)", type=["csv"])
    if uploaded is not None:
        user_df = pd.read_csv(uploaded)
        st.dataframe(user_df, use_container_width=True)
        st.success(f"Successfully loaded {len(user_df)} manual formulation records.")

with tab_audit:
    st.subheader("Pre-Fab Laboratory Safety & Compliance Checklist")
    st.markdown("Ensure every manual batch fulfills environment, health, and safety (EHS) requirements prior to wafer dispensing:")
    
    c1 = st.checkbox("Non-Fluorinated Anion Confirmed (Free of restricted PFAS perfluoroalkyl chains)")
    c2 = st.checkbox("Green Solvent Verification (PGMEA/PGME; zero NMP, 2-methoxyethanol, or benzene derivatives)")
    c3 = st.checkbox("Substrate Surface Preparation (HMDS dehydration prime completed on 6-inch Si wafer)")
    c4 = st.checkbox("Post-Exposure Bake Temperature Calibration (PEB hotplate verified at 110.0 ± 0.3 °C)")
    c5 = st.checkbox("Developer Freshness Verified (Aqueous 2.38 wt% TMAH, temperature controlled at 23 °C)")

    if c1 and c2 and c3 and c4 and c5:
        st.success("✅ Batch Certified for Fab Processing by Laboratory Chemist.")
    else:
        st.info("Complete all checklist items above before dispensing formulation onto wafer track.")
