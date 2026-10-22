"""
Automated Test Suite for Project Negative Lines Pipeline
"""

import unittest
import os
import sys
import warnings
from sklearn.exceptions import ConvergenceWarning
warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import pandas as pd

# Add src to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from dataset import load_ebeam_dataset, extract_fujifilm_ebeam_data
from surrogate import GaussianProcessSurrogate, DualLithoSurrogate
from optimizer import BayesianOptimizer, vectorize_candidate, run_retrospective_simulation, expected_improvement
from compliance import ComplianceAgent
from orchestrator import FormulationOrchestrator

class TestNegativeLinesPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.X, cls.y_lwr, cls.y_dose, cls.feature_names, cls.df = load_ebeam_dataset()

    def test_01_dataset_integrity(self):
        """Verifies the extracted e-beam dataset has 14 records and all 10 feature columns."""
        self.assertEqual(len(self.df), 14, "Expected 14 e-beam records from US7432034B2.")
        self.assertEqual(len(self.feature_names), 10, "Expected 10 engineered feature columns.")
        self.assertTrue(all(col in self.X.columns for col in self.feature_names))
        # Ensure comparative examples have higher LWR
        comp_lwr = self.df[self.df["is_comparative"] == True]["ler_3sigma_nm"].values
        dual_lwr = self.df[self.df["is_comparative"] == False]["ler_3sigma_nm"].values
        self.assertTrue(np.mean(comp_lwr) > np.mean(dual_lwr), "Comparative examples must exhibit higher LWR.")

    def test_02_surrogate_model(self):
        """Verifies Gaussian Process surrogate fits and produces mean and epistemic variance."""
        surrogate = GaussianProcessSurrogate()
        surrogate.fit(self.X, self.y_lwr)
        self.assertTrue(surrogate.is_fitted)

        mu, std = surrogate.predict(self.X.head(2))
        self.assertEqual(len(mu), 2)
        self.assertEqual(len(std), 2)
        self.assertTrue(all(s >= 0 for s in std), "Uncertainties must be non-negative.")

    def test_03_dual_surrogate(self):
        """Verifies dual surrogate simultaneously models LWR and Dose."""
        dual = DualLithoSurrogate()
        dual.fit(self.X, self.y_lwr, self.y_dose)
        preds = dual.predict(self.X.head(3))
        self.assertIn("lwr_mean", preds)
        self.assertIn("dose_mean", preds)
        self.assertEqual(len(preds["lwr_mean"]), 3)

    def test_04_compliance_screening(self):
        """Verifies compliance agent flags nonaflates (PFAS) and accepts camphorsulfonate (PFAS-free)."""
        ca = ComplianceAgent()
        # Nonaflate check
        res_pfas = ca.check_substance("Triphenylsulfonium nonaflate")
        self.assertFalse(res_pfas["is_compliant"], "Nonaflate must be flagged as PFAS.")
        self.assertIn("PFAS", res_pfas["category"])

        # Camphorsulfonate check
        res_green = ca.check_substance("Triphenylsulfonium camphorsulfonate")
        self.assertTrue(res_green["is_compliant"], "Camphorsulfonate must be compliant.")

    def test_05_bayesian_optimizer(self):
        """Verifies Bayesian optimizer generates ranked candidates within physical parameter bounds."""
        opt = BayesianOptimizer()
        cands = opt.suggest_candidates(n_candidates=3, target_dose=5.5)
        self.assertEqual(len(cands), 3)
        self.assertTrue(all(cands["pred_lwr_nm"] > 0))
        self.assertTrue(all(cands["has_dual_crosslinker"] == 1))

    def test_06_retrospective_simulation(self):
        """Verifies retrospective simulation completes and computes valid trajectory statistics."""
        sim = run_retrospective_simulation(n_trials=5)
        self.assertIn("bo_mean", sim)
        self.assertIn("rand_mean", sim)
        self.assertEqual(len(sim["bo_mean"]), len(sim["steps"]))
        self.assertLessEqual(sim["bo_mean"][-1], sim["bo_mean"][0], "BO trajectory should be monotonically non-increasing.")

    def test_07_orchestrator_pipeline(self):
        """Verifies end-to-end multi-agent orchestration generates complete recipe cards."""
        orch = FormulationOrchestrator()
        result = orch.run_pipeline(target_lwr=4.5, target_dose=5.5, pfas_free=True, n_candidates=2)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(len(result["candidates"]), 2)
        card = result["candidates"][0]
        self.assertEqual(card["compliance"]["status"], "PASS")
        self.assertTrue(card["compliance"]["is_pfas_free"])
        self.assertIn("resin_amt_g", card["formulation_loadings_grams"])

if __name__ == "__main__":
    unittest.main()
