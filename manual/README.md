# Project Negative Lines - Manual Formulation & Labeling Track

This directory is designated for the manual formulation workflows, step-by-step evaluation utilities, and hand-annotated labeling tools.

---

## Intended Purpose

- **Manual Recipe Entry & Formulations:** Tools for domain chemists to manually enter or edit formulation components and verify mass balances.
- **Manual Compliance Checklist:** Interactive or spreadsheet-based manual checklists for REACH/TSCA and solvent substitution.
- **Human-in-the-Loop Validation:** Comparing manual formulation hypotheses against the automated Bayesian Optimization recommendations in `automated/`.

---

## Directory Organization

Teammates working on the manual track can place their scripts, spreadsheets, or manual Streamlit app directly inside this folder without causing any merge conflicts with the automated engine:

```
manual/
├── README.md             # This guide
├── app.py                # (Optional) Manual formulation calculator or UI
├── data/                 # Manual test cases and worksheets
└── src/                  # Manual utilities and scripts
```
