# Project status

Updated: 2026-10-06, Asia/Hong_Kong.

Read the workspace `FYP_PROJECT_CONTEXT_FOR_CODEX.md` for the user's original context. This status supplements it; it does not imply supervisor approval or replace unknown decisions with facts.

Completed:

- Full local dataset feasibility audit, source metadata collection and a revision-pinned Steam HF Parquet download.
- Five requested audit deliverables under `reports/2026-10-05/`; raw file preservation and independent count checks passed.
- Research-design diagnostics and proposed RQs/targets/evaluation/system scope under `reports/2026-10-05/research_design/`.
- Recovery check: prior audit/design work completed; no Python/uv job remained running. Continued with versioned, provisional cleaning rather than restarting audits.
- Candidate cleaning under `data/interim/cleaning_candidate_v1/`, with complete input-row ledgers, rule counts, data dictionary, pinned inputs and independent SQL verification under `reports/2026-10-06/cleaning_candidate_v1/`. Five regression tests passed. All current per-row cohort decisions, labels and ages reconcile with independent SQL.

Working recommendations, not final approvals:

- PC: March 2025 full dataset; source-aligned estimated-owner tiers as primary target candidate. Latest base cohort 89,453 rows, 81,158 labelled and 8,295 unknown targets. Earlier reference cohort had 81,156 labelled rows. Review-volume modelling on hold pending field-definition reconciliation.
- Mobile: 2021 Google Play, excluding ambiguous Sports; install lower-bound tiers as primary target candidate. Latest candidate 318,300 rows, all labelled; earlier reference cohort had 318,298.
- Historical decision support, not revenue prediction, causal strategy optimization or validated pre-launch forecasting.

New evidence that must inform cleaning/design:

- In the PC reference cohort, 9,088 records have zero positive+negative reviews but positive num_reviews_total; do not treat all component zeros as no reviews.
- Unknown owners affect 50.70% of zero-price records versus 1.57% of positive-price records; do not compare free vs paid success from the selected labelled subset.
- The generic missing-token rule excluded two possible legitimate Mobile titles, `None` and `NULL`, and three PC titles `none`. Candidate cleaning preserves and flags all five; two of the PC additions have labels. Their actual title validity is not asserted.
- 1,033 PC reference-cohort records have only software-like genres; product-type refinement remains provisional.
- 214 Mobile reference-cohort currency values are non-USD or unknown. Do not treat all prices as USD.
- Candidate cleaning retains those 214 with missing USD price. Five retained Mobile rows have Free/price conflicts; see `mobile_free_price_review.csv` before analysing monetization.
- Latest PC candidate retains 1,033 software-only genre heuristic rows and 122 rows without developers. Product-type decisions and group-split eligibility remain pending.

Next work: incorporate any supervisor feedback; complete targeted literature matrix; agree working RQs and target definitions; review candidate product-type/name filters and Mobile Free/price conflicts; then finalize cohorts and freeze feature policy and group-aware split before modelling. Do not treat generic "continue" as final supervisor approval of the research design.

No model has been trained. No final cleaned dataset, split manifest, chosen app framework or deployed application exists. The user's current deliverable date and supervisor feedback remain unknown. Working design files explicitly distinguish measurements from proposals.
