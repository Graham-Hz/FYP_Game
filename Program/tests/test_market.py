"""Independent aggregate checks, source boundaries and active-version behaviour."""
import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server
from market import MarketStore
from revenue import RevenueStore
from imports.repository import DEFAULT_VERSION
from test_csv_import import metadata, mobile, pc, raw
from market_taxonomy import GAMEPLAY_GENRES, tag_groups


def request(source='pc', **changes):
    return dict(source=source, version_id=DEFAULT_VERSION,
                group='', year_from=None, year_to=None, top_n=10,
                rank_metric='volume') | changes


def chart(result, ident):
    return next(c for c in result['charts'] if c['id'] == ident)


class MarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.store = ComparisonStore(app_path=Path(cls.folder.name))
        cls.revenue = RevenueStore(ROOT)
        cls.market = MarketStore(cls.store, cls.revenue)

    @classmethod
    def tearDownClass(cls):
        cls.store.db.close()
        cls.folder.cleanup()

    def tearDown(self):
        for platform in ('pc', 'mobile'):
            if self.store.active[platform] != DEFAULT_VERSION:
                self.store.activate(platform, DEFAULT_VERSION)

    def test_research_aggregates_and_date_coverage(self):
        for platform, size, missing in [('pc', 51152, 1), ('mobile', 221806, 0)]:
            result = self.market.query(request(platform))
            self.assertFalse(result['empty'])
            self.assertEqual(sum(r['values'][0] for r in chart(result, 'outcome_tiers')['rows']), size)
            self.assertEqual(sum(r['values'][0] for r in chart(result, 'release_count')['rows']), size-missing)
            self.assertEqual(result['provenance']['missing_detail_rows'], missing)
            self.assertEqual(result['provenance']['partition'], 'train')
            self.assertGreaterEqual(len(result['charts']), 8)
            self.assertIn('release', result['provenance']['temporal_basis'].lower())
            json.dumps(result, allow_nan=False)

    def test_genre_volume_and_median_equal_independent_candidate_join(self):
        result = self.market.query(request('pc', group='Action'))
        candidate = str(ROOT / 'data/interim/cleaning_candidate_v1/pc_candidates.parquet')
        features = str(ROOT / 'data/processed/analysis_v1/pc_features.parquet')
        labels = str(ROOT / 'data/processed/analysis_v1/pc_labels_splits.parquet')
        with duckdb.connect() as db:
            expected = db.execute('''SELECT sum(c.owners_lower), sum(c.owners_upper),
                median(c.owners_lower), median(c.owners_upper)
                FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id)
                LEFT JOIN read_parquet(?) c USING(app_id)
                WHERE l.split='train' AND list_contains(f.genres, 'Action')''',
                [features, labels, candidate]).fetchone()
        for ident, values in [('group_volume_total', expected[:2]), ('group_volume_median', expected[2:])]:
            row = next(r for r in chart(result, ident)['rows'] if r['label'].split(' (')[0].split('（')[0] == 'Action')
            self.assertEqual(row['values'], list(values))
        self.assertTrue(all(r['volume_lower'] <= r['volume_upper'] for r in result['leaders']['rows']))
        train_ids = {r[0] for r in self.store.db.execute('SELECT app_id FROM pc').fetchall()}
        self.assertTrue({r['app_id'] for r in result['leaders']['rows']} <= train_ids)

    def test_mobile_filtered_release_cohort_equals_source(self):
        result = self.market.query(request('mobile', group='Puzzle', year_from=2020, year_to=2020))
        path = str(ROOT / 'data/interim/cleaning_candidate_v1/mobile_candidates.parquet')
        expected = self.store.db.execute('''SELECT count(*),sum(c.minimum_installs)
            FROM mobile m JOIN read_parquet(?) c USING(app_id)
            WHERE m.category='Puzzle' AND year(c.release_date)=2020''', [path]).fetchone()
        self.assertEqual(sum(r['values'][0] for r in chart(result, 'release_count')['rows']), expected[0])
        self.assertEqual(chart(result, 'group_volume_total')['rows'][0]['values'][0], expected[1])
        self.assertTrue(all(r['release_date'].startswith('2020-') for r in result['leaders']['rows']))

    def test_revenue_is_separate_selected_cohort_and_ranking(self):
        source = next(s for s in self.market.options()['sources'] if s['id'] == 'revenue')
        result = self.market.query(request('revenue', version_id=source['version_id'], rank_metric='revenue'))
        expected = sorted(self.revenue.data['rows'], key=lambda r: (-r['revenue'], int(r['steam_id'])))[:10]
        self.assertEqual({r['steam_id'] for r in result['leaders']['rows']}, {r['steam_id'] for r in expected})
        self.assertEqual(sum(r['values'][0] for r in chart(result, 'release_count')['rows']), 1500)
        self.assertAlmostEqual(chart(result, 'revenue_concentration')['rows'][-1]['values'][0], 100)
        self.assertNotEqual(result['provenance']['partition'], 'train')

    def test_import_uses_checked_source_and_only_eligible_rows(self):
        first = mobile(); first.update(app_id='fixture.a', minimum_installs='0', free='', price='', release_date='2018-01-01')
        second = mobile(); second.update(app_id='fixture.b', minimum_installs='100000', release_date='2020-01-01')
        excluded = mobile(); excluded.update(app_id='fixture.excluded', category='Sports', minimum_installs='999999999')
        saved = self.store.repository.save(raw([first, second, excluded]), metadata())
        ident = saved['version_id']
        self.store.activate('mobile', ident)
        source = next(s for s in self.market.options()['sources'] if s['id'] == 'mobile')
        self.assertEqual(source['version_id'], ident)
        result = self.market.query(request('mobile', version_id=ident))
        self.assertEqual(result['provenance']['partition'], 'application_snapshot')
        self.assertEqual({r['app_id'] for r in result['leaders']['rows']}, {'fixture.a','fixture.b'})
        self.assertEqual(chart(result, 'group_volume_total')['rows'][0]['values'][0], 100000)
        self.assertEqual(sum(r['values'][0] for r in chart(result, 'release_count')['rows']), 2)
        self.assertFalse(chart(result, 'group_high_tier_share')['rows'])
        with self.assertRaises(ValueError):
            self.market.query(request('mobile'))
        self.store.activate('mobile', DEFAULT_VERSION)
        with self.assertRaises(ValueError):
            self.market.query(request('mobile', version_id=ident))

    def test_steam_import_retains_intervals_and_date_filter(self):
        a = pc(); a.update(app_id='100', release_date='2017-01-01', genres='["Action", "RPG"]')
        b = pc(); b.update(app_id='200', owner_lower='100000', owner_upper='200000', release_date='2020-01-01')
        ident = self.store.repository.save(raw([a,b], 'pc'), metadata('pc'))['version_id']
        self.store.activate('pc', ident)
        result = self.market.query(request('pc', version_id=ident, year_from=2020))
        self.assertEqual(chart(result, 'group_volume_total')['rows'][0]['values'], [100000,200000])
        self.assertEqual([r['app_id'] for r in result['leaders']['rows']], ['200'])

    def test_empty_selection_is_not_zero_performance(self):
        result = self.market.query(request('mobile', year_from=2024, year_to=2025))
        self.assertTrue(result['empty'])
        self.assertFalse(result['leaders']['rows'])
        for c in result['charts']:
            self.assertTrue(not c['rows'] or all(v is None or v == 0 for r in c['rows'] for v in r['values']))

    def test_invalid_queries_rejected(self):
        changes = [{'source':[]}, {'source':'test'}, {'version_id':'old'}, {'group':"' OR true --"},
                   {'year_from':True}, {'year_to':'2020'}, {'year_from':2020,'year_to':2010},
                   {'top_n':500}, {'rank_metric':'revenue'}, {'split':'test'}, {'group':[]}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.market.query(request(**change))

    def test_optional_source_unavailable_does_not_remove_other_sources(self):
        market = MarketStore(self.store, None)
        sources = {s['id']:s for s in market.options()['sources']}
        self.assertFalse(sources['revenue']['available'])
        self.assertTrue(sources['pc']['available'])
        with self.assertRaises(ValueError):
            market.query(request('revenue', version_id=sources['revenue']['version_id']))

    def test_missing_revenue_month_has_no_invented_median(self):
        rows = [dict(self.revenue.data['rows'][0]), dict(self.revenue.data['rows'][1])]
        rows[0]['release_date'] = '2024-01-10'
        rows[1]['release_date'] = '2024-03-10'
        fixture = SimpleNamespace(data={'metadata':self.revenue.data['metadata'], 'rows':rows})
        result = MarketStore(self.store, fixture).query(request('revenue', version_id=fixture.data['metadata']['version']))
        counts = {r['label']:r['values'] for r in chart(result, 'release_count')['rows']}
        medians = {r['label']:r['values'] for r in chart(result, 'release_volume_median')['rows']}
        self.assertEqual(counts, {'2024-01':[1], '2024-02':[0], '2024-03':[1]})
        self.assertEqual(medians['2024-02'], [None])

    def test_unsafe_integer_is_not_silently_rounded_for_browser(self):
        row = mobile(); row['minimum_installs'] = str(2**53)
        ident = self.store.repository.save(raw([row]), metadata())['version_id']
        self.store.activate('mobile', ident)
        with self.assertRaises(ValueError):
            self.market.query(request('mobile', version_id=ident))

    def test_source_hash_failure_disables_only_affected_source(self):
        from unittest.mock import patch
        import market as module
        real_sha = module._sha
        def modified(path):
            return '0'*64 if path.name == 'pc_candidates.parquet' else real_sha(path)
        with patch.object(module, '_sha', side_effect=modified):
            sources = {s['id']:s for s in MarketStore(self.store, self.revenue).options()['sources']}
        self.assertFalse(sources['pc']['available'])
        self.assertTrue(sources['mobile']['available'])
        self.assertTrue(sources['revenue']['available'])

    def test_gameplay_options_separate_other_source_labels(self):
        sources = {s['id']:s for s in self.market.options()['sources']}
        for platform in ('pc','revenue'):
            spec = sources[platform]
            self.assertTrue(set(spec['groups']) <= GAMEPLAY_GENRES)
            self.assertFalse(set(spec['groups']) & {'Indie','Early Access','Sexual Content','Accounting','Massively Multiplayer'})
            tags = {v for g in spec['tag_groups'] for v in g['values']}
            self.assertFalse(tags & set(spec['groups']))
        content = next(g['values'] for g in sources['pc']['tag_groups'] if g['id']=='content')
        self.assertIn('Sexual Content', content)
        self.assertFalse(sources['mobile']['tag_groups'])
        self.assertEqual(len(sources['mobile']['groups']), 16)
        with self.assertRaises(ValueError):
            self.market.query(request(group='Sexual Content'))
        with self.assertRaises(ValueError):
            self.market.query(request('mobile', tag='Indie'))

    def test_content_filter_and_gameplay_filter_use_same_rows_without_mixed_groups(self):
        result = self.market.query(request(tag='Sexual Content'))
        expected = self.store.db.execute("SELECT count(*) FROM pc WHERE list_contains(genres, 'Sexual Content')").fetchone()[0]
        self.assertEqual(result['provenance']['filtered_rows'], expected)
        labels = {r['label'] for r in chart(result, 'group_count')['rows']}
        self.assertTrue(labels <= GAMEPLAY_GENRES)
        self.assertNotIn('Sexual Content', labels)
        self.assertTrue(all(r['filter']['group']==r['label'] for r in chart(result, 'group_count')['rows']))
        subset = self.market.query(request(group='Action', tag='Sexual Content'))
        expected = self.store.db.execute("SELECT count(*) FROM pc WHERE list_contains(genres, 'Sexual Content') AND list_contains(genres, 'Action')").fetchone()[0]
        self.assertEqual(subset['provenance']['filtered_rows'], expected)
        self.assertIn('Sexual Content', chart(subset, 'group_count')['source'])
        self.assertTrue(all('Sexual Content' in r['source_tags'] for r in subset['leaders']['rows']))

    def test_unknown_import_label_stays_available_without_becoming_genre(self):
        row=pc(); row['genres']='["Action", "Future Label"]'
        ident=self.store.repository.save(raw([row], 'pc'), metadata('pc'))['version_id']
        self.store.activate('pc', ident)
        result=self.market.query(request(version_id=ident, tag='Future Label'))
        self.assertEqual(result['source']['groups'], ['Action'])
        self.assertEqual(result['source']['data_kind'], 'synthetic')
        self.assertEqual(result['source']['tag_groups'], [{'id':'other','label':'其他來源標籤（未分類）','values':['Future Label']}])
        self.assertEqual(result['provenance']['filtered_rows'], 1)
        self.assertIn('label_taxonomy', result['provenance'])

    def test_http_routes_and_serializable_response(self):
        server = make_server(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            for path in ['/market','/market.js','/market.css','/charts.js','/charts.css','/api/market/options']:
                with urlopen(url+path) as response:
                    self.assertEqual(response.status, 200)
            with urlopen(Request(url+'/api/market', data=json.dumps(request()).encode(), headers={'Content-Type':'application/json'})) as response:
                self.assertFalse(json.load(response)['empty'])
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url+'/api/market', data=b'{}', headers={'Content-Type':'application/json'}))
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_overlapping_market_reads_are_not_rejected_as_duplicate_uploads(self):
        from unittest.mock import patch
        started, release = threading.Event(), threading.Event()
        original = MarketStore.query
        def delayed(instance, payload):
            if payload['source']=='pc':
                started.set()
                if not release.wait(10):
                    raise AssertionError('Concurrent read fixture did not release')
            return original(instance, payload)
        with patch.object(MarketStore, 'query', delayed):
            server=make_server(self.store, 0)
            thread=threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            url=f'http://127.0.0.1:{server.server_port}/api/market'
            def fetch(platform):
                with urlopen(Request(url, data=json.dumps(request(platform)).encode(), headers={'Content-Type':'application/json'}), timeout=15) as response:
                    return response.status, json.load(response)
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first=pool.submit(fetch, 'pc')
                    try:
                        self.assertTrue(started.wait(5))
                        status, data=pool.submit(fetch, 'mobile').result(timeout=10)
                        self.assertEqual(status, 200)
                        self.assertEqual(data['source']['id'], 'mobile')
                    finally:
                        release.set()
                    self.assertEqual(first.result(timeout=10)[0], 200)
            finally:
                release.set(); server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
