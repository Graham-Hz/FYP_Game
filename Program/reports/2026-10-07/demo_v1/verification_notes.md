# Historical comparison prototype v1: verification and stage

Date: 2026-10-07. Development notes; not submission-ready report prose.

## Recovery finding

The previous handbook review, Chapter 1 worksheet and two-week preparation plan had been saved. No previous Python/uv task remained running. The remaining step was the working demonstration. Existing audit/cleaning/split artifacts were retained; no rerun or redesign of the frozen split was needed.

## Implemented evidence

- A local Steam / Android interface with two filter scenarios, matched sample counts, fixed historical tier counts and percentages, overlap count, small/empty sample messaging, and JSON export of results and provenance.
- Frozen training rows only: Steam 51,152; Android 221,806. No fitted model, calibration query or final test performance evaluation.
- Startup SHA-256 verification of the pinned analysis manifest and four feature/label artifacts. The in-memory tables contain only train membership; the API accepts no split selection.
- No price filter while Steam collection currency remains unresolved. Android unknown Free is distinguished from false. No across-platform success ranking.
- Standard-library local server, existing DuckDB dependency and static frontend. Locked runtime dependencies and frozen analysis scripts/configs are unchanged. A double-click Windows launcher is included.

## Verification

`uv run --locked python -m unittest discover -s tests -v`: **16 tests passed**, including the 10 existing cleaning/analysis tests and 6 demo integration tests. New checks cover complete train membership, fixed tier counts, independent filtered SQL counts, unknown vs false, no-match percentages, invalid inputs/split requests, API response and static-file allowlisting.

`uv run --locked --with playwright python.exe tests/check_demo_browser.py`: **8 browser checks passed** using a separate headless system Edge session. Desktop (1365px) and mobile (390px) layouts were captured and inspected; text/cards/charts were readable with no horizontal overflow. Exported JSON matched the displayed query's counts/filters and provenance. Filter changes and delayed responses did not leave stale results visible. No uncaught JavaScript errors were observed. Browser integration tools were unavailable in this session; the documented optional CLI test uses an ephemeral dependency without altering `uv.lock`. The initial `python` invocation worked but later encountered Windows spawn error 32; the explicit `python.exe` command passed the final run and is used in the Windows launcher.

Ignored local artifacts: `data/processed/demo_qa/steam-desktop.png`, `android-desktop.png`, `android-mobile.png`, `export.json`, `browser_checks.json`. The browser script regenerates these. These checks are engineering verification, not evidence from target users or a formal usability study.

`uv run --locked python src/data/verify_analysis.py`: passed for both full frozen cohorts, with zero cross-partition developer-group overlap, zero training-fold overlap and zero independent hash-assignment mismatches. Frozen artifact/dependency checks passed; the prototype did not change the analytical design.

Example checked baseline counts, in ascending fixed tier order:

| Platform | Tier 1 | Tier 2 | Tier 3 | Train total |
|---|---:|---:|---:|---:|
| PC | 38,428 | 8,527 | 4,197 | 51,152 |
| Mobile | 103,908 | 81,403 | 36,495 | 221,806 |

No claims of predictive accuracy are available. Historical snapshot, selection, multi-genre overlap, age/confounding and differing platform outcome definitions remain limitations.

## Working phase map

This is a practical organization of the work, not a claim that the handbook prescribes exactly six phases or that the original context fixed this numbering.

1. Scope and feasibility: audience and early-planning use confirmed by student; two-platform scope awaits supervisor.
2. Data acquisition/audit/cleaning: completed for the current operational version, with documented unresolved source limitations.
3. Literature, features and split design: initial six-paper comparison and versioned design complete; broader reading and supervisor refinement remain.
4. Prototype and modelling: descriptive prototype now implemented; preprocessing, baselines, group-CV, sensitivity analysis and model evaluation remain.
5. System integration and evaluation: future validated outputs, explanation design, target-user evaluation and final system refinement.
6. Report and presentation: drafting/discussion runs alongside implementation; final experiments, student-authored text, reproducibility and presentation remain.

Immediate next steps: student tries the demonstration; discuss and write Chapter 1 in the student's own words using the saved worksheet; present a small proof and proposed scope to the supervisor; then implement the prespecified model experiment. Retain the existing approximately 2026-10-20 preparation horizon rather than resetting the two-week clock.
