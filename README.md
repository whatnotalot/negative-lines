# Project Negative Lines

AI agents that mine patents and papers to build the first open dataset of negative photoresist formulations, then design new formulations that hit a performance target and stay PFAS-free and regulation-ready.

Built at the [OSI Hackathon](https://llmhackathon.github.io/) (October 21–22, 2026) in the **Molecular and Material Design** track.

![Project Negative Lines team card](docs/negative-lines-card.png)

## Why

Negative photoresists pattern semiconductor chips, MEMS, microfluidics, and nanostructures. Their formulation is still largely trial and error:

- **No open data.** Recipes (resin, crosslinker, photoacid generator, quencher, solvent) and their lithographic performance are scattered across patents and papers in inconsistent units.
- **Costly iteration.** Sensitivity, resolution, and line-edge roughness (LWR) trade off against each other, and every iteration costs coating, exposure, and SEM time.
- **Regulatory pressure.** Many photoacid generators use PFAS anions (e.g. nonaflates, perfluoroalkyl sulfonates), and some common solvents are restricted under EU REACH and US TSCA. New formulations must perform *and* comply.

---

## System Architecture

```
                    ┌────────────────────────┐
                    │  Target Specification  │
                    │ (LWR <= 4.5 nm, PFAS=0)│
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  Bayesian Optimizer    │ ◄─── Engineered Features
                    │ (Expected Improvement) │      (Dual Crosslinkers,
                    └───────────┬────────────┘       PAG-to-Resin Ratio)
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Dual Litho Surrogate   │
                    │ (Gaussian Process +    │ ───► Predicted LWR & Dose
                    │  Epistemic Uncertainty)│      (with 95% Confidence)
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │    Compliance Agent    │ ───► Automatic PFAS Substitution
                    │ (OECD PFAS, REACH/TSCA)│      (Nonaflate -> Camphorsulfonate)
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Dispensing Recipe Card │
                    │ (Mass loadings, PEB,   │
                    │  TMAH developer steps) │
                    └────────────────────────┘
```

---

## Hackathon Deliverables

- [x] **Reconciled Master Gold Set**: 10 patents, 239 formulation records, 1,285 components, and 858 lithography results ([`data/Negative_Lines_Reconciled_Gold_Set.xlsx`](data/Negative_Lines_Reconciled_Gold_Set.xlsx)).
- [x] **Benchmarked E-Beam Lithography Dataset**: 14 standardized records from US7432034B2 under identical 50 keV tool conditions on 6-inch Si wafers ([`data/fujifilm_ebeam_dataset.csv`](data/fujifilm_ebeam_dataset.csv)).
- [x] **Gaussian Process Surrogate Model**: Matern 5/2 kernel with Leave-One-Out Cross-Validation (LOOCV), predicting LWR ($R^2 = 0.20$, MAE $1.37\text{ nm}$) and sensitivity dose with epistemic variance $\sigma(x)$ ([`src/surrogate.py`](src/surrogate.py)).
- [x] **Bayesian Optimization Design Engine**: Expected Improvement (EI) candidate generation and retrospective simulation proving 3x-4x sample efficiency advantage over random search ([`src/optimizer.py`](src/optimizer.py)).
- [x] **Compliance Agent**: Automated screening against OECD PFAS definitions, EU REACH Annex XVII, and US TSCA, with automatic non-fluorinated green substitutes (e.g., Camphorsulfonate / Tosylate) ([`src/compliance.py`](src/compliance.py)).
- [x] **Closed-Loop Multi-Agent Orchestrator**: End-to-end target spec to dispensing recipe generator ([`src/orchestrator.py`](src/orchestrator.py), [`src/demo.py`](src/demo.py)).
- [x] **Interactive Streamlit Web Dashboard**: Graphical interface for recipe generation, what-if sensitivity simulations, and retrospective validation curves ([`app.py`](app.py)).
- [x] **Automated Test Suite**: 7-point unit test suite verifying data integrity, model fitting, and agent execution ([`src/test_pipeline.py`](src/test_pipeline.py)).

---

## Quickstart

### 1. Requirements & Setup

The entire pipeline runs on any machine (including Apple Silicon M1/M2/M3 MacBooks or Linux/Windows) with zero GPU requirement:

```bash
# Clone the repository
git clone https://github.com/whatnotalot/negative-lines.git
cd negative-lines

# Install lightweight dependencies
pip install -r requirements.txt
```

### 2. Run the End-to-End CLI Demo

Execute the multi-agent pipeline in the terminal:

```bash
python src/demo.py
```

### 3. Run the Automated Test Suite

```bash
python src/test_pipeline.py
```

### 4. Launch the Interactive Streamlit Dashboard Locally

```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Deploy to Streamlit Community Cloud

This repository is pre-configured for 1-click cloud deployment:

1. Push your changes to GitHub repository `whatnotalot/negative-lines`.
2. Visit [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub account and select:
   - **Repository:** `whatnotalot/negative-lines`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **Deploy!** Streamlit Community Cloud will automatically install `requirements.txt` and serve the dashboard globally.

---

## Repository Layout

```
.
├── README.md                          # Project documentation and quickstart
├── requirements.txt                   # Production dependencies
├── app.py                             # Interactive Streamlit web application
├── vocab.yaml                         # Controlled vocabulary & record schema
├── data/
│   ├── Negative_Lines_Reconciled_Gold_Set.xlsx  # 10 reconciled patents (239 records)
│   ├── fujifilm_ebeam_dataset.csv     # Extracted 14 standardized 50 keV records
│   └── pfas_registry.json             # OECD/REACH/TSCA restricted chemicals & substitutes
├── src/
│   ├── dataset.py                     # Feature engineering and dataset loader
│   ├── surrogate.py                   # Gaussian Process surrogate model (LOOCV)
│   ├── optimizer.py                   # Bayesian Optimization & retrospective benchmark
│   ├── compliance.py                  # Chemical regulatory screening agent
│   ├── orchestrator.py                # Closed-loop multi-agent workflow
│   ├── demo.py                        # Terminal end-to-end pipeline demonstration
│   └── test_pipeline.py               # Unit test suite
└── docs/
    ├── hand-labeling-guide.md         # Gold set annotation protocol
    ├── negative-lines-card.png
    └── negative-lines-card.svg
```

---

## Key Technical Findings

1. **Dual-Crosslinker Synergism in Negative-Tone Resists (`US7432034B2`):**
   - Single-crosslinker comparative formulations suffer severe phase separation and roughness jumps ($LWR = 10.5 - 13.8\text{ nm}$).
   - Dual-crosslinker formulations combining melamine derivatives (MM-1 Cymel) and glycoluril derivatives (CL-1 Powderlink) achieve tight networks ($LWR = 4.5 - 6.2\text{ nm}$).
2. **PFAS-Free Drop-In Substitution:**
   - Historical photoacid generators (such as PAG I-1, Triphenylsulfonium Nonaflate) utilize $C_4F_9SO_3^-$, an environmentally persistent perfluorinated anion restricted under REACH SVHC and US EPA PFAS rules.
   - The compliance agent substitutes non-fluorinated Triphenylsulfonium Camphorsulfonate, preserving high thermal stability and low acid diffusion without environmental persistence.
3. **Sample Efficiency:**
   - Retrospective simulation on patent records proves Bayesian Optimization discovers optimal low-LWR formulations in **3–4 experiments**, compared to 10+ for unguided random search.

---

## Disclaimer

The compliance agent is an automated screening aid for chemical research, not formal legal counsel. Always verify current regulatory updates with ECHA and EPA inventories.

## License

[MIT](LICENSE)
