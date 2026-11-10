# Development fee references

A manually curated reference catalogue for early game-development budgeting. Checked on **9 November 2026**: **26 records**, covering 13 products/platforms and 16 official source URLs. The records comprise 24 software/platform fee variants and two equipment examples. Of these, 21 have a monetary amount (including five zero-cost entries), two contain conditional royalty rates, two require a custom quote, and one links to transaction-dependent rules without a universal price.

This catalogue supplies reference inputs, not observed game production costs or a complete project budget. It is separate from the historical [developer cases](../Development%20Cost%20Cases/README.md), market datasets and model training data. The current `/planning` calculator still uses user-entered assumptions; these references are **not yet connected to its controls**.

## Files

| File | Purpose |
|---|---|
| [fees.csv](fees.csv) | Canonical machine-readable observations: one plan, payment variant or fee component per row |
| [sources.csv](sources.csv) | Official publisher, URL, review date, page section, short evidence excerpt and retrieval limitations |
| [Development_Fee_References.xlsx](outputs/fee_references_20261109/Development_Fee_References.xlsx) | Review copy with filterable `Fees` and `Sources` sheets; not a separate source of truth |

CSV files use UTF-8 with a byte-order mark for Excel compatibility. Numeric columns contain unformatted numbers; percentages are stored as fractions. The workbook preserves numeric/date types. No conversion between USD and HKD, total across alternative plans, or estimated missing price has been added.

## Coverage and interpretation

| Area | Included |
|---|---|
| Engines | Unity Personal, both Pro payment schedules and Enterprise; Unreal standard/reduced game royalties, custom licensing and a separately marked non-game seat reference; Godot |
| Art | Blender core application; Aseprite supplied 1.x binaries |
| Audio | REAPER discounted/commercial licences; FMOD Free Indie, paid Indie, Basic and Premium |
| Collaboration | GitHub Free, Team and Enterprise base plans |
| Distribution | Steam Direct per-app fee; Google Play account registration and service-fee rule reference; optional Apple membership |
| Equipment | Dell Hong Kong monitor and laptop offers with configuration/offer identifiers |

This is a selected initial catalogue, not every vendor, add-on or available plan. Asset purchases, contractor and salary rates, marketing, hosting, electricity, office space, console certification and complete store commissions are not quantified here. Those remain separate budget inputs. Existing equipment can have zero additional purchase outlay without implying zero depreciation or economic cost.

Keep alternative tiers separate when constructing a budget: buying one applicable engine or audio plan does not mean adding every tier. A per-seat fee needs seat count; a per-game fee needs project count; an account fee is not repeated for every game. Displayed monthly units do not establish monthly cancellation rights. Royalty rates need their defined revenue base and exclusions; multiplying every game's gross revenue by the headline rate is not valid.

The Unreal seat reference is marked `non_game_reference_only`; Apple membership is an optional platform expansion reference. Neither should be a default Steam/Android game cost. Hardware entries are individual retail examples, not minimum specifications, recommended purchases, a representative equipment-price sample or evidence that the configurations run every target workflow.

## Source collection and evidence

1. Inspect official vendor pricing, licence or help pages. Preserve the displayed currency, plan and charge unit. Record separate rows for different payment schedules and eligibility tiers.
2. Save the official URL on each fee row. Link additional supporting pages through semicolon-separated `source_ids`; all IDs resolve to `sources.csv`.
3. Save a short original excerpt and a page-section locator in the source register. Most entries use opened official-page extracts. Blender's official indexed page text was inspected after direct retrieval returned HTTP 402; `S006` explicitly records this weaker retrieval route.
4. Preserve uncertainty. Unknown/custom prices are blank numeric cells, not zero. Tax and billing details not established by the inspected page remain `not_stated`. Commercial-use and price eligibility summaries do not replace the complete licence terms.
5. Record the review date separately from a published effective date. `accessed_on` records this review session; web results can be cached. It is not a claim of a live checkout, publication date or independently archived page.

The saved excerpts and locators make the observations traceable, but are not full-page snapshots or proof that a web page can never change. Sources can be reopened from the workbook/CSV; check the selected plan and applicable terms again before using a price in a real budget.

Specific unresolved details are retained instead of guessed:

- Unity's overview and FAQ differ in their wording at financial eligibility boundaries. Exact boundary eligibility is not encoded as an automatic rule.
- GitHub's displayed price unit is recorded without inventing an invoice cadence or contract length.
- Google Play's inspected service-fee page distinguishes regions, install cohorts, billing routes and programmes. `F023` therefore has **no universal numeric rate**; it is a rule reference, not a zero-cost observation.
- Only the equipment offers observed on the opened pages were retained. An older indexed laptop offer and an Apple listing without an unambiguous observed purchase price were not used.

## Field dictionary

`fees.csv`:

| Field(s) | Definition |
|---|---|
| `fee_id` | Stable reference identifier; not a vendor SKU |
| `category` | Engine, art, audio, collaboration, distribution or equipment |
| `vendor`, `product`, `plan` | Provider, product and distinct plan/payment variant |
| `charge_type` | Licence, subscription, royalty, registration, revenue share, membership or hardware |
| `price_status` | Meaning of the price fields; see the status table below |
| `amount` | Monetary amount per stated unit/period; blank for rates or unknown prices |
| `currency` | USD or HKD where relevant; blank for unpriced multi-region rules or currency-independent free software |
| `rate_fraction` | Conditional revenue fraction: e.g. 0.05 means 5%; not a currency amount |
| `charging_unit` | Seat, user, game, app, account, membership, device, contract or defined eligible revenue |
| `display_period` | Vendor price unit: month, year, one time, revenue, none or not stated |
| `billing_schedule` | Payment cadence/arrangement where established; separate from displayed price unit |
| `commitment_months` | Recorded term where explicit; blank does not mean no commitment |
| `eligibility` | Short financial/use-case conditions; intentionally not a complete executable ruleset |
| `conditions` | Exclusions, recovery conditions, version coverage and other important qualifications |
| `applicability` | General game reference, non-game reference, optional Apple reference or equipment example |
| `market_locale` | Pricing/transaction geography; a USD reference is not a verified Hong Kong checkout |
| `tax_status` | Not stated, not applicable, or excludes applicable taxes; no assumed tax calculation |
| `effective_from` | Explicit effective date where captured; otherwise blank |
| `configuration` | Hardware specification and offer scope; blank for other records |
| `source_ids` | One or more source-register IDs separated by semicolons |
| `primary_source_url`, `source_locator` | Direct price/rule source and relevant page location |
| `accessed_on` | ISO review date, YYYY-MM-DD |

| `price_status` | Interpretation |
|---|---|
| `listed` | Published monetary value for the stated plan/offer |
| `minimum` | Published minimum payment; not an upper bound |
| `free` | Zero base licence/plan fee subject to stated scope; not zero total development cost |
| `conditional_rate` | Numeric fraction applies only after eligibility/revenue rules |
| `custom_quote` | Contact vendor; no amount entered |
| `rule_dependent` | No single amount/rate represents the applicable rules |

`sources.csv` contains `source_id`, `publisher`, `title`, `url`, `accessed_on`, `source_locator`, `short_excerpt`, `evidence_method` and `evidence_note`. The last two fields distinguish opened page text from official indexed extracts and preserve relevant collection limitations.

## Using and maintaining the data

From the `Program` directory, a future importer can read the catalogue using the existing pandas dependency:

```python
from pathlib import Path
import pandas as pd

folder = Path("../Dataset/Development Fee References")
fees = pd.read_csv(folder / "fees.csv", encoding="utf-8-sig")
sources = pd.read_csv(folder / "sources.csv", encoding="utf-8-sig")
# Select a plan and check its units, term, eligibility and sources first.
# Do not fill missing prices/rates with zero or sum all alternative plans.
```

For a refresh, reopen the source, update only supported fields and the associated review evidence, then regenerate the workbook from the canonical CSVs. Preserve changes through repository version history rather than maintaining competing editable copies. Do not edit Excel alone and assume the CSV or application has changed.

Initial checks verified unique identifiers, source relationships, official-source domains, required hardware configuration, positive listed amounts, distinct free/unknown/rate values and CSV-to-workbook consistency. These are data integrity checks, not an independent vendor audit or a complete legal eligibility assessment.
