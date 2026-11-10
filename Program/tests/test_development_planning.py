"""Independent budget examples, provenance safeguards and HTTP behaviour."""
import copy
import csv
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from planning import PlanningStore, budget
from server import make_server


def example():
    return {'currency': 'HKD', 'months': 12,
            'team': [{'label': 'Founder', 'people': 1, 'allocation': 1, 'monthly_cash': 0, 'monthly_unpaid': 12000},
                     {'label': 'Part-time developer', 'people': 1, 'allocation': 0.5, 'monthly_cash': 16000, 'monthly_unpaid': 0}],
            'monthly_overhead': 2000, 'outsourcing': 20000, 'marketing': 15000,
            'other_one_off': 5000, 'contingency_percent': 10,
            'available_funds': 200000, 'net_unit_contribution': 40}


class BudgetTests(unittest.TestCase):
    def test_hand_calculated_cash_and_unpaid_labour_stay_separate(self):
        result = budget(example())
        base = result['base']
        self.assertEqual(result['monthly_cash_outflow'], 10000)
        self.assertEqual(base['cash_before_reserve'], 160000)
        self.assertEqual(base['components']['contingency'], 16000)
        self.assertEqual(base['cash_budget'], 176000)
        self.assertEqual(base['unpaid_labour_value'], 144000)
        self.assertEqual(base['resource_budget'], 320000)
        self.assertEqual(base['funding_balance'], 24000)
        self.assertEqual(base['runway_months'], 14.4)
        self.assertEqual(base['cash_break_even_units'], 4400)
        self.assertEqual(base['resource_break_even_units'], 8000)
        self.assertEqual(result['data_kind'], 'user_assumptions')

    def test_delay_increases_recurring_costs_without_repeating_one_off(self):
        delays = budget(example())['delays']
        self.assertEqual([r['cash_budget'] for r in delays], [176000, 209000, 242000])
        self.assertEqual([r['components']['outsourcing'] for r in delays], [20000]*3)
        self.assertEqual(delays[1]['funding_balance'], -9000)

    def test_missing_optional_is_not_zero_and_zero_contribution_has_no_units(self):
        p = example(); p.update(available_funds=None, net_unit_contribution=None)
        result = budget(p)
        self.assertIsNone(result['base']['funding_balance'])
        self.assertIsNone(result['base']['runway_months'])
        self.assertIsNone(result['base']['cash_break_even_units'])
        p.update(available_funds=0, net_unit_contribution=0)
        result = budget(p)
        self.assertEqual(result['base']['funding_balance'], -176000)
        self.assertEqual(result['base']['runway_status'], 'insufficient_upfront_funds')
        self.assertIsNone(result['base']['cash_break_even_units'])

    def test_zero_cash_with_unpaid_work_is_not_zero_resource(self):
        p = example()
        p['team'] = p['team'][:1]
        for key in ['monthly_overhead','outsourcing','marketing','other_one_off','contingency_percent']:
            p[key] = 0
        result = budget(p)['base']
        self.assertEqual(result['cash_budget'], 0)
        self.assertEqual(result['resource_budget'], 144000)
        self.assertEqual(result['runway_status'], 'no_monthly_cash_outflow')
        self.assertIsNone(result['runway_months'])

    def test_sales_requirement_rounds_up_and_currency_does_not_convert(self):
        p = example(); p['net_unit_contribution'] = 39
        self.assertEqual(budget(p)['base']['cash_break_even_units'], 4513)
        p['currency'] = 'USD'
        self.assertEqual(budget(p)['base']['cash_budget'], 176000)

    def test_reject_missing_nonfinite_negative_and_invalid_inputs(self):
        for key, value in [('months',0),('months',1.5),('monthly_overhead',None),
                           ('marketing',-1),('outsourcing',float('nan')),('outsourcing',float('inf')),
                           ('contingency_percent',101),('available_funds',''),('months',True),
                           ('currency',[]),('net_unit_contribution',0.001),('team',[])]:
            p=example(); p[key]=value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError): budget(p)
        for key,value in [('allocation',1.1),('people',0),('people',1.2),('label',''),('monthly_cash',False)]:
            p=example(); p['team'][0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): budget(p)


class CaseTests(unittest.TestCase):
    def test_pilot_preserves_scopes_and_uncertainty(self):
        result=PlanningStore(ROOT).data
        self.assertEqual(result['metadata']['case_count'],10)
        self.assertEqual(result['metadata']['observation_count'],37)
        cases={r['case_id']:r for r in result['cases']}
        self.assertFalse(any(r['unit']=='money' for r in cases['hang_line']['observations']))
        self.assertEqual(cases['fomography']['observations'][0]['metric'],'reported_budget')
        self.assertEqual(cases['monsters_memories']['observations'][0]['qualifier'],'less_than')
        self.assertEqual({r['value'] for r in cases['fall_of_lazarus']['observations']},{65075,166717,162972,20})
        self.assertTrue(all(r['locator'] and r['source']['url'] for c in cases.values() for r in c['observations']))

    def test_bad_source_reference_and_currency_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            origin=ROOT.parent/'Dataset/Development Cost Cases'
            for path in origin.glob('*.csv'): shutil.copyfile(path,directory/path.name)
            path=directory/'observations.csv'
            with path.open(encoding='utf-8',newline='') as f:
                reader=csv.DictReader(f); headers=reader.fieldnames; rows=list(reader)
            for key,value in [('case_id','unknown'),('currency_basis','unspecified'),('value',''),('value','NaN'),('locator','')]:
                changed=copy.deepcopy(rows); changed[0][key]=value
                with path.open('w',encoding='utf-8',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(changed)
                with self.subTest(key=key,value=value),self.assertRaises(ValueError): PlanningStore(directory=directory)


class PlanningHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(SimpleNamespace(root=ROOT),0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_cases_and_downloads_serve_checked_csv(self):
        with urlopen(self.url+'/api/planning/cases') as r: self.assertEqual(json.load(r)['metadata']['case_count'],10)
        for name in ['cases','observations','sources']:
            with urlopen(self.url+'/api/planning/csv/'+name) as r:
                self.assertEqual(r.read(),(ROOT.parent/'Dataset/Development Cost Cases'/f'{name}.csv').read_bytes())
        for path in ['/planning','/planning.js','/planning.css']:
            with urlopen(self.url+path) as r:self.assertEqual(r.status,200)

    def test_budget_and_bad_request_status(self):
        req=Request(self.url+'/api/planning/budget',data=json.dumps(example()).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:self.assertEqual(json.load(r)['base']['cash_budget'],176000)
        for p in [{}, {'currency':[]}]:
            req=Request(self.url+'/api/planning/budget',data=json.dumps(p).encode(),headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as caught: urlopen(req)
            self.assertEqual(caught.exception.code,400);caught.exception.close()
        req=Request(self.url+'/api/planning/budget',data=json.dumps(example()).encode(),headers={'Origin':'https://example.com'})
        with self.assertRaises(HTTPError) as caught:urlopen(req)
        self.assertEqual(caught.exception.code,403);caught.exception.close()


if __name__=='__main__':unittest.main()
