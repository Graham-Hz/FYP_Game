"""Independent cohort denominators, shared filters and bounded record drill-down."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore
from market import MarketStore, TIERS
from market_cohorts import compare, quartiles
from revenue import RevenueStore
from imports.repository import DEFAULT_VERSION
from test_csv_import import metadata, mobile, pc, raw


def analysis(source='mobile', **changes):
    return dict(source=source, version_id=DEFAULT_VERSION, group='Adventure',
                tag='', compare_group='', year_from=None, year_to=None,
                top_n=10, rank_metric='volume') | changes


def records(query=None, **changes):
    return dict(analysis=query or analysis(), cohort='selected', tier='', q='',
                page=1, page_size=20, sort='title') | changes


def find_chart(result, ident):
    return next(item for item in result['charts'] if item['id'] == ident)


class CohortTests(unittest.TestCase):
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
        for source in ('pc', 'mobile'):
            if self.store.active[source] != DEFAULT_VERSION:
                self.store.activate(source, DEFAULT_VERSION)

    def test_adventure_complement_preserves_equal_median_but_different_distribution(self):
        result = self.market.query(analysis())
        comparison = result['comparison']
        chosen, other = comparison['selected'], comparison['baseline']
        self.assertEqual((chosen['n'], other['n'], comparison['overlap_count']), (15795, 206011, 0))
        self.assertEqual(chosen['statistics']['volume_lower'], {'n':15795, 'q1':100, 'median':1000, 'q3':10000})
        self.assertEqual(other['statistics']['volume_lower'], {'n':206011, 'q1':50, 'median':1000, 'q3':10000})
        self.assertEqual([t['count'] for t in chosen['tiers']], [6695,6613,2487])
        self.assertEqual([t['count'] for t in other['tiers']], [97213,74790,34008])
        self.assertAlmostEqual(chosen['tiers'][2]['percent'], 100*2487/15795)
        self.assertAlmostEqual(other['tiers'][2]['percent'], 100*34008/206011)
        for item in (chosen, other):
            self.assertEqual(sum(t['count'] for t in item['tiers']), item['n'])
            self.assertAlmostEqual(sum(t['percent'] for t in item['tiers']), 100)
            self.assertEqual(item['unknown_outcome_rows'], 0)
        self.assertEqual(comparison['chart']['type'], 'stacked_bar')
        self.assertEqual([r['cohort'] for r in comparison['chart']['rows']], ['selected', 'baseline'])
        self.assertIn('15,795', comparison['chart']['source'])
        self.assertIn('206,011', comparison['chart']['source'])
        self.assertEqual(len(result['charts']), 14)
        self.assertEqual([r['values'] for r in find_chart(result, 'group_volume_median')['rows']], [[1000],[1000]])
        self.assertEqual([r['filter']['tier'] for r in find_chart(result,'outcome_tiers')['rows']], [k for k,_ in TIERS['mobile']])
        json.dumps(result, allow_nan=False)

    def test_comparison_not_created_without_primary_group(self):
        result = self.market.query(analysis(group=''))
        self.assertIsNone(result['comparison'])
        with self.assertRaises(ValueError):
            self.market.records(records(analysis(group=''), cohort='baseline'))

    def test_year_filter_applies_to_both_cohorts_independent_source_join(self):
        query = analysis(year_from=2020, year_to=2020)
        comparison = self.market.query(query)['comparison']
        source = str(ROOT/'data/interim/cleaning_candidate_v1/mobile_candidates.parquet')
        features = str(ROOT/'data/processed/analysis_v1/mobile_features.parquet')
        labels = str(ROOT/'data/processed/analysis_v1/mobile_labels_splits.parquet')
        with duckdb.connect() as db:
            expected = db.execute('''SELECT f.category='Adventure' chosen, count(*),
                quantile_cont(c.minimum_installs,.25),median(c.minimum_installs),
                quantile_cont(c.minimum_installs,.75)
                FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id)
                JOIN read_parquet(?) c USING(app_id)
                WHERE l.split='train' AND year(c.release_date)=2020 GROUP BY chosen''',
                [features,labels,source]).fetchall()
        by_chosen = {r[0]:r[1:] for r in expected}
        for key, chosen in [('selected',True),('baseline',False)]:
            item = comparison[key]
            expected_n,q1,median,q3 = by_chosen[chosen]
            self.assertEqual(item['n'],expected_n)
            self.assertEqual(item['statistics']['volume_lower'], dict(n=expected_n,q1=q1,median=median,q3=q3))
            listing = self.market.records(records(query,cohort=key,sort='release_date'))
            self.assertEqual(listing['total'],expected_n)
            self.assertTrue(all(r['release_date'].startswith('2020-') for r in listing['rows']))

    def test_explicit_steam_groups_share_tag_year_and_disclose_overlap(self):
        query = analysis('pc', group='Action', compare_group='RPG', tag='Indie', year_from=2020,year_to=2020)
        comparison = self.market.query(query)['comparison']
        source = str(ROOT/'data/interim/cleaning_candidate_v1/pc_candidates.parquet')
        features = str(ROOT/'data/processed/analysis_v1/pc_features.parquet')
        labels = str(ROOT/'data/processed/analysis_v1/pc_labels_splits.parquet')
        with duckdb.connect() as db:
            expected = db.execute('''SELECT count(*) FILTER (WHERE list_contains(f.genres,'Action')),
                count(*) FILTER (WHERE list_contains(f.genres,'RPG')),
                count(*) FILTER (WHERE list_contains(f.genres,'Action') AND list_contains(f.genres,'RPG'))
                FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id)
                JOIN read_parquet(?) c USING(app_id)
                WHERE l.split='train' AND year(c.release_date)=2020 AND list_contains(f.genres,'Indie')''',
                [features,labels,source]).fetchone()
        self.assertEqual((comparison['selected']['n'],comparison['baseline']['n'],comparison['overlap_count']),expected)
        self.assertGreater(comparison['overlap_count'],0)
        self.assertTrue(any('相同遊戲' in note for note in comparison['notes']))
        for key in ('selected','baseline'):
            listing = self.market.records(records(query,cohort=key))
            self.assertEqual(listing['total'],comparison[key]['n'])
            self.assertTrue(all('Indie' in r['source_tags'] and r['release_date'].startswith('2020-') for r in listing['rows']))

    def test_empty_cohorts_keep_percent_and_statistics_missing(self):
        result = self.market.query(analysis(year_from=2035))
        self.assertTrue(result['empty'])
        comparison = result['comparison']
        for key in ('selected','baseline'):
            item = comparison[key]
            self.assertEqual(item['n'],0)
            self.assertEqual(item['statistics']['volume_lower'],dict(n=0,q1=None,median=None,q3=None))
            self.assertTrue(all(t['percent'] is None for t in item['tiers']))
        self.assertTrue(all(all(v is None for v in r['values']) for r in comparison['chart']['rows']))
        listing = self.market.records(records(analysis(year_from=2035),page=999999))
        self.assertEqual((listing['total'],listing['page'],listing['pages'],listing['rows']),(0,1,0,[]))
        json.dumps(result,allow_nan=False)

    def test_import_eligibility_zero_and_unclassified_complement(self):
        first=mobile(); first.update(app_id='fixture.adventure',category='Adventure',minimum_installs='0')
        second=mobile(); second.update(app_id='fixture.action',category='Action',minimum_installs='100000')
        excluded=mobile(); excluded.update(app_id='fixture.excluded',category='Adventure',minimum_installs='')
        ident=self.store.repository.save(raw([first,second,excluded]),metadata())['version_id']
        self.store.activate('mobile',ident)
        query=analysis(version_id=ident)
        result=self.market.query(query)
        self.assertEqual(result['comparison']['selected']['n'],1)
        self.assertEqual(result['comparison']['baseline']['n'],1)
        self.assertEqual(result['comparison']['selected']['statistics']['volume_lower']['median'],0)
        self.assertEqual(result['comparison']['selected']['unknown_outcome_rows'],0)
        self.assertEqual([r['app_id'] for r in self.market.records(records(query))['rows']],['fixture.adventure'])
        self.assertEqual(self.market.records(records(query,tier='unknown'))['total'],0)
        with self.assertRaises(ValueError): self.market.records(records(analysis()))
        self.store.activate('mobile',DEFAULT_VERSION)
        with self.assertRaises(ValueError): self.market.records(records(query))
        a=pc();a.update(app_id='101',genres='["Action"]')
        b=pc();b.update(app_id='102',genres='["Indie"]')
        ident=self.store.repository.save(raw([a,b],'pc'),metadata('pc'))['version_id']
        self.store.activate('pc',ident)
        query=analysis('pc',version_id=ident,group='Action')
        comparison=self.market.query(query)['comparison']
        self.assertEqual((comparison['selected']['n'],comparison['baseline']['n']), (1,1))
        baseline=self.market.records(records(query,cohort='baseline'))
        self.assertEqual(baseline['rows'][0]['groups'],[])
        self.assertIn('未對照玩法',comparison['baseline_definition'])

    def test_unknown_outcomes_count_in_denominator_and_drilldown(self):
        source=self.market._load('mobile')
        frame=source['frame'].iloc[:3].copy()
        frame['groups']=[['Adventure'],['Adventure'],['Action']]
        frame['target_tier']=[TIERS['mobile'][0][0],None,TIERS['mobile'][2][0]]
        frame['volume_lower']=[0,float('nan'),100000]
        frame['volume_upper']=frame.volume_lower
        synthetic=dict(source,frame=frame)
        comparison=compare(frame.iloc[:2],frame.iloc[2:],'mobile','Adventure','Action','test','test',TIERS['mobile'])
        self.assertEqual(comparison['selected']['known_outcome_rows'],1)
        self.assertEqual(comparison['selected']['unknown_outcome_rows'],1)
        self.assertEqual(comparison['selected']['tiers'][-1],dict(id='unknown',label='結果未知',count=1,percent=50))
        self.assertEqual(comparison['baseline']['tiers'][-1]['percent'],0)
        self.assertEqual(comparison['selected']['statistics']['volume_lower']['n'],1)
        with patch.object(self.market,'_load',return_value=synthetic):
            listing=self.market.records(records(analysis(compare_group='Action'),tier='unknown'))
        self.assertEqual(listing['total'],1)
        self.assertEqual(listing['rows'][0]['tier'],'unknown')
        self.assertIsNone(listing['rows'][0]['minimum_installs'])
        json.dumps(comparison,allow_nan=False)

    def test_records_drill_count_matches_tier_and_has_bounded_pages(self):
        listing=self.market.records(records(tier='M3_100k_plus',sort='volume'))
        self.assertEqual((listing['total'],listing['pages'],len(listing['rows'])),(2487,125,20))
        self.assertTrue(all(r['minimum_installs']>=100000 for r in listing['rows']))
        self.assertEqual(listing['context']['cohort_label'],'Adventure')
        last=self.market.records(records(tier='M3_100k_plus',page=999999))
        self.assertEqual((last['page'],len(last['rows'])),(125,7))
        other=self.market.records(records(cohort='baseline',tier='M3_100k_plus',page_size=50))
        self.assertEqual((other['total'],len(other['rows'])),(34008,50))
        self.assertTrue(all('Adventure' not in r['groups'] for r in other['rows']))
        train_ids={str(r[0]) for r in self.store.db.execute('SELECT app_id FROM mobile').fetchall()}
        self.assertTrue({r['app_id'] for r in listing['rows']} <= train_ids)

    def test_search_is_literal_case_insensitive_title_or_id_and_order_is_stable(self):
        first=mobile();first.update(app_id='fixture.unique-one',title='Equal Name',category='Adventure')
        second=mobile();second.update(app_id='fixture.unique-two',title='Equal Name',category='Adventure')
        third=mobile();third.update(app_id='fixture.symbols',title='Game .* literal',category='Adventure')
        ident=self.store.repository.save(raw([second,first,third]),metadata())['version_id']
        self.store.activate('mobile',ident)
        query=analysis(version_id=ident)
        found=self.market.records(records(query,q='FIXTURE.UNIQUE-ONE'))
        self.assertEqual([r['app_id'] for r in found['rows']],['fixture.unique-one'])
        found=self.market.records(records(query,q='eQuAl NaMe'))
        self.assertEqual([r['app_id'] for r in found['rows']],['fixture.unique-one','fixture.unique-two'])
        for sort in ('title','volume','release_date'):
            found=self.market.records(records(query,q='equal',sort=sort))
            self.assertEqual([r['app_id'] for r in found['rows']],['fixture.unique-one','fixture.unique-two'])
        self.assertEqual(self.market.records(records(query,q='.*'))['total'],1)
        self.assertEqual(self.market.records(records(query,q="' OR true --"))['total'],0)

    def test_revenue_comparison_and_records_keep_independent_scope(self):
        version=self.revenue.data['metadata']['version']
        query=analysis('revenue',version_id=version,group='Action',rank_metric='revenue')
        result=self.market.query(query)
        comparison=result['comparison']
        source=pd.DataFrame(self.revenue.data['rows'])
        chosen=source.genres.map(lambda xs:'Action' in xs)
        for key,frame in [('selected',source[chosen]),('baseline',source[~chosen])]:
            self.assertEqual(comparison[key]['n'],len(frame))
            self.assertEqual(comparison[key]['statistics']['revenue']['median'],frame.revenue.median())
            self.assertEqual(comparison[key]['tiers'],[])
            listing=self.market.records(records(query,cohort=key,sort='revenue'))
            self.assertEqual(listing['total'],len(frame))
            self.assertEqual(listing['rows'][0]['revenue'],frame.revenue.max())
        self.assertEqual(comparison['selected']['n']+comparison['baseline']['n'],1500)
        self.assertEqual(comparison['chart']['type'],'bar')
        self.assertEqual(comparison['chart']['unit'],'USD')
        self.assertEqual([r['cohort'] for r in comparison['chart']['rows']],['selected','baseline'])
        with self.assertRaises(ValueError):self.market.records(records(query,tier='M3_100k_plus'))

    def test_bad_record_and_analysis_parameters_are_rejected(self):
        changes=[dict(page=True),dict(page=0),dict(page=1_000_001),dict(page_size=500),dict(page_size=True),
                 dict(cohort='test'),dict(tier='bad'),dict(q=[]),dict(q='x'*201),dict(sort='title; DROP TABLE mobile'),
                 dict(analysis=[]),dict(extra=True)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):self.market.records(records(**change))
        changes=[dict(compare_group='Adventure'),dict(compare_group=['Action']),dict(group='',compare_group='Action'),
                 dict(compare_group='bad'),dict(version_id='old'),dict(year_from=True),dict(split='test')]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):self.market.records(records(analysis(**change)))


class ComparisonStatisticsTests(unittest.TestCase):
    def test_quartiles_exclude_missing_but_keep_zero(self):
        self.assertEqual(quartiles(pd.Series([None,0,10,20,100])),dict(n=4,q1=7.5,median=15,q3=40))
        self.assertEqual(quartiles(pd.Series([float('nan')])),dict(n=0,q1=None,median=None,q3=None))


if __name__=='__main__':
    unittest.main()
