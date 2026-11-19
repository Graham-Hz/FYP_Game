# A Data-Driven Decision Support for Game Development Planning

This demonstration supports historical Steam and Android market analysis, comparison of planning conditions, Steam reference-game retrieval and source-linked development budgeting. It includes the prepared data required by these functions. It does not provide model predictions or measure the complete current market.

## Start on Windows

1. Download the **prepared Demo ZIP**, rather than GitHub's source-only **Code > Download ZIP**. Right-click it, select **Extract All**, and choose a writable local folder. Keep `Dataset/` and `Program/` together. Do not start the program from inside the ZIP preview.
2. Install **uv** once if needed. The official Windows PowerShell command is:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   This command downloads and runs Astral's installer. Installation alternatives, including GitHub release binaries, are in the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/). Reopen your terminal after installation. The launcher also checks the usual `%USERPROFILE%\.local\bin\uv.exe` location. The Demo does not run an installer automatically.
3. Open `Program/` and double-click **START_DEMO.cmd**. The first run prepares Python **3.14.x** and the dependencies recorded in `uv.lock`, then checks the data and opens the browser. Allow the setup to finish; internet access is normally needed initially. The package does not include Python or third-party packages.
4. Wait for **Demo ready**, then use `http://127.0.0.1:8765/market`. Keep the terminal open. Close it or press **Ctrl+C** to stop.

The target is Windows with a current Edge or Chrome browser. macOS/Linux and a completely offline first installation have not been validated. A newly created environment on the development computer is not a test on another physical computer.

## What to try

| Page | Demonstration |
|---|---|
| `/market` | Switch sources; compare one gameplay group with other records or another group; click a tier to inspect matching games; download SVG/CSV/JSON |
| `/` | Compare historical planning conditions and inspect group sizes and overlap |
| `/revenue` | Explore estimated revenue and retrieve comparable Steam game references |
| `/planning` | Inspect cases/fees; calculate and save budget A/B alternatives; compare changed assumptions and resource requirements |
| `/plan` | Review saved market findings, budget alternatives and an optional selected-condition plan; check sources before export |

See [the feature walkthrough](Program/DEMO_GUIDE.md). The comparison page also offers validated CSV imports; the [CSV specification](Program/CSV_IMPORT_GUIDE.md) defines the required format. No original raw dataset download, cleaning run or model training is required to use this package.

Imported datasets are stored in `Program/data/application/`, separate from frozen research files. Planning drafts live in one browser tab; export before closing. A different port or tab has a different planning context. Exported planning JSON is an evidence record, not an importable saved project.

## Check an installation

Run `Program/CHECK_DEMO.cmd` to check Python, dependencies, runtime files, source hashes, package checksums, write access and port availability. It does not start the website. To preserve output, open a terminal in `Program/` and run:

```powershell
.\CHECK_DEMO.cmd
```

The checker pauses to keep its result visible when double-clicked. Add `--no-pause` for automation, or `--skip-port-check` to check files while an existing demo is running.

For a functional HTTP/API check, from `Program/` run:

```powershell
uv run --locked python -B src/distribution/smoke_demo.py --output data/processed/demo_smoke.json
```

This uses a temporary application store, exercises the bundled data and synthetic CSV updates, and closes its own temporary server. It does not alter your active imports. It checks software behaviour, not human usability or every browser interaction.

`DEMO_PACKAGE_MANIFEST.json` inventories the shipped files and their SHA-256 hashes. Runtime caches, `.venv/`, later imports and test outputs are intentionally outside this inventory. Keep the shipped files unchanged when testing a release; rebuild the bundle after changing source code or reference data. The adjacent ZIP `.sha256` file identifies the distributed archive; these checksums detect changes but are not a digital signature.

## Troubleshooting

| Message or symptom | Action |
|---|---|
| uv not found | Follow the official installation guide, then reopen the terminal and launcher |
| Dependency/Python setup failed | Check the network and available disk space; keep the error text. Do not remove lock constraints to get past an error |
| Required data missing | Extract the complete prepared Demo ZIP. A GitHub source ZIP omits the processed data |
| File/hash mismatch | Re-extract a clean copy of the same bundle. Do not edit a manifest to accept a changed file |
| Cannot write application data | Extract to a folder you can write to; avoid running from a protected folder or ZIP preview |
| Port 8765 is already in use | Close your earlier demo, or run `.\START_DEMO.cmd --port 8766` from `Program/` |
| Browser did not open | Copy the `Demo ready` URL from the terminal into the browser |
| Browser says it cannot connect | Keep the server terminal open; use `127.0.0.1` and the port printed by the server |
| A downloaded file is blocked by school/device policy | Use the institution's approved installation route; do not disable device protection |

`uv run --locked` uses the dependency lock without silently updating it; see [uv's locking and syncing documentation](https://docs.astral.sh/uv/concepts/projects/sync/). After setup, the included analyses use local data and local web assets. Source links still require internet. Moving an already-installed `.venv` to another location is not supported: extract the original ZIP and let uv prepare an environment at the new location.

## Testing on a second computer

Use a fresh extraction on a Windows computer other than the development machine. Record its Windows version, Python/uv versions, installation result and any assistance needed. Confirm that the checks pass, all three market sources produce charts, a chart export downloads, the budget example gives **HKD 176,000**, and a synthetic CSV can be imported and rolled back. Keep the check output and note the result of the browser tasks. A successful test must be recorded after it is performed; this package does not claim that the second-computer test has already happened.

The service is local to the computer running it. This is not a public deployment, multi-user service or standalone executable. Source and research pipeline: [Graham-Hz/FYP_Game](https://github.com/Graham-Hz/FYP_Game). Data provenance: [DATA_SOURCES.md](DATA_SOURCES.md).
