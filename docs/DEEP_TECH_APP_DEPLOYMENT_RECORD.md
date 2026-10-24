# Deep-Tech Track Deployment & Architecture Record
**Project Negative Lines · Advanced ML & Bayesian Optimization Studio**  
*Document Version: 1.0 · Last Updated: 2026-10-25*

---

## 1. Executive Summary & Purpose

This record documents the complete deployment architecture, branch provenance, and technical configuration of the **Deep-Tech Track** (`ml_bo`) for Project Negative Lines. It is designed as an offline reference so that any engineer or researcher can reproduce, maintain, or redeploy both versions of the platform in the future.

Project Negative Lines operates as two distinct, parallel tracks:
* **Production Track (`main`)**: Hosted at [https://negativelines.streamlit.app/](https://negativelines.streamlit.app/). Focused on end-to-end user experience, empirical patent ground-truth reconciliation (10 patents, 239 consensus records), dual-track switching (AI engine & chemist lab workbench), and Meyerhofer spin hydrodynamics.
* **Deep-Tech Track (`Madhav-Deep-Tech-track`)**: Hosted at [https://negativelines-bo.streamlit.app/](https://negativelines-bo.streamlit.app/). Focused on structure-aware additive Gaussian Processes ($Q^2 = 0.76$), multi-objective BoTorch hypervolume optimization (`qLogNEHVI`), RDKit molecular descriptors, a 300-seed retrospective replay benchmark, and an autonomous Claude Opus 5.5 formulation design agent.

---

## 2. Git Branch Provenance & Repository Map

* **Remote Repository**: `git@github.com:whatnotalot/negative-lines.git`  
* **Web Repository**: [https://github.com/whatnotalot/negative-lines](https://github.com/whatnotalot/negative-lines)

### Branch Architecture
```
origin/main (Production Track)
  │── Root app.py: Dual-track platform (Automated Engine + Manual Workbench)
  │── manual/: Hand-coded mass balances & Meyerhofer film models
  └── automated/: MVP Gaussian process & regulatory screener

origin/feature/ml-bo-studio (Original Deep-Tech Reference Branch)
  │── Commit: 88db097 (Authored by M. Muthyala <mmuthyala@wisc.edu>, Oct 22, 2026)
  └── Status: 100% UNTOUCHED baseline reference branch.

origin/Madhav-Deep-Tech-track (Active Cloud Deployment Branch)
  │── Base: Branched from feature/ml-bo-studio (88db097)
  │── Commits:
  │     ├── 5b5899d: Added root requirements.txt & root streamlit_app.py
  │     └── 688db4b: Fixed page_link navigation & root views symlink
  └── Status: Active branch deployed to https://negativelines-bo.streamlit.app/
```

---

## 3. Cloud Deployment Settings (Streamlit Community Cloud)

When deploying or recreating the app in [share.streamlit.io](https://share.streamlit.io/):

| Setting | Value |
|---|---|
| **App Name / Subdomain** | `negativelines-bo` (Resolves to `https://negativelines-bo.streamlit.app/`) |
| **Repository** | `whatnotalot/negative-lines` |
| **Branch** | `Madhav-Deep-Tech-track` |
| **Main file path** | `streamlit_app.py` |
| **Python Version** | **`3.11`** (Crucial for BoTorch / GPyTorch pre-compiled wheels) |
| **Secrets (Optional)** | `ANTHROPIC_API_KEY = "sk-..."` *(If omitted, runs built-in offline planner)* |

---

## 4. Key Technical Fixes Implemented for Cloud Hosting

To enable Streamlit Cloud to run the multi-page studio from the repository root without modifying the original code, three key adaptations were engineered:

1. **Root `requirements.txt` Synchronization**:
   Streamlit Cloud installs packages from `/requirements.txt` at the repo root. The root file was updated to include all scientific and chemoinformatic libraries:
   * `botorch>=0.11.0`, `gpytorch>=1.12.0`, `torch>=2.2.0`
   * `rdkit>=2023.9.0`, `scikit-learn>=1.3.0`, `scipy>=1.10.0`
   * `plotly>=5.18.0`, `streamlit>=1.40.0`, `openpyxl>=3.1.0`
   * `anthropic>=0.30.0`

2. **Root Symlink (`views` $\rightarrow$ `ml_bo/app/views`)**:
   Streamlit's internal `pages_manager` resolves relative page links from the directory of the running script. A Git-tracked symbolic link was added at the root level (`views`) pointing to `ml_bo/app/views/`, allowing `st.Page("views/home.py")` and `st.page_link("views/surrogate.py")` to match identical paths.

3. **Defensive Path Resolver in `ml_bo/app/ui.py`**:
   `DeltaGenerator.page_link` was augmented with an interceptor function `_safe_page_link` that dynamically checks all path formats (`page`, `views/<name>`, `ml_bo/app/views/<name>`, and absolute filesystem paths). If Streamlit Cloud experiences an internal navigation cache miss, it gracefully displays the link text rather than throwing an unhandled `StreamlitPageNotFoundError`.

---

## 5. Local Offline Execution Guide

To run the Deep-Tech studio entirely on your local machine without depending on external cloud hosting:

### A. Checkout the Branch
```bash
cd "/Users/technano/agy2-projects/2026.10.OSI Hackathon/Negative Lines"
git checkout Madhav-Deep-Tech-track
```

### B. Activate / Create Virtual Environment (Python 3.11)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### C. Run the Studio Locally
```bash
# Launch directly from repo root:
streamlit run streamlit_app.py

# Or launch directly from the ml_bo subfolder:
cd ml_bo
streamlit run app/streamlit_app.py
```
The app will open at `http://localhost:8501`.

### D. Recomputing CV & Benchmark Results Offline
If the gold dataset is updated in `data/Negative_Lines_Reconciled_Gold_Set.xlsx`, re-run:
```bash
cd ml_bo
python scripts/build_dataset.py   # Normalizes tables and generates campaign tables
python scripts/run_cv.py          # Recomputes leave-one-out cross validation (~1 min)
python scripts/run_replay.py      # Re-runs 300-seed retrospective benchmark (~2 min)
```

---

## 6. Directory Map of the 11-Page Deep-Tech Studio

All studio code lives under `ml_bo/`:

```
ml_bo/
├── app/
│   ├── streamlit_app.py        # Sub-folder launcher
│   ├── ui.py                   # Design tokens, compliance sidebar & safe page_link
│   └── views/
│       ├── home.py             # 1. Overview & headline findings
│       ├── demo.py             # 2. Five-step guided tour of the PFAS cliff
│       ├── atlas.py            # 3. Interactive dataset explorer & issue auditor
│       ├── gaps.py             # 4. Data gaps & prioritized extraction worklist
│       ├── rls.py              # 5. Resolution-LWR-Sensitivity Pareto frontier
│       ├── surrogate.py        # 6. Surrogate lab with Q² and interval coverage
│       ├── replay.py           # 7. BO retrospective replay benchmark (300 seeds)
│       ├── agent.py            # 8. Claude Opus 5.5 design agent & offline planner
│       ├── design.py           # 9. Interactive design studio (qLogNEHVI batching)
│       ├── byod.py             # 10. Bring-Your-Own-Patents auto-campaign generator
│       └── anions.py           # 11. PFAS-free PAG anion map (RDKit molecular space)
├── neglines/
│   ├── agent.py                # Tool loop for Claude Opus 5.5 & rule-based planner
│   ├── anions.py               # RDKit descriptors (size, polar surface, acid-pull proxy)
│   ├── autocampaign.py         # Dynamic campaign inferencing from arbitrary tables
│   ├── bo.py                   # BoTorch qLogNEHVI & LogEI with compliance penalties
│   ├── campaigns.py            # Typed design spaces (TOK EUV, FUJIFILM, SU-8)
│   ├── compliance.py           # Regex, OECD 2021, and CSV-based regulatory screener
│   ├── data.py                 # Ground truth loader, unit normalizer, and QC auditing
│   ├── gaps.py                 # Prioritized extraction queue generator
│   ├── gp.py                   # Additive hierarchical GPyTorch/BoTorch Gaussian Processes
│   ├── paths.py                # Robust data file path resolver
│   └── rls.py                  # Wallow et al. Z-factor and Pareto hypervolume logic
├── results/
│   ├── cv/                     # Precomputed LOOCV predictions & metric tables
│   └── replay/                 # Precomputed 300-seed benchmark traces & summaries
└── docs/
    └── DEMO_SCRIPT.md          # 3-minute presenter guide and judge FAQ handling
```

---

## 7. Core Scientific Metrics & Validation Benchmarks

1. **Structure-Aware Additive Kernel**:
   * Evaluated on FUJIFILM US7432034B2 line-edge roughness.
   * Standard ARD GP: $Q^2 = 0.09$ | Random Forest: $Q^2 = 0.12$.
   * **Additive BoTorch Kernel**: **Leave-One-Out $Q^2 = 0.76$**.
   * Identifies mixing two crosslinker families (melamine + glycoluril) as the dominant physical driver.

2. **300-Seed Retrospective Replay**:
   * SU-8 crack-free via formulation: Reaches optimum in **4 steps** (random: 7).
   * FUJIFILM E-beam Z-factor: Reaches optimum in **5 steps** (random: 7).
   * TOK EUV: Accurately identifies zero predictive gain ($Q^2 \approx 0$) due to small sample space (18 non-failed points).

3. **Regulatory Screening Standard**:
   * Automated flags: OECD 2021 PFAS definition, EU REACH Annex XVII (SVHC), and US TSCA.
   * Substitution library: Camphorsulfonate and alicyclic sulfonates mapped via RDKit steric volume and electronic pull.

---

## 8. Summary of Active URLs for Hackathon

* **Production Track (General Audience & Fabs)**:  
  [https://negativelines.streamlit.app/](https://negativelines.streamlit.app/)
* **Deep-Tech Track (Judges, ML & Chemistry Specialists)**:  
  [https://negativelines-bo.streamlit.app/](https://negativelines-bo.streamlit.app/)
* **Code Repository**:  
  [https://github.com/whatnotalot/negative-lines](https://github.com/whatnotalot/negative-lines)
