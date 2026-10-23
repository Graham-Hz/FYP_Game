"""Read-only supplementary revenue queries, independent of imported snapshots."""
import hashlib
import json
from pathlib import Path

from analysis.revenue_metrics import analyze
from analysis.comparable_games import comparable_games, REFERENCE_GENRES


class RevenueStore:
    def __init__(self, root):
        root = Path(root)
        manifest = json.loads((root / "reports/2026-10-23/revenue_sources/analysis.json").read_text(encoding="utf-8"))
        path = root / "data/processed/revenue_v1/explorer.json"
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["artifact_sha256"]:
            raise ValueError("Revenue artifact changed; rebuild before displaying")
        self.data = json.loads(data)
        rows = self.data["rows"]
        self.options = {"genres": sorted({g for r in rows for g in r["genres"]}),
                        "publishers": sorted({r["publisher_class"] for r in rows}),
                        "reference_genres": sorted(REFERENCE_GENRES & {g for r in rows for g in r["genres"]})}

    def query(self, params):
        if any(len(values) != 1 for values in params.values()):
            raise ValueError("Duplicate query parameter")
        result = analyze(self.data["rows"], {key: values[0] for key, values in params.items()})
        return {"metadata": self.data["metadata"], "options": self.options, **result}

    def references(self, request):
        return {"metadata": self.data["metadata"], **comparable_games(self.data["rows"], request)}
