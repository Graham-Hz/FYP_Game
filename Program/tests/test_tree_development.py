import importlib.util
import json
import sys
import unittest
from pathlib import Path

if importlib.util.find_spec("sklearn") is None:
    raise unittest.SkipTest("Use experiments/model_dev_v1 environment")
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/models"))
from run_tree_development import choose, configurations, subgroup_rows, validate_train


class TreeDevelopmentTests(unittest.TestCase):
    def test_reject_holdout_duplicate_ids_and_group_leakage(self):
        data = pd.DataFrame({"app_id": ["a", "b", "c"], "developer_group": ["x", "y", "z"],
                             "split": ["train"] * 3, "cv_fold": [0, 1, 2]})
        validate_train(data, [0, 1, 2])
        for column, values in [("split", ["train", "test", "train"]), ("app_id", ["a", "a", "c"]),
                               ("developer_group", ["x", "x", "z"]), ("cv_fold", [0, 1, 1])]:
            with self.subTest(column=column), self.assertRaises(ValueError):
                validate_train(data.assign(**{column: values}), [0, 1, 2])

    def test_complete_prespecified_grid(self):
        config = json.loads((ROOT / "config/model_tree_v1.json").read_text())
        pc, mobile = list(configurations("pc", config)), list(configurations("mobile", config))
        self.assertEqual((len(pc), len(mobile)), (12, 8))
        self.assertEqual(len({s["id"] for s in pc}), 12)
        self.assertEqual({s["features"] for s in pc}, {"P", "P+A", "P_without_price"})

    def test_tie_prefers_simpler_then_unweighted_and_rejects_missing_folds(self):
        rows = pd.DataFrame({"platform": ["pc"] * 3, "features": ["P"] * 3, "folds": [3] * 3,
            "configuration": ["complex", "balanced", "simple"], "macro_f1_mean": [.5000005, .5, .5],
            "macro_f1_sd": [.01] * 3, "weight": ["none", "balanced", "none"], "max_leaf_nodes": [1024, 256, 256]})
        self.assertEqual(choose(rows)[0]["configuration"], "simple")
        with self.assertRaises(ValueError):
            choose(rows.assign(folds=[3, 2, 3]))
        with self.assertRaises(ValueError):
            choose(rows.assign(macro_f1_mean=[float("nan"), .5, .5]))

    def test_age_boundary_and_unknown_free_remain_separate(self):
        data = pd.DataFrame({"app_id": ["a", "b", "c", "d"], "age_days": [179, 180, 365, None],
                             "free": [True, False, pd.NA, True]})
        pred = pd.DataFrame({"app_id": data.app_id, "target_tier": ["a", "b", "c", "a"],
                             "predicted_tier": ["a", "b", "a", "a"]})
        rows = {r["subgroup"]: r for r in subgroup_rows(pred, data, ["a", "b", "c"], {"platform": "mobile"}, [180, 365])}
        self.assertEqual(rows["age_ge_180"]["n"], 2)
        self.assertEqual(rows["age_ge_365"]["n"], 1)
        self.assertEqual([rows[k]["n"] for k in ["free", "paid", "unknown"]], [2, 1, 1])
        self.assertAlmostEqual(rows["paid"]["macro_f1_fixed_three_labels"], 1 / 3)
        self.assertEqual(rows["unknown"]["support_2"], 1)


if __name__ == "__main__":
    unittest.main()
