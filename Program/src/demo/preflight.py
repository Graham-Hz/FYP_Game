"""Check the complete local demo without starting a server or changing datasets."""
import argparse
import hashlib
import importlib
import json
import socket
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_MANIFEST = "reports/2026-10-06/analysis_v1/manifest.json"
EXPECTED_MANIFEST = "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6"
REVENUE_MANIFEST = "reports/2026-10-23/revenue_sources/analysis.json"
REVENUE_ARTIFACT = "data/processed/revenue_v1/explorer.json"
ANALYSIS_ARTIFACTS = tuple(
    f"data/processed/analysis_v1/{platform}_{kind}.parquet"
    for platform in ("pc", "mobile") for kind in ("features", "labels_splits")
)
CANDIDATE_ARTIFACTS = tuple(
    f"data/interim/cleaning_candidate_v1/{platform}_candidates.parquet"
    for platform in ("pc", "mobile")
)
DATA_ARTIFACTS = (*ANALYSIS_ARTIFACTS, *CANDIDATE_ARTIFACTS, REVENUE_ARTIFACT)
STATIC_FILES = (
    "import.html", "import.js", "import.css",
    "app.js", "charts.css", "charts.js", "fees.js", "index.html", "market.css",
    "market.html", "market.js", "plan.html", "plan.js", "planning.css",
    "planning.html", "planning.js", "revenue.css", "revenue.html", "revenue.js",
    "style.css", "workflow.css", "workflow.js", "budget_scenarios.js", "budget_scenarios.css", "shell.js", "shell.css",
)
# Paths are relative to Program; keep Dataset beside Program when packaging.
REQUIRED_FILES = (
    "pyproject.toml", "uv.lock", ANALYSIS_MANIFEST, REVENUE_MANIFEST,
    "config/analysis_v1.json", "config/cleaning_candidate_v1.json",
    "src/demo/server.py", "src/demo/market.py", "src/demo/market_analytics.py", "src/demo/market_availability.py",
    "src/demo/market_taxonomy.py", "src/demo/market_cohorts.py", "src/demo/revenue.py", "src/demo/planning.py",
    "src/demo/fees.py", "src/imports/__init__.py", "src/imports/contracts.py",
    "src/imports/repository.py", "src/imports/guided.py", "src/analysis/revenue_metrics.py",
    "src/analysis/comparable_games.py", "src/analysis/game_taxonomy.py",
    *(f"src/demo/static/{name}" for name in STATIC_FILES),
    "../Dataset/Development Cost Cases/cases.csv",
    "../Dataset/Development Cost Cases/observations.csv",
    "../Dataset/Development Cost Cases/sources.csv",
    "../Dataset/Development Fee References/fees.csv",
    "../Dataset/Development Fee References/sources.csv",
    *DATA_ARTIFACTS,
)
DEPENDENCIES = ("duckdb", "pandas", "pyarrow", "requests", "ijson")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def data_checks(root):
    """Report missing files and preserve the application's frozen data checks."""
    results = []
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    for name in missing:
        results.append((False, f"Missing required file: {name}"))
    if not missing:
        results.append((True, "All required runtime files and complete demo data are present."))
    if any(name in missing for name in DATA_ARTIFACTS):
        results.append((False, "GitHub Download ZIP does not include the generated demo data. "
                        "Use the prepared demo bundle and extract the entire folder; "
                        "you do not need to repeat model training."))
    manifest_path = root / ANALYSIS_MANIFEST
    if manifest_path.is_file():
        try:
            if digest(manifest_path) != EXPECTED_MANIFEST:
                raise ValueError("Frozen analysis manifest checksum differs from the application.")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name in (*ANALYSIS_ARTIFACTS, *CANDIDATE_ARTIFACTS):
                if name in missing:
                    continue
                section = "outputs" if name in ANALYSIS_ARTIFACTS else "inputs"
                if digest(root / name) != manifest[section][name]:
                    results.append((False, f"Data checksum mismatch: {name}. Re-extract the matching demo bundle."))
                else:
                    results.append((True, f"Verified data: {name}"))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            results.append((False, f"Analysis manifest check failed: {exc}"))
    if (root / REVENUE_MANIFEST).is_file() and (root / REVENUE_ARTIFACT).is_file():
        try:
            manifest = json.loads((root / REVENUE_MANIFEST).read_text(encoding="utf-8"))
            if digest(root / REVENUE_ARTIFACT) != manifest["artifact_sha256"]:
                raise ValueError("Revenue data checksum mismatch; re-extract the matching demo bundle.")
            results.append((True, "Verified Steam revenue/reference data."))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            results.append((False, f"Revenue check failed: {exc}"))
    for name in ("config/analysis_v1.json", "config/cleaning_candidate_v1.json"):
        if name in missing:
            continue
        try:
            if not isinstance(json.loads((root / name).read_text(encoding="utf-8")), dict):
                raise ValueError("Expected a JSON object")
        except (OSError, ValueError) as exc:
            results.append((False, f"Invalid configuration {name}: {exc}"))
    return results


def package_checks(root):
    """Verify builder-supplied hashes. These detect damage, not publisher identity."""
    package_root = root.parent.resolve()
    path = package_root / "DEMO_PACKAGE_MANIFEST.json"
    if not path.exists():
        return [(True, "No package manifest: checking a source checkout using its data manifests.")]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list) or not manifest["files"]:
            raise ValueError("Unsupported or empty package manifest")
        results, seen = [], set()
        for item in manifest["files"]:
            relative = item["path"]
            if not isinstance(relative, str) or "\\" in relative or ":" in relative:
                raise ValueError("Invalid package path")
            parts = PurePosixPath(relative)
            if parts.is_absolute() or ".." in parts.parts or relative in seen or relative != parts.as_posix():
                raise ValueError(f"Invalid or duplicate package path: {relative}")
            seen.add(relative)
            file = (package_root / relative).resolve()
            if not file.is_relative_to(package_root):
                raise ValueError(f"Package path leaves its root: {relative}")
            if not file.is_file():
                results.append((False, f"Package file missing: {relative}"))
            elif file.stat().st_size != item["size_bytes"] or digest(file) != item["sha256"]:
                results.append((False, f"Package file changed: {relative}. Use an intact bundle or rebuild after intentional edits."))
        if not results:
            results.append((True, f"Package integrity verified: {len(seen)} files."))
        return results
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [(False, f"Package manifest check failed: {exc}")]


def writable_check(root):
    """Probe the actual import-state directory and remove only our empty additions."""
    target = root / "data/application/v1"
    created = []
    node = target
    while not node.exists():
        created.append(node)
        node = node.parent
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(prefix=".demo-write-check-", dir=target) as stream:
            stream.write(b"demo preflight\n")
            stream.flush()
        return True, "CSV import storage is writable; no imported versions were changed."
    except OSError as exc:
        return False, ("Cannot write CSV import storage (data/application/v1). "
                       "Extract the demo to a writable folder such as Documents, outside the ZIP. "
                       f"Details: {exc}")
    finally:
        for directory in created:
            try:
                directory.rmdir()  # Only directories created here, and only if still empty.
            except OSError:
                pass


def port_check(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", port))
        return True, f"Local port {port} is available now (checked before startup)."
    except OSError as exc:
        return False, (f"Local port {port} is unavailable. Stop the existing demo, "
                       f"or run START_DEMO.cmd --port 8766 with an unused port. Details: {exc}")


def run_checks(root=ROOT, port=8765, check_port=True):
    results = [(sys.version_info[:2] == (3, 14),
                f"Python {sys.version.split()[0]}; this project requires Python 3.14.x. Use the uv launcher.")]
    for module in DEPENDENCIES:
        try:
            importlib.import_module(module)
            results.append((True, f"Dependency available: {module}"))
        except (ImportError, OSError) as exc:
            results.append((False, f"Cannot load {module}: {exc}. Run uv sync --locked from Program."))
    results.extend(data_checks(root))
    results.extend(package_checks(root))
    results.append(writable_check(root))
    if check_port:
        results.append(port_check(port))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-port-check", action="store_true", help="Check files/environment while another demo is running")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    print("Checking the complete local demo...", flush=True)
    results = run_checks(port=args.port, check_port=not args.skip_port_check)
    for ok, message in results:
        print(f"[{'OK' if ok else 'FAIL'}] {message}")
    failures = sum(not ok for ok, _ in results)
    if failures:
        print(f"\nPreflight failed ({failures} issues). See README.md and DEMO_GUIDE.md; the server was not started.")
        return 1
    print("\nPreflight passed. This checks this installation, not another computer or all user workflows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
