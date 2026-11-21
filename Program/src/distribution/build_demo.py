"""Build an allowlisted, hash-inventoried local demonstration ZIP.

Run from the development checkout. Downloaded raw datasets, environments,
personal reports and saved application versions are never selected.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = "DEMO_PACKAGE_MANIFEST.json"
FIXED_FILES = (
    "Program/pyproject.toml", "Program/uv.lock",
    "Program/START_DEMO.cmd", "Program/CHECK_DEMO.cmd",
    "Program/DEMO_GUIDE.md", "Program/CSV_IMPORT_GUIDE.md",
    "Program/config/analysis_v1.json", "Program/config/cleaning_candidate_v1.json",
    "Program/src/imports/__init__.py", "Program/src/imports/contracts.py",
    "Program/src/imports/guided.py",
    "Program/src/imports/repository.py",
    "Program/src/imports/cli.py", "Program/src/imports/convert_sources.py",
    "Program/src/analysis/revenue_metrics.py", "Program/src/analysis/comparable_games.py",
    "Program/src/analysis/game_taxonomy.py",
    "Program/src/distribution/smoke_demo.py",
    "Program/reports/2026-10-06/analysis_v1/manifest.json",
    "Program/reports/2026-10-23/revenue_sources/analysis.json",
    "Program/data/processed/analysis_v1/pc_features.parquet",
    "Program/data/processed/analysis_v1/pc_labels_splits.parquet",
    "Program/data/processed/analysis_v1/mobile_features.parquet",
    "Program/data/processed/analysis_v1/mobile_labels_splits.parquet",
    "Program/data/interim/cleaning_candidate_v1/pc_candidates.parquet",
    "Program/data/interim/cleaning_candidate_v1/mobile_candidates.parquet",
    "Program/data/processed/revenue_v1/explorer.json",
    "Dataset/Development Cost Cases/cases.csv",
    "Dataset/Development Cost Cases/observations.csv",
    "Dataset/Development Cost Cases/sources.csv",
    "Dataset/Development Cost Cases/README.md",
    "Dataset/Development Fee References/fees.csv",
    "Dataset/Development Fee References/sources.csv",
    "Dataset/Development Fee References/README.md",
)
RENAMED_FILES = {
    "README.md": "Program/distribution/DEMO_SETUP.md",
    "START_HERE.txt": "Program/distribution/START_HERE.txt",
    "DATA_SOURCES.md": "Program/distribution/DATA_SOURCES.md",
    "Program/README.md": "Program/distribution/RUNTIME_README.md",
}


def document_bytes(relative, path, entries):
    """Keep bundled links local and route omitted development evidence to GitHub."""
    data = Path(path).read_bytes()
    if not relative.endswith(".md"):
        return data
    content = data.decode("utf-8")

    def link(match):
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            return match.group(0)
        parts = []
        for part in (PurePosixPath(relative).parent / unquote(url.path)).parts:
            if part == "..":
                if not parts:
                    return match.group(0)
                parts.pop()
            elif part != ".":
                parts.append(part)
        resolved = "/".join(parts)
        # The compact runtime README deliberately omits research-build sections.
        replaced_anchor = bool(url.fragment and resolved == "Program/README.md")
        if resolved in entries and not replaced_anchor:
            return match.group(0)
        remote = "https://github.com/Graham-Hz/FYP_Game/blob/main/" + quote(resolved)
        if url.fragment:
            remote += "#" + url.fragment
        return f"[{label}]({remote})"

    content = re.sub(r"\[([^\]]+)\]\(([^\s)]+)\)", link, content)
    if relative == "Program/DEMO_GUIDE.md":
        content = content.replace(
            "## Start\n", "## Start\n\nIn the prepared Demo package, all required historical data "
            "are already included. Research rebuild instructions and verification links below "
            "refer to the full source checkout; no rebuilding is needed to use this package.\n", 1)
    elif relative == "Program/CSV_IMPORT_GUIDE.md":
        content = ("Prepared Demo package: use the browser import steps below or the included CLI. "
                   "Raw source CSVs, previously converted examples and development tests are not "
                   "bundled. They require the full source checkout and its inputs.\n\n" + content)
    return content.encode("utf-8")


def selected_files(root):
    """No recursive copy: only runtime Python, known web assets and fixed files."""
    root = Path(root).resolve()
    entries = {rel: root / rel for rel in FIXED_FILES}
    entries.update({dest: root / source for dest, source in RENAMED_FILES.items()})
    for pattern in ("Program/src/demo/*.py", "Program/src/demo/static/*.html",
                    "Program/src/demo/static/*.js", "Program/src/demo/static/*.css"):
        for path in root.glob(pattern):
            entries[path.relative_to(root).as_posix()] = path
    for relative, path in entries.items():
        if not path.is_file():
            raise ValueError(f"Required bundle input is missing: {path.relative_to(root)}")
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Bundle input must be a regular file inside the checkout: {relative}")
    return entries


def build_archive(entries, output, name):
    """Hash the exact bytes written, and publish ZIP/checksum only on success."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name):
        raise ValueError("Bundle name must be 1-80 letters, digits, dots, underscores or hyphens.")
    output = Path(output)
    checksum = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or checksum.exists():
        raise ValueError("Output already exists; choose a new --name or --output-dir.")
    output.parent.mkdir(parents=True, exist_ok=True)
    inventory = []
    fd, temporary_name = tempfile.mkstemp(prefix=".demo-", suffix=".zip.tmp", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, path in sorted(entries.items()):
                pure = PurePosixPath(relative)
                if (pure.is_absolute() or ".." in pure.parts or "\\" in relative or ":" in relative
                        or relative == MANIFEST or pure.as_posix() != relative):
                    raise ValueError(f"Invalid bundle member: {relative}")
                data = document_bytes(relative, path, entries)
                archive.writestr(f"{name}/{relative}", data)
                inventory.append({"path": relative, "size_bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest()})
            manifest = {
                "schema_version": 1, "package_name": name,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "project": "A Data-Driven Decision Support for Game Development Planning",
                "repository": "https://github.com/Graham-Hz/FYP_Game",
                "package_type": "local_source_and_data_demo",
                "python_requirement": ">=3.14,<3.15",
                "files": inventory,
                "total_file_bytes": sum(entry["size_bytes"] for entry in inventory),
                "notes": [
                    "Inventory excludes this manifest itself and later runtime-generated files.",
                    "Hashes detect accidental changes; this is not a signed publisher identity.",
                    "Python, uv and third-party packages are not bundled.",
                    "No saved user imports, credentials, personal reports or model binaries are included.",
                    "A build is not evidence of another-computer or public-deployment testing.",
                ],
            }
            archive.writestr(f"{name}/{MANIFEST}", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        # Reserve the destination exclusively; never replace an older deliverable.
        with output.open("xb") as target, temporary.open("rb") as source:
            import shutil
            shutil.copyfileobj(source, target)
        checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
        return {"archive": str(output), "sha256": digest,
                "archive_bytes": output.stat().st_size, "file_count": len(inventory),
                "uncompressed_file_bytes": manifest["total_file_bytes"]}
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="FYP_Demo_" + datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "Program/dist")
    args = parser.parse_args()
    try:
        entries = selected_files(ROOT)
        subprocess.run([sys.executable, "-B", str(ROOT / "Program/src/demo/preflight.py"),
                        "--skip-port-check"], cwd=ROOT / "Program", check=True)
        result = build_archive(entries, args.output_dir / f"{args.name}.zip", args.name)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Bundle was not built: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
