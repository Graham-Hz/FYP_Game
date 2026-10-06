# FYP Project Context for Codex

Last updated: 2026-09-14

## 1. Purpose of this file

This is the working context for a restarted 6-credit HKBU BCDA Final Year Project. Codex should read this file before proposing code, data architecture, machine-learning models, or application features.

The next task is dataset feasibility assessment. Do not begin full model development until the main datasets and target variables have been validated.

## 2. Confirmed facts

- Programme context: Business Computing and Data Analytics (BCDA).
- Project type: data analysis / decision-support project with a working program as the final application.
- The gaming topic is retained, but the earlier mobile-gaming revenue-share forecasting concept is being replaced.
- The supervisor expects a substantial scope for a 6-credit FYP.
- The supervisor asked for recognized datasets with sufficient size and indicated that more than 1,000 downloads is desirable.
- AI assistance is permitted, but the report must be reviewed, understood, and rewritten where necessary by the student. Do not generate submission-ready claims without evidence.
- Kaggle is a hosting platform, not necessarily the original data source. Record the upstream source and collection method.

## 3. Proposed project concept — not yet finalized

Working title:

**Cross-Platform Data-Driven Game Development Planning and Decision-Support System**

Working decision problem:

> Given a target platform, what historical game characteristics can support early-stage decisions about game type, audience positioning, pricing or monetization, and market potential?

The system is one project with two platform-specific modules, not two unrelated FYPs:

1. PC / Steam planning module
2. Mobile / Android planning module

The modules share a research framework, evaluation approach, and user interface. They may use different variables and models because the platform ecosystems are different.

## 4. Proposed data architecture

```text
User selects target platform
        |
        +-- PC / Steam module
        |     +-- Main Steam games dataset
        |     +-- Optional RAWG metadata
        |     +-- Optional sampled Steam reviews
        |
        +-- Mobile / Android module
              +-- Main Google Play apps dataset, filtered to games
              +-- Optional Apple App Store validation dataset

Platform-specific data cleaning and feature engineering
        |
Exploratory analysis and market segmentation
        |
Similarity and/or predictive models
        |
Model evaluation and limitations
        |
Evidence-based development recommendations
```

Core scope:

- Two real main datasets: one PC and one mobile.
- Reproducible cleaning and validation pipelines.
- EDA and feature engineering.
- A small justified set of ML methods.
- Model evaluation.
- One integrated program with two platform modules.

Optional scope, only if time and data quality permit:

- RAWG metadata integration.
- Sampled Steam review NLP or sentiment analysis.
- Apple App Store validation.
- Natural-language AI planning agent.

The AI agent is not a core requirement at this stage.

## 5. Shared concepts and platform-specific variables

| Concept | PC / Steam candidates | Mobile / Google Play candidates |
|---|---|---|
| Game type | genres, tags | category |
| Audience positioning | required_age | content_rating |
| Pricing | price, free-to-play status | free/paid, price |
| Monetization | mainly price; possibly DLC/features if available | ads, in-app purchases, price |
| Popularity/performance proxy | estimated owners, reviews, CCU, playtime | installs, rating count, ratings |
| Product characteristics | multiplayer, supported platforms, languages, tags | app size, Android requirements, ads, IAP |

Important limitations:

- Steam `required_age` is a content age requirement, not the observed age distribution of players.
- Steam `estimated_owners` is normally an estimate/proxy, not exact official unit sales or revenue.
- Google Play installs are not revenue.
- The known 2.3M Google Play dataset is a 2021 snapshot and must not be described as the current 2026 market.
- Download count and popularity do not prove data quality.

## 6. Current dataset candidates

### PC main candidates

1. FronkonGames Steam Games Dataset
   - Approximately 120k+ games in the versions previously reviewed.
   - Hosted on Kaggle and Hugging Face.
   - Candidate fields include price, required age, estimated owners, peak CCU, reviews, recommendations, playtime, genres, and tags.
   - Current leading candidate, subject to local inspection.

2. Steam Games Dataset 2025 by Artemiy Ermilov
   - Approximately 90k+ games and many columns.
   - Feature-rich but potentially heavier cleaning and feature-selection work.

### Mobile main candidate

3. Google Play Store 2.3M Apps
   - Filter to game-related categories.
   - Candidate fields include category, rating, rating count, installs, price, content rating, ad supported, and in-app purchases.
   - Large and widely used, but old snapshot and no direct revenue field.

### Optional secondary candidates

- RAWG video-game metadata: broader platform/genre/Metacritic/developer metadata. Join feasibility is unknown.
- Steam reviews: useful for sampled NLP/player-feedback analysis, but the full dataset is too large for the default scope.
- Video Game Sales with Ratings: useful for historical regional sales context, but old.
- Apple App Store dataset: possible mobile validation source, not part of core scope.

## 7. Unknown decisions that must not be assumed

- Exact identity and version/date of the downloaded Kaggle CSV.
- Exact Hugging Face repository and revision to compare.
- Whether the Kaggle and Hugging Face versions are identical mirrors or different snapshots.
- Final project title and final research questions.
- Whether the supervisor approves the combined PC + mobile scope.
- Final target variable for the PC module.
- Final target variable for the mobile module.
- Whether a composite success score is methodologically defensible.
- Whether secondary datasets can be joined reliably.
- Final ML model set.
- Final application framework.

Do not silently resolve any of these. Report them as unknown and request evidence or a decision when they become blocking.

## 8. Dataset feasibility gates

Evaluate each candidate with the same checklist:

1. Identity and provenance
   - Dataset name, URL, author, upstream source, collection method, license, snapshot/update date, and version/revision.
2. Acceptance evidence
   - Download/use figures, citation or DOI if available, and documented downstream usage. Do not compare Kaggle cumulative downloads directly with Hugging Face recent-period downloads without a warning.
3. Physical structure
   - File format, size, row count, column count, data types, encoding, and memory requirements.
4. Data quality
   - Missingness, duplicates, invalid values, impossible dates, inconsistent categories, outliers, and leakage risks.
5. Analytical coverage
   - Coverage of game type, audience, price/monetization, and performance.
6. Target feasibility
   - Candidate targets, distributions, zero inflation/skew, class balance, and whether each target is a direct measure or proxy.
7. ML feasibility
   - Sample size after cleaning, categorical cardinality, text/list fields, baseline models, metrics, and interpretability.
8. Program usefulness
   - Whether the data can support actionable outputs rather than descriptive charts only.
9. Reproducibility
   - Stable source, version pinning, raw-data preservation, environment requirements, and deterministic pipeline.
10. Risks and recommendation
   - Accept as main, accept as secondary, hold, or reject, with reasons.

## 9. Required comparison outputs

When both candidate datasets are available, produce:

- `dataset_inventory.csv`: one row per file/version with provenance and structural metadata.
- `schema_comparison.csv`: matched, renamed, missing, and extra columns.
- `data_quality_summary.csv`: missingness, uniqueness, duplicates, and invalid-value counts.
- `target_feasibility.md`: evidence for and against each candidate target.
- `dataset_feasibility_report.md`: final PC/mobile dataset recommendation.

If Kaggle and Hugging Face host the same dataset, compare:

- repository/version date;
- row and column counts;
- column names and data types;
- sample and full-file hashes where practical;
- value-level differences on aligned records;
- license and provenance documentation;
- ease of reproducible access.

Do not select Hugging Face merely because it supports code loading. Do not select Kaggle merely because its download count is easier to show.

## 10. Hugging Face access patterns

Install the standard libraries in a project environment:

```bash
python -m pip install -U datasets huggingface_hub pandas pyarrow
```

Load a public dataset repository into Python:

```python
from datasets import load_dataset

dataset = load_dataset(
    "FronkonGames/steam-games-dataset",
    split="train",
)

print(dataset)
print(dataset.column_names)
print(dataset.features)
```

Convert to pandas only if it fits memory:

```python
df = dataset.to_pandas()
df.to_parquet("data/processed/hf_steam_games.parquet", index=False)
```

For a very large dataset, inspect by streaming instead of downloading everything immediately:

```python
from datasets import load_dataset

dataset = load_dataset(
    "OWNER/DATASET_NAME",
    split="train",
    streaming=True,
)

for row in dataset.take(5):
    print(row)
```

Replace `OWNER/DATASET_NAME` only after confirming the exact repository URL. If a repository has multiple configurations, splits, or files, inspect its dataset card before running the load command.

## 11. Instructions for Codex

General rules:

- Read this file first.
- Treat factual claims, assumptions, hypotheses, suggestions, and unknowns separately.
- Never invent dataset facts or silently infer column meaning.
- Preserve raw files unchanged under `data/raw/`.
- Put generated/intermediate data under `data/interim/` and final cleaned data under `data/processed/`.
- Create small, reviewable scripts rather than one monolithic notebook.
- Record dataset URLs, versions/revisions, licenses, and retrieval dates.
- Pin a random seed for reproducible sampling/model evaluation.
- Check for target leakage before training.
- Do not call a proxy “revenue”, “sales”, or exact commercial success.
- Do not create final research conclusions until the dataset audit is complete.
- Explain every cleaning rule and preserve a count of affected rows.
- Ask a focused clarification whenever a missing choice would materially change the result.

Suggested project structure:

```text
fyp-game-planner/
├── README.md
├── PROJECT_CONTEXT.md
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── reports/
├── notebooks/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   └── app/
├── tests/
└── requirements.txt
```

## 12. First Codex task prompt

Use this prompt only after the local Kaggle CSV and exact Hugging Face URL are provided:

> Read `PROJECT_CONTEXT.md` completely. Audit the supplied Kaggle CSV and the specified Hugging Face dataset without modifying raw data. First report their exact identities, versions, schemas, file sizes, row/column counts, and provenance. Then compare missing values, duplicates, data types, categorical cardinality, date coverage, and candidate target distributions. Explicitly label facts, unknowns, assumptions, hypotheses, and suggestions. Do not train models yet. Create reproducible inspection scripts and the five outputs listed under “Required comparison outputs”. Stop and ask if the dataset identity, revision, or column meaning is ambiguous.

## 13. Immediate next step

Required input from the user:

1. Upload or place the downloaded Kaggle CSV in the project workspace.
2. Provide the exact Kaggle dataset URL.
3. Provide the exact Hugging Face dataset URL.
4. State whether the first comparison is for the PC/Steam module or the mobile module.

After these are available, perform the dataset audit before finalizing research questions or models.
