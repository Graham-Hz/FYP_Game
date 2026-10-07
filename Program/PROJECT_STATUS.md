# Project status

Updated: 2026-10-07, Asia/Hong_Kong.

Read the workspace `FYP_PROJECT_CONTEXT_FOR_CODEX.md` for the user's original context. This status supplements it; it does not imply supervisor approval or replace unknown decisions with facts.

Latest student clarification (2026-10-06): target users are independent game developers/small studios planning early-stage development. The near-term deadline is within two weeks (planning horizon approximately 2026-10-20; exact submission date not specified). Steam + Android is NOT yet supervisor-approved; the student wants a small feasibility demonstration before presenting the direction. Use the supplied BCDA 2025-26 handbook for format discussion, without importing its old calendar as the current deadline. See `reports/planning/supervisor_discussion_2026-10-06.md` for the Chapter 1 worksheet and proposed two-week plan.

Handbook check: Sample 3 has Background and Objective within Chapter 1 Introduction. Section 11 prohibits LLM-generated report prose and permits editing author-written prose, with AI use disclosure. Support student-authored drafts with discussion, evidence and editing; existing working notes are not submission prose. This corrects the looser wording in the original context about rewriting generated text.

Completed:

- Full local dataset feasibility audit, source metadata collection and a revision-pinned Steam HF Parquet download.
- Five requested audit deliverables under `reports/2026-10-05/`; raw file preservation and independent count checks passed.
- Research-design diagnostics and proposed RQs/targets/evaluation/system scope under `reports/2026-10-05/research_design/`.
- Recovery check: prior audit/design work completed; no Python/uv job remained running. Continued with versioned, provisional cleaning rather than restarting audits.
- Candidate cleaning under `data/interim/cleaning_candidate_v1/`, with complete input-row ledgers, rule counts, data dictionary, pinned inputs and independent SQL verification under `reports/2026-10-06/cleaning_candidate_v1/`. Five regression tests passed. All current per-row cohort decisions, labels and ages reconcile with independent SQL.
- Targeted six-paper literature matrix, explicit reading-depth/quality limits, and source/local-data question review under `reports/2026-10-06/analysis_v1/`. Not a systematic review or submission-ready literature chapter.
- Operational analysis_v1 cohort, feature allowlist, group-aware train/calibration/test split and training CV are frozen. PC primary: 73,527 rows (51,152/11,435/10,940); Mobile: 318,300 (221,806/48,297/48,197). No developer group crosses partitions or training folds. Independent source/SQL verification and 10 regression tests passed.
- Generated features, labels/splits and cohort ledger under `data/processed/analysis_v1/`; they remain Git-ignored. Features are selected by `src/features/feature_policy.py`; IDs/targets are denied as predictors.
- Local historical comparison prototype v1 under `src/demo/`, with `START_DEMO.cmd` and `DEMO_GUIDE.md`. Steam genre/function and Android category/monetization filters; two-scenario counts/tier distributions, overlap counts, small/empty sample handling and JSON export with provenance. Only frozen train rows are queried (51,152 PC / 221,806 Mobile). Startup validates manifest and feature/label hashes. No new runtime dependency or lock change.
- Prototype verification: 16 automated tests passed (10 existing + 6 demo integration checks), plus headless Edge interactions/export/stale-result handling and desktop/mobile visual inspection. See `reports/2026-10-07/demo_v1/verification_notes.md`. This is a feasibility proof, not model evaluation or user validation.

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

Immediate priority: student tries the working local demonstration and develops their own Chapter 1 draft with the writing worksheet; prepare the supervisor discussion within the original two-week window (approximately 2026-10-20). Then prepare a small, prespecified modelling/preprocessing configuration; fit baselines and candidates using only frozen train/group CV. Keep calibration for calibration and test for final evaluation. Verify artifacts first; do not reroll splits for better scores. PC without-price sensitivity is required while collection currency remains unverified. Expand the targeted literature review and fully read abstract-only entries before final report writing. Do not treat operational design as supervisor approval.

No model or learned preprocessing has been fitted. The descriptive prototype uses a standard-library local HTTP server with DuckDB, not a final framework decision. The student has specified a two-week preparation window; exact institutional deadline and supervisor feedback remain unconfirmed. Working files distinguish measurements, operational decisions, hypotheses and unknowns. The repo root README had an existing user modification and was not edited; no commit, merge or push was performed for planning/prototype work. Git was ahead 1 / behind 2 when checked; synchronization is separate from this local implementation.
