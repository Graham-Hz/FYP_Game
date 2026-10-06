"""Select only approved columns; IDs are an index, never a predictor."""
import json
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[2] / "config/feature_policy_v1.json"


def select_features(frame, platform, feature_set="P", policy=None):
    policy = policy or json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    columns = policy[platform][feature_set]
    forbidden = set(policy["forbidden_predictors"])
    if forbidden.intersection(columns):
        raise ValueError("Feature allowlist includes a forbidden predictor")
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    return frame.loc[:, columns].copy()
