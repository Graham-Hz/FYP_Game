import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if importlib.util.find_spec("sklearn") is None:
    raise unittest.SkipTest("Use experiments/model_dev_v1 environment")
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/models"))
import run_age_sensitivity as age


def sample():
    return pd.DataFrame({"app_id": list("abcdefghi"), "developer_group": list("abcdefghi"),
        "cv_fold": [0, 0, 1, 2, 2, 0, 1, 2, 0], "split": ["train"] * 9,
        "target_tier": list("ABC AABCBC".replace(" ", "")),
        "age_days": [179, 180, 365, None, 400, 500, 180, 365, 400]})


class AgeSensitivityTests(unittest.TestCase):
    def test_age_boundary_missing_and_assignments(self):
        data = sample()
        for cutoff, expected in [(180, set("bcefghi")), (365, set("cefhi"))]:
            subset = age.age_cohort(data, cutoff, [0, 1, 2])
            self.assertEqual(set(subset.app_id), expected)
            self.assertTrue(subset.cv_fold.equals(data.loc[subset.index, "cv_fold"]))
            self.assertTrue(subset.developer_group.equals(data.loc[subset.index, "developer_group"]))
        with self.assertRaises(ValueError):
            age.age_cohort(data.assign(split="test"), 180, [0, 1, 2])
        with self.assertRaises(ValueError):
            age.age_cohort(data.assign(developer_group="same"), 180, [0, 1, 2])

    def test_reference_matching_rejects_missing_duplicate_wrong_target_or_fold(self):
        data = sample()
        valid = data.loc[data.cv_fold.eq(0) & data.age_days.ge(180)]
        reference = data.loc[data.cv_fold.eq(0)].copy()
        matched = age.matched_reference(reference.iloc[::-1], valid)
        self.assertEqual(set(matched.app_id), set(valid.app_id))
        bad = [reference.loc[~reference.app_id.eq("b")], pd.concat([reference, reference.iloc[:1]]),
               reference.assign(cv_fold=2), reference.assign(target_tier="wrong")]
        for frame in bad:
            with self.assertRaises(ValueError):
                age.matched_reference(frame, valid)

    def test_atomic_completion_preserves_previous_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            age.atomic_json(path, {"status": "running"})
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                age.atomic_json(path, {"bad": float("nan")})
            self.assertEqual(path.read_bytes(), original)
            with patch.object(Path, "replace", side_effect=PermissionError("simulated interruption")):
                with self.assertRaises(PermissionError):
                    age.atomic_json(path, {"status": "complete"})
            self.assertEqual(path.read_bytes(), original)
            age.atomic_json(path, {"status": "complete"})
            self.assertEqual(age.read_json(path)["status"], "complete")
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_completed_run_checks_identity_and_output_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "result.json"
            file.write_text("original")
            run = {"identity": {"a": 1}, "status": "complete", "outputs": {file.name: age.digest(file)}, "artifacts": {}}
            with patch.object(age, "REPORT", root):
                self.assertTrue(age.completed_run_matches(run, {"a": 1}))
                with self.assertRaises(ValueError):
                    age.completed_run_matches(run, {"a": 2})
                file.write_text("changed")
                with self.assertRaises(ValueError):
                    age.completed_run_matches(run, {"a": 1})
            self.assertFalse(age.completed_run_matches({"identity": {"a": 1}, "status": "running"}, {"a": 1}))

    def test_fixed_candidates_and_fit_budget(self):
        config = age.read_json(ROOT / "config/model_age_v1.json")
        self.assertFalse(config["retune"])
        self.assertEqual(sum(map(len, config["candidates"].values())) * len(config["minimum_age_days"]) * len(config["folds"]), 84)
        age.validate_candidates(config)
        config["candidates"]["pc"][2]["C"] = 99
        with self.assertRaises(ValueError):
            age.validate_candidates(config)


if __name__ == "__main__":
    unittest.main()
