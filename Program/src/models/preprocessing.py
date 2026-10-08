"""Fold-fitted encoding for the frozen planning feature allowlist."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction import DictVectorizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/features"))
from feature_policy import select_features

NUMERIC = {"age_days", "price_observed", "price_usd"}
LISTS = {"genres", "planning_categories", "supported_languages"}


def key(kind, column, value=None):
    return json.dumps([kind, column, value], ensure_ascii=False, separators=(",", ":"))


class PlanningEncoder(TransformerMixin, BaseEstimator):
    def __init__(self, platform, feature_set):
        self.platform = platform
        self.feature_set = feature_set

    def _frame(self, X):
        return select_features(X, self.platform, self.feature_set)

    @staticmethod
    def _numeric(values):
        array = pd.to_numeric(values, errors="raise").to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(array).any() or (array[~np.isnan(array)] < 0).any():
            raise ValueError("Numeric planning features must be finite and nonnegative or missing")
        return np.log1p(array)

    def fit(self, X, y=None):
        frame = self._frame(X)
        self.numeric_stats_ = {}
        self.columns_ = list(frame.columns)
        for column in self.columns_:
            if column in NUMERIC:
                values = self._numeric(frame[column])
                median = float(np.nanmedian(values)) if np.isfinite(values).any() else 0.0
                imputed = np.where(np.isnan(values), median, values)
                std = float(imputed.std())
                self.numeric_stats_[column] = {"median": median, "mean": float(imputed.mean()), "std": std if std > 0 else 1.0}
        self.vectorizer_ = DictVectorizer(sparse=True, sort=True)
        self.vectorizer_.fit(self._records(frame))
        return self

    def _records(self, frame):
        numeric_values = {}
        for column, stats in self.numeric_stats_.items():
            values = self._numeric(frame[column])
            missing = np.isnan(values)
            numeric_values[column] = ((np.where(missing, stats["median"], values) - stats["mean"]) / stats["std"], missing)
        for index, row in enumerate(frame.itertuples(index=False, name=None)):
            record = {}
            for column, value in zip(self.columns_, row):
                if column in NUMERIC:
                    scaled, missing = numeric_values[column]
                    record[key("numeric", column)] = float(scaled[index])
                    record[key("missing", column)] = float(missing[index])
                elif column in LISTS:
                    if value is not None:
                        for token in set(value):
                            record[key("token", column, str(token))] = 1.0
                else:
                    token = "<unknown>" if pd.isna(value) else str(value)
                    record[key("category", column, token)] = 1.0
            yield record

    def transform(self, X):
        return self.vectorizer_.transform(self._records(self._frame(X)))

    def coverage(self, X):
        vocabulary = self.vectorizer_.vocabulary_
        total, unknown, rows_unknown = 0, 0, 0
        columns = {}
        for record in self._records(self._frame(X)):
            unseen = [name for name in record if name not in vocabulary]
            total += len(record)
            unknown += len(unseen)
            rows_unknown += bool(unseen)
            for name in unseen:
                column = json.loads(name)[1]
                columns[column] = columns.get(column, 0) + 1
        return {"validation_rows": len(X), "rows_with_unknown": rows_unknown,
                "encoded_keys": total, "unknown_keys": unknown, "unknown_by_column": columns}

    def get_feature_names_out(self, input_features=None):
        return self.vectorizer_.get_feature_names_out()
