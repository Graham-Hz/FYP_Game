"""Reference ranking uses gameplay overlap and price, not outcomes."""
import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from analysis.comparable_games import comparable_games, REFERENCE_GENRES, METHOD
from analysis.game_taxonomy import GAMEPLAY_GENRES
from server import make_server


def row(ident, genres, price, revenue=1):
    return {"steam_id": str(ident), "name": str(ident), "genres": genres,
            "price": price, "revenue": revenue}


def request(**changes):
    return {"genres": ["Action", "Adventure"], "price": 10, "limit": 5,
            "price_factor": 2, **changes}


class ReferenceTests(unittest.TestCase):
    def test_shared_gameplay_taxonomy_excludes_play_form_from_similarity(self):
        self.assertEqual(REFERENCE_GENRES, GAMEPLAY_GENRES)
        result = comparable_games([row(1, ["Action", "Massively Multiplayer"], 10),
                                   row(2, ["Massively Multiplayer"], 10)], request(genres=["Action"]))
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["rows"][0]["match"]["genre_similarity"], 1)
        self.assertEqual(result["rows"][0]["genres"], ["Action", "Massively Multiplayer"])
        self.assertEqual(result["method"]["label_taxonomy"]["gameplay_genres"], sorted(GAMEPLAY_GENRES))
        with self.assertRaises(ValueError):
            comparable_games([], request(genres=["Massively Multiplayer"]))

    def test_priority_overlap_then_price_then_numeric_id(self):
        rows = [row(99, ["Action"], 10, 10000000), row(10, ["Action", "Adventure"], 10),
                row(2, ["Action", "Adventure", "Indie", "Early Access"], 10),
                row(5, ["Action", "Adventure"], 12)]
        result = comparable_games(rows, request())
        self.assertEqual([r["steam_id"] for r in result["rows"]], ["2", "10", "5", "99"])
        self.assertEqual(result["rows"][0]["match"]["genre_similarity"], 1)
        self.assertEqual(result["rows"][-1]["match"]["genre_similarity"], .5)
        tied_prices = [row(2, ["Action"], 9.99), row(9, ["Action"], 19.99)]
        self.assertEqual([r["steam_id"] for r in comparable_games(tied_prices, request(price=14.99))["rows"]], ["2", "9"])

    def test_revenue_publisher_and_input_order_do_not_affect_ranking(self):
        original = [row(i, ["Action"], i, revenue=i*100) for i in range(1, 20)]
        baseline = comparable_games(original, request())
        changed = copy.deepcopy(original)
        for r in changed:
            r["revenue"] = 1e9 - r["revenue"]
            r["publisher_class"] = "AAA"
        changed.reverse()
        self.assertEqual([r["steam_id"] for r in baseline["rows"]],
                         [r["steam_id"] for r in comparable_games(changed, request())["rows"]])

    def test_exact_boundaries_missing_genres_and_no_fallback(self):
        rows = [row(1, ["Action"], 5), row(2, ["Action"], 20), row(3, ["Action"], 20.01),
                row(4, ["Action"], 4.99), row(5, ["Strategy"], 10), row(6, [], 10),
                row(7, ["Indie", "Utilities"], 10), row(8, ["Action"], 0)]
        result = comparable_games(rows, request())
        self.assertEqual({r["steam_id"] for r in result["rows"]}, {"1", "2"})
        self.assertEqual(result["status"], "fewer_than_requested")
        self.assertEqual(result["coverage"]["source_rows"], 8)
        self.assertEqual(result["coverage"]["supported_genre_rows"], 6)
        self.assertEqual(result["coverage"]["same_price_cohort_rows"], 5)
        self.assertEqual(result["coverage"]["shared_genre_rows"], 4)
        self.assertEqual(result["coverage"]["within_price_range_rows"], 2)
        self.assertEqual(comparable_games(rows, request(price=1000))["rows"], [])
        # Binary floating point must not drop a candidate exactly at 10.1 * 3.
        decimal_boundary = comparable_games([row(1, ["Action"], 30.3)], request(price=10.1, price_factor=3))
        self.assertEqual(decimal_boundary["returned_count"], 1)

    def test_zero_price_is_separate_even_without_ratio_constraint(self):
        rows = [row(1, ["Action"], 0), row(2, ["Action"], .01)]
        result = comparable_games(rows, request(price=0, price_factor=None))
        self.assertEqual([r["steam_id"] for r in result["rows"]], ["1"])
        self.assertEqual(result["price_range"], {"minimum": 0, "maximum": 0, "inclusive": True})

    def test_bad_inputs_are_rejected(self):
        invalid = [None, {}, request(genres=[]), request(genres=["Action", "Action"]),
                   request(genres=["Indie"]), request(genres=[{}]), request(price=True),
                   request(price=float("nan")), request(price=float("inf")), request(price=-1),
                   request(price="10"), request(price=1001), request(price=10**1000), request(limit=5.0),
                   request(limit=True), request(price_factor=True), request(price_factor=0)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                comparable_games([], value)


class ReferenceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(SimpleNamespace(root=ROOT), 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/api/references"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_actual_candidates_and_export_provenance(self):
        raw = json.loads((ROOT / "data/processed/revenue_v1/explorer.json").read_text(encoding="utf-8"))
        with urlopen(Request(self.url, data=json.dumps(request()).encode(), headers={"Content-Type": "application/json"})) as response:
            result = json.load(response)
        expected = [r for r in raw["rows"] if 5 <= r["price"] <= 20 and set(r["genres"]) & {"Action", "Adventure"}]
        self.assertEqual(result["candidate_count"], len(expected))
        self.assertEqual(result["returned_count"], 5)
        self.assertEqual(result["metadata"]["source_sha256"], raw["metadata"]["source_sha256"])
        self.assertEqual(result["method"]["version"], "genre_price_references_v2")
        for row in result["rows"]:
            self.assertTrue(set(row["match"]["shared_genres"]) & {"Action", "Adventure"})
            self.assertTrue(5 <= row["price"] <= 20)

    def test_metadata_exposes_reference_method_version(self):
        with urlopen(self.url.removesuffix("/api/references") + "/api/revenue/metadata") as response:
            result = json.load(response)
        self.assertEqual(result["options"]["reference_method_version"], METHOD["version"])
        self.assertNotIn("Massively Multiplayer", result["options"]["reference_genres"])
        groups = result["options"]["genre_groups"]
        self.assertEqual(set(groups[0]["values"]), GAMEPLAY_GENRES & set(result["options"]["genres"]))
        self.assertEqual({value for group in groups for value in group["values"]}, set(result["options"]["genres"]))
        self.assertIn("Indie", next(group["values"] for group in groups if group["id"] == "production"))

    def test_revenue_source_label_filter_retains_original_semantics(self):
        with urlopen(self.url.removesuffix("/api/references") + "/api/revenue?genre=Indie") as response:
            result = json.load(response)
        self.assertEqual(result["filters"]["genre"], "Indie")
        self.assertTrue(result["rows"])
        self.assertTrue(all("Indie" in row["genres"] for row in result["rows"]))

    def test_invalid_and_cross_origin_requests_fail(self):
        cases = [({}, {}, 400), (request(), {"Origin": "https://example.com"}, 403),
                 (request(price="nan"), {}, 400)]
        for payload, headers, status in cases:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}))
            self.assertEqual(error.exception.code, status)
            error.exception.close()

    def test_missing_artifact_has_explicit_unavailable_response(self):
        with tempfile.TemporaryDirectory() as folder:
            server = make_server(SimpleNamespace(root=Path(folder)), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(f"http://127.0.0.1:{server.server_port}/api/references", data=json.dumps(request()).encode()))
                self.assertEqual(error.exception.code, 503)
                error.exception.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
