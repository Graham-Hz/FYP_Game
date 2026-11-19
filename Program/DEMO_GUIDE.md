# Local application demonstration

The application provides independent historical market analysis, planning-condition comparisons and a connected reference-to-budget workflow. It supports versioned updates through a specified CSV format and runs locally with a Python service and browser interface.

## Start

Install `uv` and prepare the required analysis files described in the [program guide](README.md). On Windows, open `Program/START_DEMO.cmd`. Alternatively, run from `Program/`:

```powershell
uv run --locked python src/demo/server.py --open
```

Open `http://127.0.0.1:8765/market` and keep the terminal running. Press Ctrl+C to stop. If the port is occupied, use `--port 8766`. The service is bound to localhost. Restart an already-running server after updating the program so the new API routes are loaded.

## Independent market analysis walkthrough

1. Start on **市場資料分析**. Charts load automatically; no plan, team or budget input is required. Read the source date and sample definition before interpreting the results.
2. With **Steam**, compare gameplay counts and summed owner bounds in the overview. **玩法類型** contains gameplay genres such as Action and RPG. **附加來源標籤** separately groups Indie, Early Access, content descriptors and software/media labels. For example, select Sexual Content as an additional content label: the gameplay chart still groups the matching records by Action, Adventure and other gameplay genres, rather than ranking content and gameplay labels together. Genre and additional-label selections combine with AND. Android uses its separate Google Play game categories.
3. Select a genre and a release-year range, then click **更新圖表**. The old results are hidden until recalculation. Inspect high-tier shares alongside their group sizes; the 30-record display threshold does not establish statistical reliability.
4. Inspect the release-cohort line charts. These compare different games released in each year and observed in one historical snapshot. They are not sales occurring in those years, growth of the same games, or a forecast. Older games have had more time to accumulate outcomes.
5. Switch to **Android**. Inspect installation lower-bound rankings and free/paid/unknown, advertising and in-app-purchase comparisons. Do not compare these numeric outcomes directly with Steam owner estimates.
6. Switch to the separate **Steam revenue** selection. Inspect estimated copies/revenue rankings, genre medians, release-month cohorts and revenue concentration. This source includes all 1,500 selected games, including 85 with zero observed prices; its results differ intentionally from the positive-price default on `/revenue`.
7. Use **下載圖表 SVG** on an individual chart, expand its data table, and try **匯出圖表數據 CSV** and **匯出分析 JSON**. These exports preserve the displayed values and source context. SVG is a scalable image suitable for further layout work; it is not a screenshot.
8. To analyse a compatible new snapshot, use **歷史分布比較** to validate, save and activate its CSV version. Return to the market page and select **重新讀取資料版本**. The market analysis uses that platform's eligible records, while the revenue dataset remains independent.

Use the analysis tabs to switch between overview, distribution, relationships, release cohorts and rankings. The plot selector focuses on one question at a time. In **數值分布**, compare the histogram with the boxplot: the histogram shows where values accumulate, while the boxplot shows medians, quartiles and outliers by gameplay group. Read the metric and units because the PC price, Android install-lower-bound and revenue distributions have different meanings. Groups below the boxplot's minimum size are disclosed rather than treated as having no variation.

In **變數關聯**, inspect the scatter diagram and its complete-pair count; click a point to inspect its displayed record. The visual may contain a deterministic subset of up to 800 records, whereas the reported rank correlation uses all valid pairs. Change the linear/log display when needed to inspect skew and extreme values. Use the heatmap to compare within-group outcome proportions, checking the row sample sizes and cell counts. These are descriptive associations, not evidence of a causal effect or a reliable market opportunity. Selecting a gameplay-count bar applies that genre filter across the analysis; reset the conditions to restore the whole source.

Each screen shows a chart title and explanation once. Source/method details and numeric tables can be expanded. SVG downloads include a self-contained title and source caption; CSV exports retain histogram boundaries, boxplot statistics, displayed scatter records and heatmap cell counts rather than treating every chart as a simple bar series.

The research view contains 51,152 Steam and 221,806 Android training records. One Steam exception has no matching candidate detail row; overall counts retain it and numeric/date coverage discloses the gap. This avoids drawing on reserved calibration/test outcomes or inventing missing figures. The source dates are historical and cannot establish today's complete market environment.

## Connected planning walkthrough

1. Open **歷史分布比較** in the navigation. Select **Steam**, compare **Action** with **RPG**, and inspect the sample sizes and overlap. Click **以條件 A 繼續規劃** to record your choice; the system does not pick a winner.
2. The reference page carries over Action when supported. Enter **14.99 USD** as an illustrative proposed price, search, and select one or more references using **加入規劃** (maximum five). These references come from a separate selected Steam sample; other comparison filters are not silently treated as matching criteria. If no suitable references exist, record a skip reason.
3. Follow **繼續成本預算**. Enter your own assumptions or load the artificial example. Net contribution is independently supplied; it is not populated from the reference price. Optionally select two Unity Pro prepaid yearly seats and enter **7.8 HKD per USD** as an illustrative conversion rate, then confirm conditions.
4. Calculate. With the artificial example and those selected fees, the original cash budget is **HKD 215,639.60** and the 15-month scenario is **HKD 288,279.20**. Open **查看整合規劃摘要** to see the chosen market condition, selected references and budget together.
5. Add a planning name and a short note about the decision and remaining uncertainty. Export the JSON. It contains original evidence and source versions, selected references, the full budget request and results, and a completion indicator. A skipped step is recorded; a partial plan is not labelled complete. The summary can also be printed.
6. Return to the budget, change the duration, and observe that the old calculation disappears until recalculation. Reopen a previous page to check that draft inputs, fee choices and source context persist. Changing the comparison context clears reference choices and calculated budgets; manually entered budget fields remain for review. Changing platform also clears fee selections.
7. Repeat with **Android**. It proceeds directly from the selected historical condition to budgeting, filters the cost-case library to Android, and marks Android game-reference retrieval as unavailable. Steam references are not inserted into the Android plan.

The workflow is stored in the current browser tab, not in a server account. Export before closing; a different port or browser tab has a separate context. JSON is currently an evidence export and cannot be loaded back as a project file. The main CSV importer continues to update datasets independently. If a source version changes, follow the summary's prompt to update the affected evidence before export.

## Individual module checks

1. Select Steam and compare Action with Adventure. Inspect sample sizes, estimated-owner tier distributions and overlap between the two samples.
2. Add a feature such as Single-player and inspect how the matching sample changes. The result is a historical association, not the causal effect of adding that feature.
3. Select Android and compare categories such as Puzzle and Action, optionally using free status, advertising or in-app purchase conditions.
4. Inspect a small or empty result. Small-sample feedback uses an interface threshold of 30 records, not a guarantee of statistical reliability.
5. Export the JSON result. It includes the conditions, counts, proportions, overlap and data provenance. Re-run a comparison after changing its conditions before exporting.
6. Use the [CSV import workflow](CSV_IMPORT_GUIDE.md) to validate a compatible file, review inclusion/exclusion results, save a version, activate it and return to the original research version.
7. Open **Steam revenue analysis** using the link above the main title, or visit `/revenue`. Compare positive-price and zero-price subsets, inspect the revenue distribution and top-decile share, filter a genre, and search/sort/page through game records. Export the filtered JSON. This supplementary dataset is independent of the main page's imported versions.
8. Expand **用遊戲構想尋找相近作品** on the revenue page. Try Action at USD 14.99, a half-to-double price range and 10 results. Inspect shared genres, genre overlap, price difference and source-provided revenue. Add Adventure or change the price, re-run and inspect why the reference list changes. Export the list with its matching method and provenance. A zero-price query searches zero-price candidates only.

Conditions across fields are combined with AND. A blank feature condition does not mean the game lacks that feature. Steam genres can overlap; Android records use a single source category.

For a later human user-task study, ask participants to complete the connected walkthrough using a planning choice of their own. Record whether they can select and explain a comparison, justify a reference or skip, revise a budget, and identify one limitation in the exported summary. Record completion, errors, assistance required and interpretation difficulties. The automated browser checks are not participant results; no human study has been conducted yet.

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

The calculator also displays exportable cost-composition, delay, cash/resource-budget and break-even charts. The duration line compares complete project scenarios at the original, three-month-delay and six-month-delay horizons; it is not a monthly spending ledger. Break-even quantities are requirements under the entered contribution assumption, not predicted sales. Leaving contribution blank suppresses that dependent chart, and changing inputs hides all old results until recalculation.

Optional funds or net-contribution inputs can be blank; dependent outputs then remain unavailable. Zero monetary spending is valid when explicitly entered, but it does not erase unpaid labour. Manual monetary inputs must use the selected currency; changing currencies does not convert them. Cases are reviewed local CSVs, separate from the main snapshot importer, and are not used to train models.

The **工具、平台與設備費用** section provides 26 saved fee variants with 16 official sources. Search a tool or filter its category/currency, expand its conditions and follow the source links. Add an applicable plan and enter quantity, any required exchange rate, and confirm eligibility/no duplicate manual entry. One product can have one selected plan; multiple seats use quantity. Royalty rules, quote-only prices and the non-game Unreal seat reference are displayed without an add action. GitHub monthly units require an explicit flexible-monthly budgeting assumption because the recorded pricing page did not establish a commitment.

For a reproducible fee example, first load the artificial HKD example, select **Unity Pro - prepaid yearly**, set quantity to **2** and the user-assumed conversion rate to **7.8 HKD per USD**, then confirm the conditions. The rate is illustrative, not a market quote. The selected annual cost is HKD 36,036; total cash budget including the existing 10% reserve is HKD 215,639.60. At 15 months, a second full subscription year is included and total cash budget is HKD 288,279.20. Inspect the fee breakdown and export the source-linked JSON. Do not also add the same selected cost to manual overhead or one-off inputs.

Subscriptions are assumed to start at development month 1 and renew in full terms. A monthly-paid annual contract includes the full commitment even for a shorter project. The conservative runway measure reserves selected fees upfront and does not extrapolate beyond the scenario horizon. Changing currency clears FX/eligibility confirmation for selected items; loading the example or resetting clears selections. Source data retains its original review date and is not refreshed from vendor sites automatically.

### Decision-usefulness checks still to conduct with users

Automated checks establish software behaviour, not user benefit. Recruit a small initial group of people with relevant game-development experience (for example, 3–5 participants) for formative feedback; this is not a representative efficacy study. Ask each participant to complete these tasks without supplying the answer in advance:

1. Find a relevant case and explain which costs or production phases it includes and excludes. Check that a funding request or zero-budget claim is not mistaken for actual total cost.
2. Enter a resource plan, inspect a three-month delay and identify the funding shortfall or remaining capacity. Record the assumptions they would revise and why.
3. Explain what the break-even requirement says, and what it cannot say about likely sales. Export enough evidence for another person to reproduce their calculation.
4. Compare two tool plans, inspect their source/commitment, add one using an explicit FX assumption, and explain why crossing a renewal date changes the delay budget. Check that a conditional royalty or unquoted price is not interpreted as zero.

Record anonymous participant background, task completion, time, interpretation errors, needed assistance and requested changes. Review misinterpretations before expanding the dataset or making recommendations. These sessions have **not** been conducted; no participant results or usability claims are recorded here.

## Implementation and verification

The service uses the Python standard-library HTTP server, DuckDB and PyArrow. The frontend uses HTML, CSS and JavaScript without a CDN dependency. Analysis input hashes are checked at startup; imported versions have their own version files and validation. CSV updates do not alter research splits or retrain models.

The local write API has Host, Origin and page-token checks. Multi-user authentication and public deployment are not implemented. See the [application verification](reports/2026-10-07/demo_v1/verification_notes.md), [CSV verification](reports/2026-10-10/csv_import_v1/verification_notes.md) and [test commands](README.md#model-experiments-and-checks).
