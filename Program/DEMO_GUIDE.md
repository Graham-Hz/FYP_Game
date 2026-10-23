# Local application demonstration

The application compares historical game outcomes under two sets of planning conditions and supports versioned updates through a specified CSV format. It runs locally with a Python service and browser interface.

## Start

Install `uv` and prepare the required analysis files described in the [program guide](README.md). On Windows, open `Program/START_DEMO.cmd`. Alternatively, run from `Program/`:

```powershell
uv run --locked python src/demo/server.py --open
```

Open `http://127.0.0.1:8765/` and keep the terminal running. Press Ctrl+C to stop. If the port is occupied, use `--port 8766`. The service is bound to localhost.

## Demonstration sequence

1. Select Steam and compare Action with Adventure. Inspect sample sizes, estimated-owner tier distributions and overlap between the two samples.
2. Add a feature such as Single-player and inspect how the matching sample changes. The result is a historical association, not the causal effect of adding that feature.
3. Select Android and compare categories such as Puzzle and Action, optionally using free status, advertising or in-app purchase conditions.
4. Inspect a small or empty result. Small-sample feedback uses an interface threshold of 30 records, not a guarantee of statistical reliability.
5. Export the JSON result. It includes the conditions, counts, proportions, overlap and data provenance. Re-run a comparison after changing its conditions before exporting.
6. Use the [CSV import workflow](CSV_IMPORT_GUIDE.md) to validate a compatible file, review inclusion/exclusion results, save a version, activate it and return to the original research version.

Conditions across fields are combined with AND. A blank feature condition does not mean the game lacks that feature. Steam genres can overlap; Android records use a single source category.

## Data shown in the original application version

| Platform | Snapshot | Training rows | Outcome |
|---|---|---:|---|
| Steam | March 2025 | 51,152 | Estimated-owner interval tiers |
| Android | June 2021 | 221,806 | Installation lower-bound tiers |

The complete research cohorts contain 73,527 Steam and 318,300 Android records. The original application version queries training rows only. An imported version uses its own eligible historical records, with the version and denominator displayed separately.

The interface does not provide model inference, revenue estimation, recommendation ranking or causal conclusions. Source dates differ, Steam price currency remains unresolved, and unknown Android free status is preserved rather than treated as paid. These samples should not be presented as the whole current market.

## Implementation and verification

The service uses the Python standard-library HTTP server, DuckDB and PyArrow. The frontend uses HTML, CSS and JavaScript without a CDN dependency. Analysis input hashes are checked at startup; imported versions have their own version files and validation. CSV updates do not alter research splits or retrain models.

The local write API has Host, Origin and page-token checks. Multi-user authentication and public deployment are not implemented. See the [application verification](reports/2026-10-07/demo_v1/verification_notes.md), [CSV verification](reports/2026-10-10/csv_import_v1/verification_notes.md) and [test commands](README.md#model-experiments-and-checks).
