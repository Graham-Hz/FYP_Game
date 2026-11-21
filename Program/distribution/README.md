# Demo distribution

The Windows Demo package contains the application source, local web assets, seven prepared data artifacts, source-linked reference CSVs and locked dependency definitions. It is intended for running and assessing the implemented functions without repeating data cleaning or model training. Python, uv and third-party dependencies are installed separately.

## Use a prepared package

Obtain the prepared `FYP_Demo_*.zip`, select **Extract All**, keep `Dataset/` beside `Program/`, and open `START_HERE.txt`. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) once, then double-click `Program/START_DEMO.cmd`. The initial setup normally needs internet access. Keep its terminal open while using the browser.

`CHECK_DEMO.cmd` diagnoses installation, complete data, checksums, write access and port conflicts. It pauses so a double-click user can read the results; `--no-pause` returns directly for automation. Use `START_DEMO.cmd --port 8766` if the default port is occupied. GitHub's source download alone omits the generated data and is not this prepared package.

## Build from the development checkout

From `Program/`, after preparing the verified local data:

```powershell
uv run --locked python -B src/distribution/build_demo.py --name FYP_Demo_2026-11-19
```

The builder runs preflight, selects an explicit runtime allowlist, and writes the ZIP plus its SHA-256 sidecar under ignored `Program/dist/`. It refuses to replace an existing package; use a new name for a revised build. Each archive has one top-level directory and a `DEMO_PACKAGE_MANIFEST.json` listing the exact shipped files, sizes and hashes. The seven data artifacts occupy about 49 MB before ZIP compression.

The builder excludes `.git`, `.venv`, raw downloads, existing application imports, caches, model binaries, lectures and personal progress reports. The frozen source manifests remain byte-for-byte unchanged. `DEMO_SETUP.md`, `START_HERE.txt`, `DATA_SOURCES.md` and `RUNTIME_README.md` in this directory are package documentation templates: the builder places them at the archive root or at `Program/README.md`, so their relative links target the extracted package. Documentation links to omitted development evidence point to the full GitHub checkout; package notes distinguish optional research commands from ordinary use. The CSV CLI and explicit source adapters are included, but their original raw data inputs are not.

The bundle is generated locally. No GitHub release or public deployment is created by the build command. Source terms remain distinct; see the package's source register, including the unresolved revenue redistribution licence. Hashes detect accidental changes, not publisher identity.

## Verify the extracted artifact

Extract into a new directory, preferably containing spaces and non-ASCII characters. Confirm there is no copied `.venv` or application state, then run from the extracted `Program/`:

```powershell
uv sync --locked
.\CHECK_DEMO.cmd --no-pause --skip-port-check
uv run --locked python -B src/distribution/smoke_demo.py --output data/processed/demo_smoke.json
```

The API smoke check uses disposable import state and an ephemeral loopback port. It verifies static routes, original Steam/Android counts, three market sources, shared gameplay taxonomy, selected/baseline cohort counts and matching records, revenue references, cost/fee catalogues, documented artificial budgets, and CSV preview/save/activation/rollback. It also checks that restoration survives a store restart. It never uses existing saved imports as its fixture.

Check actual browser rendering and exports separately. Finally, repeat installation and the main user tasks on another Windows computer, recording its OS, environment, results and assistance required. A fresh extracted path and environment on the development machine do not establish that another physical computer, a clean OS or an offline first installation works. The package does not provide public hosting or multi-user authentication.

The [recorded verification](verification.json) identifies each tested ZIP by SHA-256. The 19 November 2026 **v1** package passed 14 distribution/preflight tests, 10 API check groups and six focused browser check groups in an independent extraction with a newly created environment on the development computer. The initial setup downloaded the 13 locked packages; uv and the base Python interpreter were already present. The final artifact used a second new environment with those packages cached. The student subsequently confirmed successful operation on another laptop. Its OS, environment versions and individual task results were not supplied, so this is recorded separately as user-reported execution rather than a second automated certification.

The **v2** package (`FYP_Demo_2026-11-19_v2.zip`) includes selected-versus-baseline comparisons, matching-record inspection and the shared gameplay taxonomy. In another independent extraction, a new environment installed the 13 locked packages from the existing cache. All 65 shipped-file hashes, 11 API check groups and seven actual-package browser checks passed. The latter include the Adventure comparison, its 2,487 highest-tier records, comparison exports and the existing budget charts. Source-level market, taxonomy, reference, import, distribution and planning regressions also passed. These v2 checks ran on the development computer; the earlier second-laptop confirmation applies to v1. Both ZIPs remain separate, and neither was uploaded by this build process.

The **v3** package (`FYP_Demo_2026-11-20_v3.zip`) adds saved market findings, independent budget A/B alternatives and combined summary export. Another new extracted environment passed all 67 shipped-file hashes, 11 API check groups and ten actual-package browser checks. These include a real Adventure finding followed by budgets of HKD176,000 and HKD189,200, their HKD13,200 difference, preserved source/assumption snapshots and correctly partial planning status. Source checks include 18 new browser groups for capture, alternative comparison and their integration, plus existing market, planning and selected-condition workflow regressions. The new environment used previously cached locked packages on the development computer. A physical second-device run of v3 has not been recorded; previous packages remain separate.

The **v4** package (`FYP_Demo_2026-11-20_v4.zip`) adds confirmed restoration of saved A/B assumptions and identifies matching current budgets after recalculation. All 67 file hashes, 11 API groups and 12 actual-package browser groups passed in a new extracted environment using cached dependencies. The browser checks include the complete Steam route: Action/RPG evidence, an explicit Action choice, two reference games, budget A/B, a source-checked completed summary, then restoration and recalculation of A while preserving B and both references. Independent Android exploration preserves that Steam planning context. Six focused restoration groups and 20 existing browser regression groups also passed, including source failures, storage failures and delayed responses. These checks ran on the development computer; they do not establish second-device v4 operation, human usability or presentation timing.

The **v5** package (`FYP_Demo_2026-11-21_v5.zip`) adds the shared left sidebar, four planning steps, chart-data readiness and reading guidance. All 70 shipped-file hashes, 11 API groups and 13 actual-package browser groups passed in a new environment using cached packages. The latter retain the complete planning route and add sidebar navigation, readable sample labels, readiness in chart exports and real empty-filter handling. Source checks passed 60 unit/integration tests, 43 browser groups and the existing planning browser check. A rapid five-page navigation test reproduced refused static-file requests; increasing the pending-connection queue resolved that sequence. Missing-date UI behaviour was tested with an explicit response fixture, since the CSV importer excludes such rows. Verification remains on the development computer, without a new physical second-device or participant study.

The **v6** package (`FYP_Demo_2026-11-21_v6.zip`) reduces repeated market-page content: section-specific headings, a collapsed shared filter summary, overview-only metric cards, and expandable limited-data notices. All 70 shipped-file hashes and 11 API check groups passed after extraction using the existing development Python environment. Five source browser suites passed 37 groups covering compact desktop/mobile layouts, retained filters, chart interaction, comparisons, saved findings, data readiness and exports. The four changed browser assets in the ZIP match the tested source byte-for-byte. This revision did not repeat fresh dependency installation or a physical second-device run; browser checks were against the source checkout rather than the extracted server.

The latest **v7** package (`FYP_Demo_2026-11-22_v7.zip`) adds guided CSV field mapping, confirmed formats, reusable browser profiles and separate exploration/comparison eligibility. All 74 shipped-file hashes and 12 API check groups passed after extraction. Six actual-package Edge browser groups cover renamed columns, partial-data charts, missing-date explanations, matching records, preview invalidation, exports, activation/rollback and mobile layout. Source verification passed 115 targeted unit/integration tests and 15 browser groups (guided import, legacy import and shared navigation). Read-only guided conversions of the existing 51,152-row Steam and 221,806-row Android CSVs retained the original comparison counts with zero format errors. Tests used disposable application registries; existing research files and user imports were not changed. The extracted package reused the development environment and cached browser-test dependencies; fresh installation, another physical device and human user benefit were not re-evaluated for v7.
