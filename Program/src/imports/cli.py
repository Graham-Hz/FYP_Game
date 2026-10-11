"""Validate/import standard CSV snapshots without running the web application."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from imports.contracts import MAX_BYTES, template, validate
from imports.repository import SnapshotRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["template", "validate", "import"])
    parser.add_argument("--platform", choices=["pc", "mobile"])
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path, help="Template or validation JSON (must not already exist)")
    args = parser.parse_args()
    try:
        if args.action == "template":
            if not args.platform or not args.output:
                raise ValueError("template requires --platform and --output")
            with args.output.open("xb") as f:
                f.write(template(args.platform))
            return
        if not args.csv or not args.metadata:
            raise ValueError("--csv and --metadata are required")
        if args.csv.stat().st_size > MAX_BYTES:
            raise ValueError("CSV exceeds 64 MiB")
        raw = args.csv.read_bytes()
        meta = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
        prepared = validate(raw, meta)
        result = prepared[0]
        if args.action == "import" and result["can_import"]:
            result = SnapshotRepository(ROOT / "data/application/v1").save(raw, meta, prepared)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            with args.output.open("x", encoding="utf-8") as f:
                f.write(output + "\n")
        else:
            print(output)
        if not prepared[0]["can_import"]:
            sys.exit(2)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
