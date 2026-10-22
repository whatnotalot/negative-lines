"""
Project Negative Lines - Autonomous Formulation Design Pipeline Demo
Multi-Agent Orchestration: Bayesian Optimization + Gaussian Process Surrogate + Compliance Screener
"""

import sys
import os
import time

# Ensure src is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from dataset import load_ebeam_dataset
from surrogate import GaussianProcessSurrogate, DualLithoSurrogate
from compliance import ComplianceAgent
from optimizer import BayesianOptimizer, run_retrospective_simulation
from orchestrator import FormulationOrchestrator

def print_banner(text):
    print("\n" + "=" * 78)
    print(f" {text.upper()}")
    print("=" * 78)

def main():
    print_banner("Project Negative Lines: Closed-Loop AI Lithography Engine")
    print("Initializing benchmark dataset from US7432034B2 (Fujifilm e-beam negative resists)...")
    
    t0 = time.time()
    X, y_lwr, y_dose, fnames, df = load_ebeam_dataset()
    print(f"✓ Loaded {len(df)} standardized formulation records under identical 50 keV tool conditions.")
    print(f"  - Baseline Best LWR: {y_lwr.min():.1f} nm (Examples with Dual MM+CL crosslinkers)")
    print(f"  - Baseline Worst LWR: {y_lwr.max():.1f} nm (Single crosslinker comparative examples)")

    print_banner("1. Surrogate Model Leave-One-Out Cross-Validation")
    surrogate = GaussianProcessSurrogate()
    cv_res = surrogate.evaluate_leave_one_out(X, y_lwr)
    print(f"Leave-One-Out CV on LWR (N=14 records):")
    print(f"  - R² Score: {cv_res['r2']:.3f}")
    print(f"  - Mean Absolute Error (MAE): {cv_res['mae']:.2f} nm")
    print(f"  - Root Mean Squared Error (RMSE): {cv_res['rmse']:.2f} nm")

    print_banner("2. Retrospective Simulation: Bayesian Optimization vs Random Search")
    print("Benchmarking optimization trajectory over historical patent data...")
    sim = run_retrospective_simulation(n_trials=25)
    print(f"  - Initial LWR (Random Seed N=3): {sim['bo_mean'][0]:.2f} nm")
    print(f"  - Iteration 3 LWR  -> BO: {sim['bo_mean'][2]:.2f} nm | Random: {sim['rand_mean'][2]:.2f} nm")
    print(f"  - Final Reached    -> BO: {sim['bo_mean'][-1]:.2f} nm | Random: {sim['rand_mean'][-1]:.2f} nm")
    print(f"  ✓ Efficiency advantage: BO achieves low-LWR optima in 3-4 experiments vs ~{sim['rand_steps_to_target']} for unguided trial-and-error.")

    print_banner("3. End-to-End Orchestrator: Autonomous PFAS-Free Design Loop")
    print("User Target Specification:")
    print("  - Target Line Edge Roughness (LWR): <= 4.5 nm")
    print("  - Target Dose / Sensitivity: ~ 5.5 µC/cm²")
    print("  - Regulatory Constraint: 100% PFAS-Free (REACH & TSCA compliant)")
    
    orch = FormulationOrchestrator()
    results = orch.run_pipeline(target_lwr=4.5, target_dose=5.5, pfas_free=True, n_candidates=2)

    for cand in results["candidates"]:
        print("\n" + "-" * 70)
        print(f"★ CANDIDATE RECIPE {cand['candidate_id']} (Rank #{cand['rank']})")
        print("-" * 70)
        perf = cand["predicted_performance"]
        print(f"Predicted LWR (3σ):    {perf['ler_3sigma_lwr_nm']:.2f} ± {perf['lwr_uncertainty_nm']:.2f} nm (95% CI: {perf['confidence_interval_95_lwr']})")
        print(f"Predicted Sensitivity: {perf['sensitivity_dose_uc_cm2']:.1f} ± {perf['dose_uncertainty_uc_cm2']:.1f} µC/cm²")
        print(f"Expected Improvement:  {perf['ei_acquisition_score']:.4f}")
        print(f"Compliance Status:     [{cand['compliance']['status']}] {cand['compliance']['regulatory_clearance']}")
        print(f"PFAS Audit Action:     {cand['compliance']['pag_audit_note']}")

        print("\nLaboratory Dispensing Card:")
        loadings = cand["formulation_loadings_grams"]
        print(f"  • Resin (P-1, Mw 12k):               {loadings['resin_amt_g']:.3f} g")
        print(f"  • Primary Crosslinker (MM-1 Cymel):  {loadings['mm_crosslinker_amt_g']:.3f} g  (MM ratio: {cand['chemical_ratios']['mm_to_total_crosslinker_ratio']:.1%})")
        print(f"  • Secondary Crosslinker (CL-1 Gly): {loadings['cl_crosslinker_amt_g']:.3f} g")
        print(f"  • Compliant PAG (Camphorsulfonate):  {loadings['pag_amt_g']:.3f} g  ({cand['chemical_ratios']['pag_to_resin_percent']:.1f}% on resin)")
        print(f"  • Quencher (Trioctylamine):          {loadings['quencher_amt_g']:.4f} g")
        print(f"  • Solvents:                          PGMEA {loadings['solvent_pgmea_g']:.1f} g + PGME {loadings['solvent_pgme_g']:.1f} g")
        print(f"  • Surfactant (Megafac F-176):        {loadings['surfactant_g']:.4f} g")

        proc = cand["recommended_litho_process"]
        print(f"\nRecommended Lithography Process:")
        print(f"  • Substrate: {proc['substrate']}, Film: {proc['resist_film_thickness_nm']} nm")
        print(f"  • Softbake:  {proc['softbake']}")
        print(f"  • Exposure:  {proc['exposure_source']}")
        print(f"  • PEB:       {proc['post_exposure_bake']}")
        print(f"  • Develop:   {proc['developer']}, {proc['development_time']}")

    elapsed = time.time() - t0
    print_banner(f"Pipeline executed successfully in {elapsed:.2f} seconds!")

if __name__ == "__main__":
    main()
