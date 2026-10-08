import sys
import unittest
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if importlib.util.find_spec("sklearn") is None:
    raise unittest.SkipTest("Run model tests in the separate experiments/model_dev_v1 environment")
sys.path.insert(0, str(ROOT / "src/models"))
from preprocessing import PlanningEncoder, key


def mobile(categories, prices, free):
    return pd.DataFrame({"category": categories, "content_rating": ["Everyone"]*len(categories),
                         "free": free, "price_usd": prices, "price_usd_unavailable": pd.isna(prices),
                         "ad_supported": [False]*len(categories), "in_app_purchases": [True]*len(categories),
                         "free_unavailable": pd.isna(free)})


class EncodingTests(unittest.TestCase):
    def test_validation_does_not_change_vocabulary_or_numeric_statistics(self):
        train = mobile(["Puzzle", "Action"], [0, 2], [True, False])
        valid = mobile(["Unseen"], [999], [True])
        encoder = PlanningEncoder("mobile", "P").fit(train)
        before = dict(encoder.vectorizer_.vocabulary_)
        mean = encoder.numeric_stats_["price_usd"]["mean"]
        self.assertEqual(encoder.transform(valid).shape[1], len(before))
        self.assertEqual(encoder.vectorizer_.vocabulary_, before)
        self.assertAlmostEqual(mean, np.log1p(2)/2)
        self.assertEqual(encoder.numeric_stats_["price_usd"]["mean"], mean)
        self.assertEqual(encoder.coverage(valid)["unknown_by_column"], {"category": 1})

    def test_unknown_free_is_distinct_from_false(self):
        train = mobile(["Puzzle"]*3, [0, 1, np.nan], [True, False, pd.NA])
        encoder = PlanningEncoder("mobile", "P").fit(train)
        matrix = encoder.transform(train).toarray()
        vocab = encoder.vectorizer_.vocabulary_
        self.assertEqual(matrix[1, vocab[key("category", "free", "False")]], 1)
        self.assertEqual(matrix[2, vocab[key("category", "free", "False")]], 0)
        self.assertEqual(matrix[2, vocab[key("category", "free", "<unknown>")]], 1)

    def test_missing_numeric_imputed_from_fit_and_flagged(self):
        encoder = PlanningEncoder("mobile", "P").fit(mobile(["Puzzle"]*2, [0, 2], [True, False]))
        result = encoder.transform(mobile(["Puzzle"], [np.nan], [True])).toarray()[0]
        self.assertAlmostEqual(result[encoder.vectorizer_.vocabulary_[key("numeric", "price_usd")]], 0)
        self.assertEqual(result[encoder.vectorizer_.vocabulary_[key("missing", "price_usd")]], 1)

    def test_outcomes_and_ids_never_enter_predictors(self):
        data = mobile(["Puzzle"], [0], [True]).assign(app_id="secret", target_tier="M3", installs=999999)
        encoder = PlanningEncoder("mobile", "P").fit(data)
        self.assertFalse(any(token in name for name in encoder.get_feature_names_out() for token in ("secret", "target_tier", "installs", "app_id")))

    def test_multilabel_presence_and_unknown_tokens(self):
        data = pd.DataFrame({"genres": [["Action", "Action"]], "planning_categories": [[]],
            "supported_languages": [["English"]], "windows": [True], "mac": [False], "linux": [False],
            "categories_unavailable": [False], "languages_unavailable": [False]})
        encoder = PlanningEncoder("pc", "P_without_price").fit(data)
        result = encoder.transform(data).toarray()[0]
        self.assertEqual(result[encoder.vectorizer_.vocabulary_[key("token", "genres", "Action")]], 1)
        valid = data.copy()
        valid.at[0, "genres"] = ["NovelGenre"]
        self.assertEqual(encoder.coverage(valid)["rows_with_unknown"], 1)

    def test_all_missing_age_stays_finite_and_negative_rejected(self):
        encoder = PlanningEncoder("pc", "age_only").fit(pd.DataFrame({"age_days": [np.nan, np.nan]}))
        self.assertTrue(np.isfinite(encoder.transform(pd.DataFrame({"age_days": [np.nan, 5]})).toarray()).all())
        with self.assertRaises(ValueError):
            encoder.transform(pd.DataFrame({"age_days": [-1]}))


if __name__ == "__main__":
    unittest.main()
