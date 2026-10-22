# Project Negative Lines - Automated Formulation Engine

This directory contains the autonomous, closed-loop Bayesian Optimization and Gaussian Process machine learning engine for negative-tone photoresist formulation design.

---

## Capabilities

1. **Gaussian Process Surrogate Modeling (`src/surrogate.py`)**:
   - Matern 5/2 kernel with WhiteKernel noise estimator.
   - Rigorous Leave-One-Out Cross-Validation (LOOCV) achieving MAE $1.37\text{ nm}$ on Line Edge Roughness (LWR).
   - Simultaneously predicts LWR and sensitivity dose with epistemic uncertainty $\sigma(x)$.

2. **Bayesian Optimization Engine (`src/optimizer.py`)**:
   - Expected Improvement ($\text{EI}$) acquisition function.
   - Retrospective simulation validating that BO reaches target optimum ($LWR \le 4.6\text{ nm}$) in **3–4 iterations**, vs. 10+ iterations for random search.

3. **Regulatory Compliance Agent (`src/compliance.py`)**:
   - Automated screening against OECD PFAS definitions, EU REACH SVHC Annex XVII, and US TSCA.
   - Automatically identifies restricted fluorinated anions (e.g. nonaflate in PAG I-1) and substitutes non-fluorinated green alternatives (Camphorsulfonate or Tosylate).

4. **Closed-Loop Orchestrator (`src/orchestrator.py`, `src/demo.py`)**:
   - Converts target specifications ($LWR \le 4.5\text{ nm}$, Dose $\approx 5.5\ \mu\text{C/cm}^2$, PFAS-free) directly into physical dispensing recipe cards with exact pipetting masses.

5. **Streamlit Web Application (`app.py`)**:
   - Graphical user interface for formulation generation, real-time what-if simulations with uncertainty error bars, and retrospective benchmark curves.

---

## Directory Structure

```
automated/
├── app.py                # Standalone Streamlit application
├── requirements.txt      # Dependencies for this engine
├── README.md             # This documentation
├── data/
│   ├── Negative_Lines_Reconciled_Gold_Set.xlsx  # 10 reconciled patents (239 records)
│   ├── fujifilm_ebeam_dataset.csv     # Extracted 14 standardized 50 keV records
│   └── pfas_registry.json             # OECD/REACH/TSCA restricted chemicals & substitutes
└── src/
    ├── dataset.py        # Feature engineering & dataset loader
    ├── surrogate.py      # GP surrogate model (LOOCV)
    ├── optimizer.py      # Bayesian optimization & retrospective benchmark
    ├── compliance.py     # Regulatory compliance screening
    ├── orchestrator.py   # Multi-agent orchestrator
    ├── demo.py           # CLI demonstration
    └── test_pipeline.py  # Unit test suite
```

---

## Running the Automated Engine

```bash
# Navigate to the automated folder
cd automated

# 1. Run the CLI demonstration
python src/demo.py

# 2. Run the automated test suite
python src/test_pipeline.py

# 3. Launch the Streamlit dashboard
streamlit run app.py
```
