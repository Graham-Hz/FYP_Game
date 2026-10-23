# Chapter 1 planning notes

Updated 2026-10-23. Working notes and writing prompts, not a meeting record or submission text. These notes replace the former two-week supervisor discussion worksheet. The student has not yet discussed the project scope and methods with the supervisor; no meeting date, feedback or scope approval is recorded.

Use [PROJECT_STATUS.md](../../PROJECT_STATUS.md) for current progress, [product scope](product_scope_v1.md) for the product plan, and [Chapter 1 review](fyp_v1_review_2026-10-08.md) for the review of the dated report draft. The expired October preparation windows and duplicate demonstration checklist have been removed from this worksheet.

## Confirmed by the student

- Target users: independent game developers and small studios planning a game at an early stage.
- Product direction: an updatable decision-support system accepting specified-format CSV files.
- Steam + Android remains the student's working scope, pending supervisor confirmation.
- The student supplied a First Progress Report deadline of 23 October 2026 at 5 pm. A report draft and two submission-format PDFs have been prepared; submission has not been confirmed.

## Report guidance and current sources

The latest supplied source is `FYP/BCDA FYP Handbook.pdf` (2026-27, August 2026). It supersedes the 2025-26 edition used in the original worksheet. Sample 3 places Background and Objective within Chapter 1 Introduction; use this as structural guidance rather than a record of supervisor instructions.

Section 11 retains its general restriction on LLM-generated report text and requires disclosure. On 23 October the student separately reported a supervisor relaxation of that restriction; its scope is not documented here. This statement does not establish a project-scope meeting or approval. Actual drafting, implementation and checking assistance is recorded in [AI assistance log](ai_assistance_log.md).

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

### Objective — project commitments and evidence

| Objective component | Evidence of completion | Current position |
|---|---|---|
| Prepare and validate platform-specific data | Source records, cleaning rules, dictionary and validation | Working version complete |
| Analyse historical attribute/outcome relationships | Clearly scoped EDA, sample support and limitations | Train EDA and age/scope/target sensitivity checks complete |
| Evaluate historical tier classification | Group-CV/baseline comparisons and eventual locked test evaluation | Linear/tree development comparisons complete; group-versus-random diagnostic and final evaluation pending |
| Build an integrated planning-support program | Shared platform selection, comparison, evidence export and versioned specified-format CSV updates | Local comparison and CSV/versioning implemented; overview/explorer and final integration pending |
| Assess reliability and usefulness | Sensitivity checks, functional cases and user-task evaluation if recruitment permits | Recorded sensitivity and functional checks exist; no user study performed |

Objectives describe what the project intends to deliver, not claims that the results already exist. Model evaluation can be completed even if complex models do not outperform a baseline; predictive outputs should only enter the app when justified by evaluation.

## Pending confirmation

The two-platform scope, balance of analysis and implementation, assessment schedule and feasible user evaluation remain open. Keep these in the current project status and product plan rather than maintaining a separate meeting package. Record actual feedback only after the student supplies it.
