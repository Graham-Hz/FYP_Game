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
7. Open **Steam revenue analysis** using the link above the main title, or visit `/revenue`. Compare positive-price and zero-price subsets, inspect the revenue distribution and top-decile share, filter a genre, and search/sort/page through game records. Export the filtered JSON. This supplementary dataset is independent of the main page's imported versions.
8. Expand **用遊戲構想尋找相近作品** on the revenue page. Try Action at USD 14.99, a half-to-double price range and 10 results. Inspect shared genres, genre overlap, price difference and source-provided revenue. Add Adventure or change the price, re-run and inspect why the reference list changes. Export the list with its matching method and provenance. A zero-price query searches zero-price candidates only.

Conditions across fields are combined with AND. A blank feature condition does not mean the game lacks that feature. Steam genres can overlap; Android records use a single source category.

## Data shown in the original application version

| Platform | Snapshot | Training rows | Outcome |
|---|---|---:|---|
| Steam | March 2025 | 51,152 | Estimated-owner interval tiers |
| Android | June 2021 | 221,806 | Installation lower-bound tiers |

The complete research cohorts contain 73,527 Steam and 318,300 Android records. The original application version queries training rows only. An imported version uses its own eligible historical records, with the version and denominator displayed separately.

The interface does not provide model inference, new-game revenue prediction or causal conclusions. The Steam revenue page offers deterministic reference retrieval using genres and observed prices. Source dates differ, the primary March 2025 Steam price currency remains unresolved, and unknown Android free status is preserved rather than treated as paid. These samples should not be presented as the whole current market.

## Supplementary Steam revenue page

Prepare the revenue snapshot using the [program guide](README.md#audit-supplementary-revenue-data), then restart the service. The separate page uses source-provided estimated cumulative gross revenue for 1,500 selected games. It retains 85 zero-price games separately and defaults to the other 1,415. In that default subset, median estimated revenue is USD 105,087 and the top 142 games account for 92.05% of the subset's revenue. These are selected-sample statistics, not market-wide benchmarks or expected earnings for a new game.

Genre metadata matches 1,406 Steam IDs, with usable genre lists for 1,401. Genres can overlap and were observed later than the revenue snapshot. The provider's publisher classes partly reflect past revenue and should not be presented as independent causal explanations of revenue or verified studio size. The page shows these interpretation limits and exports its source hashes and filters with the results.

## Development planning

Open **開發資源規劃** in the navigation or visit `/planning`. Search the developer case library, filter a production stage/platform, expand a case and follow its original source. Costs, budget plans, funding and labour estimates are explicitly separated. Download the three linked CSV tables for case context, observations and sources. The collection method and field definitions are in [Development Cost Cases](../Dataset/Development%20Cost%20Cases/README.md).

In the budget section, enter a plan or click **載入假設示例**. The example is artificial, not market guidance: its 12-month cash budget is HKD 176,000; adding unpaid labour gives HKD 320,000. At an assumed HKD 40 net contribution per copy, cash break-even requires 4,400 copies. The three-month delay scenario requires HKD 209,000 cash. Edit any assumption, recalculate and export the resulting JSON, which includes the full inputs and calculation assumptions.

Optional funds or net-contribution inputs can be blank; dependent outputs then remain unavailable. Zero monetary spending is valid when explicitly entered, but it does not erase unpaid labour. All monetary inputs must use the selected currency. There is no conversion when switching currencies. Cases are reviewed local CSVs, separate from the main snapshot importer, and are not used to train models.

### Decision-usefulness checks still to conduct with users

Automated checks establish software behaviour, not user benefit. Recruit a small initial group of people with relevant game-development experience (for example, 3–5 participants) for formative feedback; this is not a representative efficacy study. Ask each participant to complete these tasks without supplying the answer in advance:

1. Find a relevant case and explain which costs or production phases it includes and excludes. Check that a funding request or zero-budget claim is not mistaken for actual total cost.
2. Enter a resource plan, inspect a three-month delay and identify the funding shortfall or remaining capacity. Record the assumptions they would revise and why.
3. Explain what the break-even requirement says, and what it cannot say about likely sales. Export enough evidence for another person to reproduce their calculation.

Record anonymous participant background, task completion, time, interpretation errors, needed assistance and requested changes. Review misinterpretations before expanding the dataset or making recommendations. These sessions have **not** been conducted; no participant results or usability claims are recorded here.

## Implementation and verification

The service uses the Python standard-library HTTP server, DuckDB and PyArrow. The frontend uses HTML, CSS and JavaScript without a CDN dependency. Analysis input hashes are checked at startup; imported versions have their own version files and validation. CSV updates do not alter research splits or retrain models.

The local write API has Host, Origin and page-token checks. Multi-user authentication and public deployment are not implemented. See the [application verification](reports/2026-10-07/demo_v1/verification_notes.md), [CSV verification](reports/2026-10-10/csv_import_v1/verification_notes.md) and [test commands](README.md#model-experiments-and-checks).
