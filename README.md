# Project Negative Lines

AI agents that mine patents and papers to build the first open dataset of negative photoresist formulations, then design new formulations that hit a performance target and stay PFAS-free and regulation-ready.

Built at the [OSI Hackathon](https://llmhackathon.github.io/) (October 21–22, 2026) in the **Molecular and Material Design** track.

![Project Negative Lines team card](docs/negative-lines-card.png)

## Why

Negative photoresists pattern semiconductor chips, MEMS, microfluidics and nanostructures. Their formulation is still largely trial and error:

- **No open data.** Recipes (resin, crosslinker, photoacid generator, quencher, solvent) and their lithographic performance are scattered across patents and papers in inconsistent units.
- **Costly iteration.** Sensitivity, resolution and line-edge roughness trade off against each other, and every iteration costs coating, exposure and SEM time.
- **Regulatory pressure.** Many photoacid generators use PFAS anions, and some common solvents are restricted. New formulations have to perform *and* comply.

## What we are building

| Component | What it does |
| --- | --- |
| Extraction agent | Reads formulation tables in patents, papers and datasheets and turns them into structured, cited records |
| Open dataset | Composition + process + performance records in a shared schema ([`vocab.yaml`](vocab.yaml)) |
| Surrogate model | Predicts performance (dose, resolution, LER) from formulation and process |
| Design agent | Bayesian optimization over formulations, guided by the surrogate, toward a target spec |
| Compliance agent | Screens candidates against PFAS, REACH and TSCA lists, explains flags and suggests substitutes |
| Orchestrator | Takes the target spec, coordinates the agents and assembles the ranked report |

Every candidate from the design agent passes through the compliance agent. Flagged candidates are rejected or penalized, so only compliant formulations reach the ranked output.

## Hackathon deliverables

- [ ] Open formulation dataset: 50–200 records in the agreed schema
- [ ] Gold set of ~10 hand-labeled documents and an extraction accuracy report (precision and recall on held-out documents)
- [ ] Extraction agent with page and table citations
- [ ] Surrogate model + Bayesian optimization design agent
- [ ] Compliance agent with cited rationale and substitutes
- [ ] End-to-end demo, video and slides

## Repository layout

```
.
├── README.md
├── vocab.yaml                 # controlled vocabulary and record schema (v3), source of truth
├── pyproject.toml / uv.lock   # Python project (uv)
├── .env.example               # copy to .env (gitignored) for API keys
├── config/llm.yaml            # LLM provider/model profiles (no secrets)
├── src/negative_lines/
│   ├── config.py              # settings, LLM profile loading, API-key checks
│   ├── vocab.py               # vocab.yaml loader (units, dose families, record fields)
│   └── schema/
│       ├── enums.py           # static Literal mirrors of vocab.yaml
│       ├── refs.py            # SourceRef (paragraph / table-row citations)
│       ├── llm.py             # LLM structured-output models (DocumentMap, ExampleExtraction)
│       ├── record.py          # full dataset record (FormulationRecord)
│       ├── mapping.py         # vocab <-> LLM <-> record field mapping
│       └── validators.py      # labeling-guide rules
├── tests/                     # vocab consistency, strict-schema and validator tests
└── docs/
    ├── hand-labeling-guide.md
    ├── negative-lines-card.png
    └── negative-lines-card.svg
```

## Development

```
pip install uv            # if needed
uv sync                   # create .venv and install
cp .env.example .env      # then set GOOGLE_API_KEY (never commit it)
uv run pytest
```

Select the LLM with `NL_LLM_PROFILE` (profiles in `config/llm.yaml`). Switching provider or model does not change the schema or pipeline.

## Documentation

- [Hand-labeling guide](docs/hand-labeling-guide.md): how to label the gold set, including the different wt% bases and dose definitions
- [`vocab.yaml`](vocab.yaml): the shared contract between the extraction agent, dataset, models and compliance agent

## Team

Organized by Prem. We are looking for people with skills in LLM extraction, polymer chemistry or lithography, ML and Bayesian optimization, chemical regulation, and demo building.

| Role | People | Owns |
| --- | --- | --- |
| Data and extraction | 2 | Extraction agent, dataset, gold set |
| Domain experts | 1–2 | Labeling guide, gold labels, sanity checks |
| Modeling | 1–2 | Surrogate model, Bayesian optimization agent |
| Compliance | 1 | Compliance agent, regulatory list lookups |
| Integration and demo | 1 | Orchestrator, UI, video, slides |

Join us on the hackathon Slack: [team channel](https://app.slack.com/client/T04T81QB7RQ/C04TLL1RSGH).

## Disclaimer

The compliance agent is a screening tool, not legal advice. Regulatory lists change; always check the current official sources.

## License

[MIT](LICENSE)
