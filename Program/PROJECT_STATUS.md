# Project status

Updated: 2026-10-06, Asia/Hong_Kong.

Read the workspace `FYP_PROJECT_CONTEXT_FOR_CODEX.md` for the user's original context. This status supplements it; it does not imply supervisor approval or replace unknown decisions with facts.

Completed:

- Full local dataset feasibility audit, source metadata collection and a revision-pinned Steam HF Parquet download.
- Five requested audit deliverables under `reports/2026-10-05/`; raw file preservation and independent count checks passed.
- Research-design diagnostics and proposed RQs/targets/evaluation/system scope under `reports/2026-10-05/research_design/`.
- Recovery check: prior audit/design work completed; no Python/uv job remained running. Continued with versioned, provisional cleaning rather than restarting audits.
- Candidate cleaning under `data/interim/cleaning_candidate_v1/`, with complete input-row ledgers, rule counts, data dictionary, pinned inputs and independent SQL verification under `reports/2026-10-06/cleaning_candidate_v1/`. Five regression tests passed. All current per-row cohort decisions, labels and ages reconcile with independent SQL.
- Targeted six-paper literature matrix, explicit reading-depth/quality limits, and source/local-data question review under `reports/2026-10-06/analysis_v1/`. Not a systematic review or submission-ready literature chapter.
- Operational analysis_v1 cohort, feature allowlist, group-aware train/calibration/test split and training CV are frozen. PC primary: 73,527 rows (51,152/11,435/10,940); Mobile: 318,300 (221,806/48,297/48,197). No developer group crosses partitions or training folds. Independent source/SQL verification and 10 regression tests passed.
- Generated features, labels/splits and cohort ledger under `data/processed/analysis_v1/`; they remain Git-ignored. Features are selected by `src/features/feature_policy.py`; IDs/targets are denied as predictors.

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
- Candidate cleaning v1 retained 1,033 software-only genre heuristic rows and 122 rows without developers; the subsequent analysis_v1 scope and placeholder-aware grouping decisions are recorded below.
- analysis_v1 adds an explicit title-filter exception for Forex Demo Accelerator (1129080), making the broader PC base 89,454. It excludes software-only heuristic records and nonpositive observed prices from primary analysis, and treats developer placeholder tokens as unknown. No raw/candidate files were overwritten.
- Five Mobile Free/price conflicts all have missing currency; analysis_v1 masks Free as unknown and retains labels. The 214 unavailable USD prices remain missing.
- Current pinned upstream Steam scraper supplies evidence that SteamSpy failure can produce zero review components and owners 0-0, and missing price overview can produce price 0. The exact original collection invocation remains unknown; do not claim every local zero is explained.
- Current Steam API type=game also occurs for software-like products; this does not establish a reliable historical product-type filter. Software exclusion remains an explicit sensitivity-tested scope rule.

Next work: incorporate supervisor feedback when available; prepare a small, prespecified modelling/preprocessing configuration; fit baselines and candidates using only the frozen train partition and its group CV. Keep calibration for calibration and test for final evaluation. Verify analysis artifacts first; do not reroll splits for better scores. PC without-price sensitivity is required because the original collection currency is not independently verified. Expand the targeted literature review and fully read abstract-only entries before final report writing. Do not treat operational design as supervisor approval.

No model or learned preprocessing has been fitted. A versioned analytical dataset and split manifest now exist, but there is no chosen app framework or deployed application. The user's current deliverable date and supervisor feedback remain unknown. Working files distinguish measurements, operational decisions, hypotheses and unknowns. The repo root README had an existing user modification when this phase began and was not edited; no commit/push was performed for this phase.
