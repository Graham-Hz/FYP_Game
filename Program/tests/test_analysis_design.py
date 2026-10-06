import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/data"))
sys.path.insert(0, str(ROOT / "src/features"))
from group_splits import pc_components, normalize_developer, partition
from feature_policy import select_features


class AnalysisDesignTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/analysis_v1.json").read_text())
        self.placeholders = self.config["developer_placeholder_tokens"]

    def test_excluded_game_still_bridges_developers(self):
        records = [("A", ["Studio A"]), ("excluded", ["Studio A", "Studio B"]), ("B", ["Studio B"]), ("C", ["Other"])]
        groups, _ = pc_components(records, self.placeholders)
        self.assertEqual(groups["A"], groups["B"])
        self.assertNotEqual(groups["A"], groups["C"])
        reversed_groups, _ = pc_components(list(reversed(records)), self.placeholders)
        self.assertEqual(groups, reversed_groups)

    def test_placeholder_not_shared_studio(self):
        groups, _ = pc_components([("1", ["None"]), ("2", []), ("3", ["None", "Actual studio"])], self.placeholders)
        self.assertIsNone(groups["1"])
        self.assertIsNone(groups["2"])
        self.assertIsNotNone(groups["3"])

    def test_normalization_retains_punctuation(self):
        self.assertEqual(normalize_developer("  ＡＢＣ  Studio "), "abc studio")
        self.assertNotEqual(normalize_developer("A,B"), normalize_developer("AB"))

    def test_split_is_group_deterministic_and_cv_train_only(self):
        outcomes = [partition(f"group_{i}", "pc", self.config) for i in range(100)]
        self.assertEqual(outcomes, [partition(f"group_{i}", "pc", self.config) for i in range(100)])
        self.assertEqual({x[0] for x in outcomes}, {"train", "calibration", "test"})
        for split, fold in outcomes:
            if split == "train": self.assertIn(fold, [0,1,2])
            else: self.assertIsNone(fold)

    def test_feature_selection_excludes_target_identity_and_age_from_P(self):
        policy = json.loads((ROOT / "config/feature_policy_v1.json").read_text())
        for platform in ["pc", "mobile"]:
            columns = set(policy[platform]["P+A"]) | set(policy["forbidden_predictors"])
            frame = pd.DataFrame({c:[0] for c in columns})
            selected = select_features(frame, platform, "P")
            self.assertEqual(list(selected.columns), policy[platform]["P"])
            self.assertNotIn("age_days", selected)
            self.assertFalse(set(selected).intersection(policy["forbidden_predictors"]))
        policy["pc"]["P"].append("target_tier")
        with self.assertRaises(ValueError):select_features(frame,"pc","P",policy)


if __name__ == "__main__":unittest.main()
