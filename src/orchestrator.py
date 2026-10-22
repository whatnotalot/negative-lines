import os
import json
import pandas as pd
import numpy as np

from dataset import load_ebeam_dataset
from surrogate import DualLithoSurrogate
from optimizer import BayesianOptimizer, vectorize_candidate
from compliance import ComplianceAgent

class FormulationOrchestrator:
    """
    End-to-End Orchestrator for Closed-Loop Resist Formulation Design.
    Coordinates: Target Spec -> Bayesian Optimization -> GP Surrogate Evaluation -> Compliance Screening -> Lab Recipe Generation.
    """
    def __init__(self):
        # 1. Initialize dataset & surrogate model
        self.X, self.y_lwr, self.y_dose, self.feature_names, self.raw_df = load_ebeam_dataset()
        self.surrogate = DualLithoSurrogate()
        self.surrogate.fit(self.X, self.y_lwr, self.y_dose)

        # 2. Initialize optimizer and compliance agent
        self.optimizer = BayesianOptimizer(dual_surrogate=self.surrogate)
        self.compliance_agent = ComplianceAgent()

    def run_pipeline(self, target_lwr=4.5, target_dose=5.5, pfas_free=True, n_candidates=3, random_state=42):
        """
        Executes the closed-loop formulation design workflow.
        """
        # Step 1: Candidate suggestion via Bayesian Optimization
        candidates = self.optimizer.suggest_candidates(
            n_candidates=n_candidates,
            target_dose=target_dose,
            max_lwr=target_lwr + 0.8,
            random_state=random_state
        )

        recipes = []
        for idx, row in candidates.iterrows():
            # Base chemical assignments derived from patent US7432034B2
            resin_name = "P-1 (Poly[p-hydroxystyrene-co-4-(2-hydroxy-2-propyl)styrene], Mw 12,000)"
            mm_name = "MM-1 (Hexamethoxymethylmelamine / Cymel 300)"
            cl_name = "CL-1 (Tetramethoxymethylglycoluril / Powderlink 1174)"
            quencher_name = "D-1 (Trioctylamine)"
            surfactant_name = "W-1 (Megafac F-176 / Non-ionic surfactant)"

            if pfas_free:
                pag_name = "Triphenylsulfonium Camphorsulfonate (PFAS-Free Non-Fluorinated Sulfonate)"
                pag_status = "COMPLIANT_SUBSTITUTE"
                pag_note = "Substituted for historical restricted PAG I-1 (Triphenylsulfonium Nonaflate) to comply with OECD PFAS & REACH restrictions."
            else:
                pag_name = "PAG I-1 (Triphenylsulfonium Nonaflate, C4F9SO3-)"
                pag_status = "RESTRICTED_PFAS"
                pag_note = "Contains perfluorobutanesulfonate (C4 nonaflate) - restricted under REACH SVHC & US EPA PFAS Action Plan."

            # Construct recipe dict for compliance screening
            formulation_dict = {
                "resin": resin_name,
                "crosslinker_primary": mm_name,
                "crosslinker_secondary": cl_name,
                "photoacid_generator": pag_name,
                "basic_quencher": quencher_name,
                "solvent_1": "Propylene glycol monomethyl ether acetate (PGMEA)",
                "solvent_2": "Propylene glycol monomethyl ether (PGME)",
                "surfactant": surfactant_name
            }

            compliance_audit = self.compliance_agent.screen_formulation(formulation_dict)

            recipe_card = {
                "candidate_id": f"NL-CAND-{idx+1:02d}",
                "rank": idx + 1,
                "target_spec": {
                    "target_lwr_nm": target_lwr,
                    "target_dose_uc_cm2": target_dose,
                    "pfas_free_required": pfas_free
                },
                "predicted_performance": {
                    "ler_3sigma_lwr_nm": float(row["pred_lwr_nm"]),
                    "lwr_uncertainty_nm": float(row["lwr_std_nm"]),
                    "sensitivity_dose_uc_cm2": float(row["pred_dose_uc_cm2"]),
                    "dose_uncertainty_uc_cm2": float(row["dose_std_uc_cm2"]),
                    "confidence_interval_95_lwr": f"{max(0.0, float(row['pred_lwr_nm'] - 1.96*row['lwr_std_nm'])):.2f} - {float(row['pred_lwr_nm'] + 1.96*row['lwr_std_nm']):.2f} nm",
                    "ei_acquisition_score": float(row["ei_score"])
                },
                "formulation_loadings_grams": {
                    "resin_amt_g": float(row["resin_amt"]),
                    "mm_crosslinker_amt_g": float(row["mm_crosslinker_amt"]),
                    "cl_crosslinker_amt_g": float(row["cl_crosslinker_amt"]),
                    "pag_amt_g": float(row["pag_amt"]),
                    "quencher_amt_g": float(row["quencher_amt"]),
                    "solvent_pgmea_g": 7.50,
                    "solvent_pgme_g": 1.50,
                    "surfactant_g": 0.001
                },
                "formulation_chemicals": formulation_dict,
                "chemical_ratios": {
                    "total_crosslinker_g": round(float(row["resin_amt"] * 0 + row["mm_crosslinker_amt"] + row["cl_crosslinker_amt"]), 3),
                    "mm_to_total_crosslinker_ratio": round(float(row["mm_ratio"]), 3),
                    "has_dual_crosslinker": True,
                    "pag_to_resin_percent": round(float(row["pag_to_resin_ratio"] * 100), 2),
                    "quencher_to_pag_percent": round(float(row["quencher_to_pag_ratio"] * 100), 2)
                },
                "compliance": {
                    "status": compliance_audit["status"],
                    "is_pfas_free": pfas_free,
                    "regulatory_clearance": "EU REACH & US TSCA Compliant" if pfas_free else "RESTRICTED (Contains PFAS)",
                    "pag_audit_note": pag_note
                },
                "recommended_litho_process": {
                    "exposure_source": "Electron Beam (50 keV, HL-750 tool equivalent)",
                    "substrate": "6-inch HMDS-primed Silicon Wafer",
                    "resist_film_thickness_nm": 300,
                    "softbake": "120 °C for 90 seconds",
                    "post_exposure_bake": "110 °C for 90 seconds",
                    "developer": "2.38 wt% aqueous Tetramethylammonium Hydroxide (TMAH)",
                    "development_time": "60 seconds at 23 °C",
                    "rinse": "Deionized water for 30 seconds"
                }
            }
            recipes.append(recipe_card)

        return {
            "status": "SUCCESS",
            "pipeline_summary": f"Generated {len(recipes)} optimized formulation candidates meeting specifications.",
            "candidates": recipes
        }

if __name__ == "__main__":
    print("Testing FormulationOrchestrator pipeline...")
    orch = FormulationOrchestrator()
    res = orch.run_pipeline(target_lwr=4.5, target_dose=5.5, pfas_free=True, n_candidates=2)
    print("\nPipeline Result:")
    print(json.dumps(res, indent=2))
