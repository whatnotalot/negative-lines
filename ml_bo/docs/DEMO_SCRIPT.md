# Demo script · Negative Lines ML & BO (about 3 minutes)

## Before you present

1. `.\run_app.ps1` (opens http://localhost:8501). For the live agent, set the key first:
   `$env:ANTHROPIC_API_KEY = "sk-ant-..."; .\run_app.ps1`
2. Open **Demo tour** once and flip the III-1 toggle on and off. The first visit computes and caches the proposals
   (about 15 s); after that the page is instant, even after a restart.
3. On **Design agent**, run the "PFAS-reduced e-beam resist" goal once and keep the transcript download as a backup.
4. No network or no key? Use the **Rule-based planner** engine. It calls the same tools and says so on screen.

## Run of show

| Time | Page | Say | Click |
|---|---|---|---|
| 0:00 | Overview | "Patents only publish wins: 82% of our 239 records are positive examples. And the best-performing resists are exactly the ones regulators are coming for." | Point at the five findings |
| 0:25 | Demo tour, step 1–2 | "The best e-beam resist in our open dataset contains a fluorosurfactant. But another patent in the same dataset already shows silicone surfactants coat just as well." | Scroll |
| 0:50 | Demo tour, step 3 | "Compliance-aware Bayesian optimization proposes a formulation predicted to beat the best tested example, with 95% intervals and a citation to the closest real example." | Hover proposal #1 |
| 1:15 | Demo tour, step 3 | "Now the compliance agent flags one PAG as PFAS. BO re-plans in seconds." | Flip the III-1 toggle |
| 1:35 | BO replay | "Is BO worth it on 14 experiments? Replaying the patents: SU-8 best condition in 4 experiments instead of 7. And where the surrogate can't predict, on EUV, BO gives no gain. We show that." | SU-8, then EUV |
| 2:05 | Design agent | "The design agent does this end to end: it checks surrogate skill, runs BO, looks for substitution evidence and writes a cited brief." | Run the e-beam goal (or show the saved transcript) |
| 2:35 | Demo tour, step 5 | "On EUV the PFAS-free design space is empty. We say so, and turn it into an extraction query. New patents flow straight in: upload, and they become a campaign automatically." | Point at the worklist link |
| 2:55 | — | "Dataset, code and every agent transcript are open." | — |

## Questions judges are likely to ask

**How much data is this?** 239 records from 10 patents, but only three patents have numeric outcomes that vary
(13–19 experiments each). We model per patent and say so; there is no cross-patent model until structures (SMILES)
are extracted.

**Can you trust a GP on 14 points?** We report leave-one-out validation for every objective. FUJIFILM LER: Q² 0.76
with an additive kernel vs 0.09 for a standard GP. EUV LWR: about 0, and we flag those predictions as unreliable.

**Is the BO gain real?** It is a retrospective replay over each patent's own examples: 30 BO seeds, 300 random, plus
the patent's own order. Gains appear only where the surrogate has skill, which is the expected behavior.

**Is the proposal actually PFAS-free?** It has no PFAS flag, but the PAG and quencher structures are not in the
dataset, so they are "unverified", and the app says so. The surfactant swap is supported by coating data from another
patent, not yet by lithography data.

**Is the compliance output legal advice?** No. It is a screening aid with the source and confidence of every flag. The
team's compliance agent can replace or extend the rules (sidebar upload).

**What happens when extraction adds patents?** Upload the workbook on "Bring your own patents": any patent whose
examples vary something and report a numeric outcome becomes a campaign with validation and proposals.

**Why Claude?** The agent decides which tools to call and writes the brief; every number must come from a tool result,
and the transcript shows each call. It runs Claude Opus 5.5 with adaptive thinking and server-side refusal fallback.
