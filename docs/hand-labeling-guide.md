# Project Negative Lines hand-labeling guide

Oct 21, 2026 · @Prem

## Purpose and workflow

Two people label the same \~10 documents by hand. The reconciled result is the gold set used to score the extraction agent. A gold set is only useful if it records what the source says, so this guide is about consistency, not chemistry judgement.

1. **Pick documents** — about 4 patents, 4 papers and 2 datasheets, including hard cases: codenamed ingredients, comparative examples, parts-per-hundred amounts, qualitative grades, several formulations in one table.
2. **Label independently** — each labeler fills the record template alone. No discussion until both are done.
3. **Reconcile** — compare field by field, agree on the correct value, and log every disagreement with its cause (section *Reconciliation*).
4. **Split** — at most 2 documents may become worked examples in the extraction prompt. The other 8 are held out for scoring only and must never be shown to the agent.
5. **Freeze** — once scoring starts, gold records only change to fix a proven labeling error, and that fix is logged.

## Golden rules

If you remember nothing else, follow these six rules. They prevent most disagreements.

1. **Copy, don't convert.** Enter `amount_raw`, `dose`, temperatures and times exactly as printed, with the unit and basis the source uses. Normalized values (`amount_wt_pct_solids`, SI units) are computed later by code, never by hand.
2. **Missing is `null`, never `0`.** If the source doesn't state a value, leave it empty. Zero means "measured and found to be zero".
3. **Don't fill gaps from knowledge.** Even if you know SU-8 is usually soft-baked at 95 °C, record only what this document says. Put your knowledge in `labeler_note` if useful.
4. **Names as written.** Copy `name_as_written` verbatim, including codenames like "PAG-2". Resolving to a structure, CAS or SMILES is a separate lookup step.
5. **Every value has a location.** Fill `location` (page, table, example number) and paste a short `evidence_snippet` for the record. A value you can't point to doesn't go in.
6. **When unsure, flag it.** Choose the best value, set `labeler_confidence` to `low`, and explain in `labeler_note`. Never silently guess.

## Record boundaries

One record = one formulation, processed one way, with its results. Most disagreements in practice come from splitting records differently, so agree on boundaries before filling fields.

| Situation in the source | How to record it |
| --- | --- |
| Patent Examples 1–5 and Comparative Examples 1–2 in one table | One record per example; set `is_comparative: true` on the comparative ones |
| Same formulation exposed at 3 doses, results at each | Three records sharing the same `components`, one dose each |
| Same formulation, one process, several metrics (dose, resolution, LER) | One record with several entries in `results` |
| A process-condition table that applies to all examples ("unless otherwise stated") | Copy those conditions into every record it covers; cite the shared table in `location` |
| A sweep shown only in a figure (e.g. contrast curve) | One record; enter only values stated in text or tables. Note "figure-only data" in `labeler_note` rather than reading values off a plot |
| Codenamed ingredient ("Resin A", "PAG-2") defined in a synthesis section | `name_as_written` = the codename; put the definition you found in `definition_location` |
| Codename never defined | Keep the codename, set `labeler_confidence: low` |
| Commercial product ("SU-8 2010", "ma-N 2403") with no composition given | One record with a single component, `role: product`, and the trade name. Don't fill in a composition from datasheets you know |

**Record ID** = `<doc_id>_<example label>`, e.g. `JP2019123456A_ex3`, `JP2019123456A_cex1`. Both labelers must use the same IDs so records can be matched.

## Components and roles

Assign the role the **source** gives the ingredient. If the source gives none, use the function it plays in this formulation, and add a note.

| Role | Typical examples | Watch out for |
| --- | --- | --- |
| `resin` | Epoxy novolac (SU-8), novolac, poly(hydroxystyrene) | A resin that also carries crosslinkable groups is still `resin` |
| `crosslinker` | Melamine (HMMM), glycoluril (TMMGU), multifunctional epoxides or oxetanes | In SU-8 the resin crosslinks itself, so there may be no separate crosslinker |
| `pag` | Triarylsulfonium salts, iodonium salts, non-ionic oxime sulfonates | Record the whole salt name; the compliance agent needs the anion |
| `quencher` | Trioctylamine, other amines, photodecomposable bases | Sometimes called "base", "acid diffusion control agent" or "basic compound" |
| `sensitizer` | Anthracene derivatives, thioxanthones | Distinct from a PAG: it absorbs light and transfers energy |
| `photoinitiator` | Radical initiators in acrylate negative resists | Use for radical systems; `pag` for acid-catalysed ones |
| `monomer` | Multifunctional acrylates in radical systems |  |
| `metal_oxo_cluster` | Sn-oxo or Hf-oxo clusters in EUV metal-oxide resists |  |
| `solvent` | PGMEA, cyclopentanone, GBL, ethyl lactate | Mixed solvents: one component per solvent, with its ratio |
| `surfactant`, `adhesion_promoter`, `additive` | Fluorosurfactants, silanes, dyes | Unsure? Use `additive` with a note |
| `product` | "SU-8 2010", "ma-N 2403" | Only for commercial products whose composition is not given |
| `other` | Anything else | Always fill `role_other_text` |

The `product` role is not yet in `vocab.yaml` v1. Add it if the team agrees.

**Polymers.** If the source gives them, fill `repeat_units` as text (e.g. "hydroxystyrene / styrene"), `monomer_ratio` exactly as printed ("70/30 mol"), `mw` and `pdi`. Don't draw SMILES by hand.

## Amounts: why the same PAG can be "3", "2.65 %" and "0.19 %"

Always record `amount_raw` and `amount_basis` exactly as printed. The same quantity looks completely different depending on what it is a percentage *of*, and a wrong basis is the most damaging labeling error because the number still looks plausible.

### Basis values

| Source wording | `amount_basis` | What it means |
| --- | --- | --- |
| "100 parts by mass of resin, 3 parts of PAG" | `parts_per_100_resin` | Mass relative to 100 mass units of resin (phr) |
| "5 wt% relative to the resin", "based on polymer", "per resin solids" | `parts_per_100_resin` | Same thing as phr, even though it says wt%. Record 5 |
| "PAG: 2.5 wt% of solids", "in the solid content" | `wt_pct_solids` | Fraction of all non-solvent ingredients |
| "composition (wt%)" table including the solvent, summing to 100 | `wt_pct_total` | Fraction of the whole solution, solvent included |
| "0.1 mol% relative to PAG", "0.2 eq. to PAG" | `mol_pct_vs_pag` or `mol_eq_vs_pag` | Quencher loading relative to PAG moles |
| "0.05 mmol/g" | `mmol_per_g_solids` | Molar loading per gram of solids (check the denominator) |
| "2 % w/v", "g per 100 mL" | `w_v_pct` | Mass per volume; not convertible without density |
| "%" with no further explanation | `unspecified` | Set `labeler_confidence: low` and note the ambiguity |

### Solution concentration is not a component

Phrases like "dissolved in PGMEA to a solids content of 30 wt%" go in the record-level field `solids_content_wt_pct` (30). The solvent is still a component with `role: solvent`, but its `amount_raw` stays `null` unless the source gives it directly (e.g. "1500 parts PGMEA").

### Worked example

A patent lists: resin 100 parts, crosslinker 10 parts, PAG 3 parts, quencher 0.3 parts, PGMEA 1500 parts. Code (not you) will compute:

| Ingredient | As printed (phr) | wt% of solids | wt% of total solution |
| --- | --- | --- | --- |
| Resin | 100 | 88.3 | 6.20 |
| Crosslinker | 10 | 8.83 | 0.62 |
| PAG | 3 | 2.65 | 0.19 |
| Quencher | 0.3 | 0.26 | 0.02 |
| PGMEA | 1500 | — | 92.98 |

Solids total 113.3 parts; the whole solution is 1613.3 parts. One PAG loading, three very different numbers. You enter only the first column.

### Common traps

- **"wt%" that is really phr.** Check the denominator wording: "relative to", "based on" or "per" the resin or polymer means phr.
- **Columns that don't sum to 100.** A composition table whose solids add to more than 100 is almost certainly in parts, not percent.
- **Mixed solvents.** "PGMEA/PGME = 7/3 (mass ratio)" → two solvent components, `amount_raw` 7 and 3, `amount_basis: solvent_mass_ratio`.
- **Ranges.** "1–10 parts, preferably 3" in claims is not a formulation. Only label the specific value used in a worked example.
- **Polymer composition.** Monomer ratios inside a resin ("70/30 mol") belong in `monomer_ratio`, not in the formulation amounts.
- **Mass vs mole.** "mol%" is never wt%. Keep the unit as printed.

## Dose and sensitivity: same word, different measurements

"Sensitivity 20 mJ/cm²" can mean at least four different doses. Record the metric the source actually measured, and copy its wording into `metric_as_written` so reconciliation can check it.

### Dose units and exposure sources

| Exposure | Unit to expect | Also record |
| --- | --- | --- |
| i-line (365 nm), g/h-line, broadband UV | mJ/cm² | `dose_meter_wavelength_nm` if stated (broadband tools are often metered at 365 or 405 nm, which changes the number) |
| KrF (248 nm), ArF (193 nm) | mJ/cm² | Scanner or contact; immersion or dry |
| EUV (13.5 nm) | mJ/cm² | Tool or beamline, e.g. interference lithography |
| Electron beam | µC/cm² (area); also pC/cm (line) or fC (dot) | `ebeam_kv` — the same resist needs a very different dose at 30 kV vs 100 kV |
| Ion beam | ions/cm² | Ion species and energy |

- **Never convert between mJ/cm² and µC/cm².** They measure different things.
- **Intensity × time.** If the source gives "10 mW/cm² for 15 s", record `intensity_mw_cm2: 10` and `exposure_time_s: 15`, and leave `dose` null. Code will compute 150 mJ/cm².
- **Line and dot doses** (pC/cm, fC) are not area doses. Use the matching unit; don't divide by pitch yourself.
- **Set vs measured dose.** If the source distinguishes nominal and measured or effective dose, record the one it reports results against and note the other.

### Which sensitivity metric is it?

Negative resists are characterized by a contrast curve: normalized remaining thickness after development plotted against log dose. Different papers pick different points on that curve.

| `metric` | Definition | Typical wording |
| --- | --- | --- |
| `dose_gel` | Lowest dose at which an insoluble film remains (onset) | "gel dose", "Dg", "Di", "onset", "threshold dose", sometimes "E0" in negative-tone papers |
| `d50` | Dose giving 50% normalized remaining thickness | "D50", "D0.5", "half-thickness dose" |
| `dose_sat` | Dose at which thickness saturates (often 90% or 100%) | "D100", "D0.9", "saturation dose" — record which percentage |
| `sensitivity_esize` | Dose that prints the target feature at nominal size | "Eop", "Esize", "optimum dose", "sizing dose" — also record the target CD and pitch |
| `contrast_gamma` | Slope of the contrast curve | "γ", "contrast" — copy the formula into `definition_as_written`, because papers use different ones |
| `sensitivity_unspecified` | Source says "sensitivity" and gives no definition | Set `labeler_confidence: low` |

**Traps:**

- **E0 in negative tone.** For positive resists E0 is the clearing dose. In negative-tone papers it is sometimes used for the gel dose. Use the source's definition, not the term.
- **Normalization.** "Remaining thickness" may be normalized to the initial film or to the maximum remaining film. Note which if stated.
- **Results at one dose.** If resolution or LER is reported "at 30 mJ/cm²", that 30 is the process dose, not a sensitivity metric. Put it in `process.exposure.dose`.
- **Comparative tables in relative units** ("sensitivity 1.2× that of Example 1") → `value_qualitative`, with the reference record ID.

## Process conditions

Copy each condition with its printed unit. The table lists the canonical unit code will convert to, and the traps that change the number.

| Field | Canonical unit | Traps |
| --- | --- | --- |
| `film_thickness` | nm | Sources mix nm, µm and Å. Thickness before vs after development differs — record which (`thickness_stage`) |
| `softbake_temp`, `softbake_time` | °C, s | Also called prebake, PAB or PB. Two-step bakes (65 °C then 95 °C, common for SU-8) → record both steps in order |
| `peb_temp`, `peb_time` | °C, s | Post-exposure bake. Hot plate vs oven changes the effective time; record `bake_method` if stated |
| `exposure` | see the dose section | Contact, proximity, projection, e-beam, interference |
| `developer.name` | as written | Negative resists use both aqueous (TMAH) and organic (PGMEA, SU-8 developer, n-butyl acetate) developers |
| `developer.concentration` | as written | "2.38 wt% TMAH" and "0.26 N TMAH" are the same; don't convert, just copy |
| `developer.time` | s | "Puddle 60 s" vs "immersion 1 min" — record method if stated |
| `rinse`, `hardbake_temp`, `hardbake_time` | as written, °C, s | Hard bake is optional; null if absent |
| `substrate`, `primer` | as written | e.g. Si with HMDS, glass, SiO₂; "adhesion promoter OmniCoat" is a process step, not a formulation component |

- **Minutes vs seconds.** "1 min" → enter `1` with unit `min`; code converts.
- **"Room temperature"** → enter the text `RT`, not 25.
- **Conditions given as ranges** ("90–110 °C") in a worked example → copy the range as text and set `labeler_confidence: low`.

## Results

Each result is one entry: `metric`, `value` (or `value_qualitative`), `unit`, `condition`, `method`, `metric_as_written`.

| `metric` | Record alongside | Traps |
| --- | --- | --- |
| `resolution_min_cd_nm` | `pitch_nm`, `pattern_type` (line/space, isolated line, dots, pillars, contact holes), `film_thickness` | "Resolution 100 nm" may be the line width or the half-pitch. Copy both CD and pitch if given; if only one number, note which it is |
| `ler_3sigma_nm`, `lwr_3sigma_nm` | `method` (SEM tool, software, frequency range if stated) | LER (one edge) ≠ LWR (width). Some papers report 1σ — enter the printed value and set `sigma: 1` |
| `max_aspect_ratio` | `film_thickness`, CD | Only if stated; don't compute thickness ÷ CD yourself |
| `swelling`, `scum_residue`, `adhesion`, `pattern_collapse`, `profile` | `value_qualitative` + `scale` | Usually qualitative |
| Other metrics (etch resistance, Tg, outgassing) | `metric: other` + `metric_as_written` |  |

### Qualitative grades

Patents often grade results as A/B/C, ◎/○/△/× or 1–5. Record the symbol in `value_qualitative` and copy the patent's definition of the scale into `scale` (e.g. "○: no residue; ×: residue observed"). Don't translate grades into numbers.

### Values only in figures

Don't digitize plots for the gold set. If the only evidence is an SEM image or a curve, add a result with `value: null`, `metric_as_written` and a note such as "Fig. 4 shows 200 nm L/S resolved". If a figure caption states a number, that counts as text.

### Pass/fail statements

"Patterns down to 500 nm were resolved" → `resolution_min_cd_nm: 500`, with `condition: "smallest tested"` if the source suggests they did not try smaller. That tells the model the true limit may be lower.

## Reconciliation

After both labelers finish a document, compare the records field by field. Agree on one value, and log every disagreement in the table below, even trivial ones. The log shows which rules in this guide are unclear and feeds fixes back into `vocab.yaml` and the extraction prompt.

1. **Match records first.** If the record IDs differ, you split the document differently. Settle the boundaries (section *Record boundaries*) before comparing fields.
2. **Go back to the source.** Agree on the value the document supports, not the one that seems most reasonable chemically.
3. **Classify the cause** using one of these codes: `boundary` (records split differently), `basis` (amount basis), `metric_def` (which sensitivity or resolution metric), `unit`, `missed` (one labeler didn't find the value), `typo`, `guide_unclear` (this guide didn't cover the case).
4. **Fix the guide** for every `guide_unclear` case: add a row or trap to the relevant section and tell the other labeler.

| Record ID | Field | Labeler A | Labeler B | Agreed value | Cause | Note |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

**Agreement rate.** Before reconciling, count fields where A and B already agree divided by fields either filled. If it's below about 0.8 for a section, the rules for that section need tightening before you trust the agent's scores there.

## Checklist before submitting a record

- [ ] Record ID follows `<doc_id>_<example label>`; comparative examples flagged
- [ ] `location` and `evidence_snippet` filled
- [ ] Every component has a `role` and `name_as_written` (codenames kept)
- [ ] Every amount has `amount_raw` **and** `amount_basis`; "wt% relative to resin" recorded as `parts_per_100_resin`
- [ ] Solution solids content in `solids_content_wt_pct`, not as a component amount
- [ ] Dose unit as printed; e-beam records have `ebeam_kv`; intensity × time not multiplied out
- [ ] Each sensitivity value has the right `metric` (gel dose, D50, saturation, Esize) and `metric_as_written`
- [ ] Resolution has CD and pitch (or a note saying which one was given)
- [ ] Qualitative grades copied with their `scale`
- [ ] No values from memory, plots or other documents; missing values are `null`
- [ ] Low-confidence fields flagged with a `labeler_note`
