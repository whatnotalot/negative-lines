# Negative Lines · ML & Bayesian optimization

Surrogate models, compliance-aware Bayesian optimization (BO) and a design agent on the reconciled gold set
(10 patents, 239 records), plus a Streamlit studio. Self-contained in `ml_bo/`; it does not touch the root app.

It reads the repo's shared gold set at `../data/Negative_Lines_Reconciled_Gold_Set.xlsx` (set `NEGLINES_GOLD` to use
another workbook).

## Run it

```powershell
cd ml_bo
pip install -r requirements.txt   # Python 3.11
.\run_app.ps1                     # opens http://localhost:8501; computes CV + replay results if missing
.\run_app.ps1 -Rebuild            # recompute results after the gold set changes
```

Without PowerShell: `python -m streamlit run app/streamlit_app.py` from `ml_bo/`. Individual steps:

| Command | Output |
|---|---|
| `python scripts/build_dataset.py` | `data/processed/*.csv`: normalized tables, compliance screen, campaign tables |
| `python scripts/run_cv.py` | `results/cv/`: leave-one-out CV of 5 models × every objective (~1 min) |
| `python scripts/run_replay.py` | `results/replay/`: retrospective BO benchmark, 30 BO / 300 random seeds (~2 min on 16 workers) |
| `python tests/test_app_smoke.py` | renders all 11 pages headlessly through the real navigation, including a planner run and the demo's re-plan toggle |
| `python tests/test_agent.py` | drives the agent loop with a scripted client (no API calls) and runs the planner on three goals |

**Live design agent:** set `ANTHROPIC_API_KEY` before launching. Without it, the Design agent page offers the
rule-based planner, which calls the same tools in a fixed order and is labeled as such. The demo walkthrough and
answers to likely judge questions are in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## What the app adds on top of the models

| Page | What it does |
|---|---|
| Demo tour | Five-step story: the best e-beam resist is not PFAS-free → silicone-surfactant evidence → compliance-aware BO proposal with intervals → live re-plan when the compliance agent flags a PAG → the empty PFAS-free EUV space |
| Design agent | Claude Opus 5.5 plans and calls 8 tools (campaigns, surrogate skill, BO batch, compliance screen, SMILES check, PAG substitutes, dataset search, data gaps) and writes a cited brief; transcript downloadable |
| Bring your own patents | Upload a workbook in the gold-set schema; every patent with a varying numeric outcome becomes a campaign automatically (`neglines/autocampaign.py`) |
| Sidebar: compliance rules | Upload the compliance agent's rules CSV (template downloadable); every page re-screens and BO re-plans with it |

## What is in the data, honestly

The 239 records are not one dataset. They are ten small experiments with different exposure technologies.
Only three patents have quantitative results that vary enough to model, so the work is organized as three
**campaigns** (`neglines/campaigns.py`):

| Campaign | Source | Experiments | Design space | Objectives |
|---|---|---|---|---|
| EUV | TOK US20230314945A1 | 19 (1 failed) | resin × PAG × crosslinker × quencher × developer (4,410 candidates) | Eop, LWR, Z-factor |
| E-beam | FUJIFILM US7432034B2 | 14 | crosslinker-family loadings, PAG (code within family), quencher | LER, sensitivity, resolution, Z |
| SU-8 | FormFactor US20070248896A1 Ex. 8 | 13 conditions × 8 readings | formulation × dose × bake ramp | % vias cracked |

Doses are never compared across families (mJ/cm² vs µC/cm²), as `vocab.yaml` requires. The other seven patents
report constant or qualitative results. They feed compliance and substitution evidence, not regression.

## Findings

1. **Patents only publish wins.** 82% of records are positive examples and 29 of 73 metric series never vary.
   The 43 comparative examples carry most of the information.
2. **Structure-aware kernels matter.** With an additive GP (one kernel per factor group, hierarchical for PAG
   code within family), FUJIFILM LER reaches leave-one-out Q² = 0.76, against 0.09 for a standard ARD GP and 0.12
   for a random forest. Its largest relevance weight lands on "two crosslinker families mixed", which is the
   patent's own claim.
3. **BO pays off where the surrogate has skill.** In the replay, BO reaches the best SU-8 condition in a median of
   4 experiments (random: 7) and the best e-beam Z-factor in 5 (random: 7). On EUV, where LWR is not predictable
   from 18 points (Q² ≈ 0), it gives no gain (10 vs 10).
4. **PFAS sits where the performance is.** Every EUV PAG is flagged (QC sheet). All 17 FUJIFILM records also
   contain Megafac F176, a fluorosurfactant that the QC sheet did not flag. The PFAS-free EUV design space in
   this dataset is empty: that is a data gap, not an optimization problem.
5. **Substitution evidence.** In WO2004107052A1, 10 silicone-surfactant embodiments coat as well as 41
   fluorosurfactant ones. For PAG anions no such evidence exists. The best fluorine-free sulfonate in the anion
   library reaches 0.30 "acid-site pull" against 0.97 for nonaflate (structure-only proxy, see below).
6. **The best SU-8 crack reduction relies on DOP**, a phthalate (likely DEHP, REACH SVHC).

## Modules

| Module | Role |
|---|---|
| `neglines/data.py` | Loads the workbook, converts units (µm→nm for resolution under `*_nm` metrics), computes phr amounts and outcome classes, and reports data issues |
| `neglines/compliance.py` | `DefaultScreener` with QC-sheet, product-family and OECD-2021 SMILES rules. **Pluggable:** any object with `screen(components, doc_id) -> ScreenResult` replaces it |
| `neglines/campaigns.py` | Typed design spaces, encoders, candidate grids, component lists for screening |
| `neglines/gp.py` | BoTorch/GPyTorch GPs (additive, additive+interaction, ARD) and leave-one-out CV |
| `neglines/bo.py` | Pool-based replay (LogEI / qLogNEHVI vs random vs patent order) and prospective batch design with compliance penalties, known-failure exclusion and nearest-example citations |
| `neglines/rls.py` | Z-factor (Wallow et al. 2008), Pareto masks, hypervolume |
| `neglines/anions.py` | PAG anion library with RDKit descriptors and nearest PFAS-free substitutes |
| `neglines/agent.py` | Design agent: tool definitions, manual tool-use loop on `claude-opus-5-5` (adaptive thinking, server-side refusal fallback), and the offline rule-based planner |
| `neglines/autocampaign.py` | Builds a campaign from any patent: varying component identities and loadings, process settings, best-covered numeric outcomes |
| `neglines/gaps.py` | Extraction worklist and PAG coverage, shared by the app and the agent |
| `app/` | Streamlit studio: overview, atlas, data gaps, RLS frontier, surrogate lab, BO replay, design studio, anion map |

## Interfaces for the team

- **Extraction:** the Data gaps page exports a prioritized worklist (`extraction_worklist.csv`) with search
  queries. Top items are EUV sources with non-fluorinated PAGs, and SMILES for the 10 unverified FUJIFILM PAG codes.
- **Compliance:** either pass your agent as a `Screener` in code, or export its findings as a CSV with the
  columns of `data/compliance_rules_template.csv` (`TableScreener`) and upload it in the app sidebar. Its flags
  drive the `block` / `penalize` / `watch` penalties in `bo.propose`.
- **Integration:** the Design studio downloads a Markdown design brief per batch. It includes predictions with 95%
  intervals, the closest tested example with its patent location, and compliance rationale with substitutes.

## Limits

- Each campaign has 13 to 19 experiments, so predictions are local to each patent's chemistry. There is no
  cross-patent transfer, because components are patent-local codes until `smiles` is filled.
- The anion map is a structure-only heuristic (size and an electron-withdrawing proxy), not a trained model.
- The retrospective replay uses each pool's worst observed value as the hypervolume reference point.
- Compliance output is a screening aid, not legal advice. Product-family identities (e.g. Megaface F-series,
  BYK-3xx, "DOP", "MCA") must be confirmed on SDS/CAS.

## Data issues found (send to extraction)

Computed on every load (`GoldSet.issues`, also on the Atlas page):

- **Counts disagree:**
  - The README sheet says 240 records, 1285 components, 858 results and 112 reconciliation items.
  - The Summary total says 239, 1335, 928 and 80.
  - The actual rows are 239, 1284, 857 and 78.
- **Mislabeled units:** US7432034B2 resolution is stored under `resolution_min_cd_nm` in µm.
- **Missing exposure fields:** 21 CN120370628A records have `dose_unit = "mJ"` with no area. `dose_type` and
  `intensity_mw_cm2` are never populated.
- **Split group statements:** in CN120370628A, outcomes like "good adhesion" and "poor adhesion" are separate
  metrics, so no series varies.
