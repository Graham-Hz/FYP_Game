"""Regression checks for data-loss and target-definition edge cases."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/data"))
from cleaning_rules import boolean, collection, install_tiers, nonnegative, owner_interval, title_missing


class CleaningRulesTests(unittest.TestCase):
    def test_literal_titles_are_preserved(self):
        for title in ["None", "NULL", "none", "N/A", "nan", "0"]:
            self.assertFalse(title_missing(title))
        for title in [None, pd.NA, float("nan"), "", "  "]:
            self.assertTrue(title_missing(title))

    def test_developer_names_are_not_split_on_commas(self):
        self.assertEqual(collection("['Studio, Inc.', 'Second Studio']"), (["Studio, Inc.", "Second Studio"], "valid"))
        for malformed in ["Studio, Inc.", "{'Studio': 1}", "[1]", "['unfinished'"]:
            self.assertEqual(collection(malformed), ([], "invalid"))

    def test_unknown_owners_and_straddling_intervals_stay_unlabelled(self):
        self.assertEqual(owner_interval("0 - 0")[2:], (None, "unknown_0_0"))
        self.assertEqual(owner_interval("0 - 50000")[2:], (None, "straddles_threshold"))
        for invalid in ["20000 - 1", "-1 - 0", "sold 300", "unknown"]:
            self.assertEqual(owner_interval(invalid)[3], "invalid")
        for interval, prefix in [("0 - 20000", "O1"), ("20000 - 50000", "O2"), ("50000 - 100000", "O2"), ("100000 - 200000", "O3")]:
            self.assertTrue(owner_interval(interval)[2].startswith(prefix))

    def test_installs_require_finite_nonnegative_integers(self):
        values = nonnegative(pd.Series(["-1", "0", "999", "1000", "99999", "100000", "1.5", "inf", None]), integer=True)
        self.assertEqual(values.isna().tolist(), [True, False, False, False, False, False, True, True, True])
        self.assertEqual(install_tiers(values).dropna().tolist(), ["M1_under_1k", "M1_under_1k", "M2_1k_to_under_100k", "M2_1k_to_under_100k", "M3_100k_plus"])

    def test_boolean_unknown_is_not_false(self):
        values = boolean(pd.Series(["True", "False", None, "unknown", " true "]))
        self.assertEqual(values.isna().tolist(), [False, False, True, True, False])
        self.assertEqual(values.dropna().tolist(), [True, False, True])


if __name__ == "__main__":
    unittest.main()
