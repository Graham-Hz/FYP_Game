# Demonstration data and provenance

The package contains derived historical data, not newly collected or live market figures. Source dates, meanings and licences remain distinct. Each shipped file is listed in `DEMO_PACKAGE_MANIFEST.json`; the original analytical manifests retain the hashes checked by the application.

| Source | Included use | Snapshot and interpretation |
|---|---|---|
| [Steam Games Dataset 2025](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset), Artemiy Ermilov / artermiloff | Frozen Steam features/labels and candidate details; genre enrichment for revenue records | March 2025; estimated owner intervals, not exact purchases. Original observed-price currency remains unresolved |
| [Google Play Store Apps](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps), Gautham Prakash / gauthamp10 | Frozen Android features/labels and candidate details | June 2021 collection; installation lower bounds, not revenue or exact sales |
| [Top 1500 games on Steam by revenue](https://www.kaggle.com/datasets/alicemtopcu/top-1500-games-on-steam-by-revenue-09-09-2024), alicemtopcu | Independent Steam revenue/reference JSON | 2024-09-09 title-based snapshot; selected high-revenue games. Estimated cumulative gross revenue, not profit or representative expected earnings |
| [Development cost cases](Dataset/Development%20Cost%20Cases/README.md) | Three curated CSVs: cases, observations and sources | Public developer disclosures; cash spending, funding, budgets and unpaid labour remain separate |
| [Development fee references](Dataset/Development%20Fee%20References/README.md) | Two curated CSVs: fee variants and sources | Saved official pricing evidence with original currencies, conditions and review dates; not live vendor quotes |

## Files and transformations

`Program/data/processed/analysis_v1/` contains four frozen feature/label files. The service selects training membership only: **51,152 Steam** and **221,806 Android** records. Other frozen partitions remain in these files because their original bytes and hashes are retained; the UI does not query their outcomes. This package does not run final held-out model evaluation.

`Program/data/interim/cleaning_candidate_v1/` contains two candidate-detail files used for names, release dates and numeric descriptive values. The service joins them to the selected training membership. One approved Steam exception lacks a matching detail row and is disclosed in coverage. Raw labels are preserved; the interface's gameplay/other-label mapping does not rewrite research partitions or model features.

`Program/data/processed/revenue_v1/explorer.json` contains all **1,500** selected revenue records plus later genre metadata. `/revenue` defaults to **1,415** positive-price records, while the independent market view includes all 1,500. Steam ID matching supplies later metadata, not launch-time facts. Revenue estimates are retained rather than recreated from price times copies.

The original verification manifests are `Program/reports/2026-10-06/analysis_v1/manifest.json` and `Program/reports/2026-10-23/revenue_sources/analysis.json`. They also reference development inputs not shipped in this runtime subset. The complete audit and pipeline are in the [source repository](https://github.com/Graham-Hz/FYP_Game); a current dataset download is not assumed to reproduce the pinned input bytes.

## Source terms as recorded

The saved Kaggle metadata retrieved on 2026-10-05 reports **MIT** for the Steam 2025 dataset, and **Database: Open Database, Contents: Database Contents** for the Google Play dataset. Exact local download versions were not established; original file hashes identify the research inputs. These are recorded provider labels, not a new blanket licence for the application or all underlying content.

The local revenue audit records its URL, source hash and [Gamalytic methodology](https://gamalytic.com/about), but does not preserve a verified redistribution licence. No additional permission is inferred from the ability to download a CSV. The prepared artifact is a local assessment package; public redistribution has not been established by this build. Source credits and original terms must accompany any authorised onward distribution.

The cost and fee CSVs preserve source URLs, dates, locators and qualifications. Full source articles are not included. They are evidence references, not representative cost benchmarks or statements that a tool plan is eligible for every user.

Time charts compare release cohorts observed in historical snapshots; they are not stock-style repeated sales measurements. Descriptive associations, deterministic reference retrieval and user-entered budgets do not establish causal effects, predicted success or expected profit.
