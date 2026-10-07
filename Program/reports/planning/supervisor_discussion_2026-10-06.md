# Two-week supervisor discussion plan and Chapter 1 worksheet

Working notes and writing prompts, not text for submission in the Project Report.

Progress update (2026-10-07): the proposed descriptive demonstration is now implemented in `src/demo/`; see [DEMO_GUIDE.md](../../DEMO_GUIDE.md) and the verification notes under `reports/2026-10-07/demo_v1/`. The sections below retain the original 2026-10-06 planning context. No model has been fitted and the two-platform scope remains unapproved. Keep the original approximate 2026-10-20 horizon.

## Confirmed by the student

- Target users: independent game developers and small studios planning a game at an early stage.
- Near-term timeframe: within two weeks. Using the session date 2026-10-06, the planning horizon is approximately 2026-10-20; the exact institutional submission date is not established.
- Steam + Android has not been approved by the supervisor. The student wants a small, working feasibility demonstration before discussing this direction with the supervisor.
- Use the supplied *Handbook of Projects for the Final Year*, BCDA, 2025-26, July 2025, for the report-format discussion. Its dated submission calendar does not establish the student's current deadline.

## What the supplied handbook actually says

Page numbers below are printed page numbers, followed by PDF page indices counted from 1.

| Location | Requirement or guidance | Consequence for this project |
|---|---|---|
| Section 8, p.12 (PDF p.13) | Chapter 1 is Introduction and should clearly state objectives and significance. Sample structure is guidance, not rigidly mandatory. | Introduction is the parent chapter; do not assume three separate chapters are required. |
| Sample 3, p.22 (PDF p.23) | Introduction contains Background and Objective; later sections cover data acquisition, processing, analysis and visualization. | This is a suitable starting structure for our analysis + system project, subject to supervisor feedback. |
| Section 8, p.12 (PDF p.13) | A4, black text, font size 10-12, single spacing and 1.27 cm margins. | Apply when formatting the student's own report. The handbook does not set a separate word count for these three parts. |
| Section 8, p.13 (PDF p.14) | ACM reference format, alphabetic reference list and author-year citations. | Record sources now; format checked citations when the student drafts the report. |
| Section 3.3, p.4 (PDF p.5) | Final report must explain setup or reproduction of results. | Existing scripts, locked environment and manifests support this later section. |
| Section 11, p.17 (PDF p.18) | LLM-generated report text is prohibited; editing author-written text is allowed. AI assistance must be disclosed. | Discuss structure/evidence and review the student's own draft; do not turn these notes into generated submission paragraphs. Keep an AI assistance record for code, processing, visualization and editing. |

The AI rule is stricter than the original context file's suggestion that generated text can simply be reviewed or rewritten. Use the supplied handbook's explicit wording when planning this report workflow. This is a reading of the supplied edition, not verification of any newer university policy or supervisor exception.

## Recommended immediate scope

Prepare a feasibility demonstration and a student-written Chapter 1 discussion draft. The demonstration should show that both audited sources can support useful historical comparisons through a shared interaction pattern. It does not need to be the final app, a revenue predictor or a validated pre-release forecasting service.

Current proof already exists: source audit, reproducible cleaning, feature allowlist, 73,527 PC and 318,300 Mobile analysis rows, developer-group partitions, and successful independent verification. There is currently no user-facing application or fitted model.

### Small demonstration acceptance criteria — proposed, not implemented

1. One interface with Steam and Android selection, showing the source date and the applicable cohort.
2. Steam genre/function or Android category/monetization filters, with matched sample counts and historical outcome-tier distributions.
3. Compare two sets of conditions within the same platform; make clear that differences are associations, not the effect of changing price or monetization.
4. Handle no matches and small samples explicitly; a small-count warning is an interface rule, not a statistical guarantee.
5. Export the displayed aggregate counts and data provenance for checking.
6. Use the frozen **training partition only** for exploratory prototype comparisons. Label the displayed denominator as the training subset; do not accidentally present it as the entire market or full analysis cohort.
7. A model result is optional for the first demonstration. If available, show development-stage group-CV results with a baseline; do not inspect final test results merely to strengthen the presentation.

Avoid core-scope expansion into RAWG joins, review NLP, Apple validation or an LLM agent during this two-week preparation. Keep the platform-specific data and logic modular so that supervisor feedback can narrow the scope without discarding all work. No final app framework has been selected.

## Chapter 1 writing worksheet

Suggested outline adapted from Sample 3:

```text
Chapter 1  Introduction
  Opening overview and project motivation
  1.1 Background
  1.2 Objective
  [Optional: 1.3 Scope and Limitations, if useful and accepted]
```

### Opening overview — questions for the student to answer

- What motivated you personally to study game-development planning?
- Which developer decisions should the system help with: choosing/comparing genres and features, historical price positioning, or monetization configurations?
- What information would a small studio want to inspect before committing to a concept?
- What will the combined analysis and program deliver to that user?

Keep this at problem-and-purpose level. Claims that small studios lack particular resources or information need supporting sources or user evidence; do not treat an assumed user need as an interview finding. Detailed row counts and cleaning rules belong primarily in Method/Data chapters.

### Background — evidence to explain

- Platform coverage: Steam games and the conservative Google Play game subset.
- Metadata available on each platform: genre/category, language/platform support, observed price, ads/IAP and content rating as applicable.
- Outcomes and limits: estimated-owner intervals versus install lower bounds; neither directly measures revenue or profit.
- Source timing: PC March 2025 reference snapshot and Android June 2021; do not compare the two as contemporaneous market sizes.
- Related work: use the targeted literature matrix to explain what others predict and what inputs they have; acknowledge its incomplete coverage.
- The project's intended contribution: traceable data handling, disciplined historical analysis and an integrated comparison interface. Do not claim to be the first dual-platform system or to have invented a novel algorithm.

### Objective — proposed commitments to discuss, not submission prose

| Objective component | Evidence of completion | Current position |
|---|---|---|
| Prepare and validate platform-specific data | Source records, cleaning rules, dictionary and validation | Working version complete |
| Analyse historical attribute/outcome relationships | Clearly scoped EDA, sample support and limitations | Diagnostics complete; substantive EDA pending |
| Evaluate historical tier classification | Group-CV/baseline comparisons and eventual locked test evaluation | Features/splits ready; no model fitted |
| Build an integrated planning-support program | Shared platform selection, comparison and evidence export | Proposed; not implemented |
| Assess reliability and usefulness | Sensitivity checks, functional cases and user-task evaluation if recruitment permits | Design only; no user study performed |

Objectives describe what the project intends to deliver, not claims that the results already exist. Model evaluation can be completed even if complex models do not outperform a baseline; predictive outputs should only enter the app when justified by evaluation.

## Proposed two-week sequence

These are relative work blocks, not confirmed institutional deadlines or a promise of supervisor availability.

| Period | Primary work | Reviewable output |
|---|---|---|
| Days 1-2 | Student explains motivation and planning decisions; agree Chapter 1 content map and demo scope | Student notes, evidence map, demonstration scenarios |
| Days 3-5 | Build training-only historical comparison prototype; complete initial descriptive checks | Small working Steam/Android demonstration with traceable counts |
| Days 6-8 | Check demo cases; assemble brief evidence package; student arranges supervisor feedback | Demonstration, scope/options, current limits; optional baseline group-CV results |
| Days 9-11 | Student writes Introduction/Background/Objective; review logic, references and wording; incorporate available feedback | Student-authored discussion draft and revised scope record |
| Days 12-14 | Recheck evidence, demo and draft; rehearse explanation of decisions | Concise supervisor package and next-work list |

If time is tight, protect the student-authored draft, traceable demo and supervisor discussion. Extra models and visual polish are secondary. Do not wait for a completed final system before seeking scope feedback.

## Questions for the supervisor

- Is Steam + Android an appropriate unified scope for this 6-credit project?
- Is historical planning support with owners/install proxies acceptable, given snapshot age and coverage limits?
- Is the proposed balance of analysis, model evaluation and program implementation appropriate?
- Is the proposed Chapter 1 structure acceptable, and are there additional current report requirements?
- What level of user evaluation is feasible and expected?

The student will communicate with the supervisor; no message has been sent on the student's behalf.
