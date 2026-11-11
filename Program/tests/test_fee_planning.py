"""Hand-calculated term/FX examples, source integrity and HTTP fee integration."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/demo'))
from fees import FeeStore
from planning import budget
from server import make_server
from test_development_planning import example


def item(fee_id, quantity=1, fx=1, currency='USD', assumption=None):
    return {'fee_id':fee_id,'quantity':quantity,'fx_rate':fx,'target_currency':currency,
            'eligibility_confirmed':True,'billing_assumption':assumption}


def empty_plan(store, *items, months=12, currency='USD'):
    p=example()
    p.update(currency=currency,months=months,team=[dict(label='Solo',people=1,allocation=1,monthly_cash=0,monthly_unpaid=0)])
    for key in ('monthly_overhead','outsourcing','marketing','other_one_off','contingency_percent'):
        p[key]=0
    p['fee_selection']={'revision':store.metadata['revision'],'items':list(items)}
    return p


class FeeBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.store=FeeStore(ROOT)

    def test_short_project_keeps_entire_monthly_paid_annual_obligation(self):
        # Two seats x USD 210 x 12 committed months, even for a six-month plan.
        p=empty_plan(self.store,item('F003',2),months=6)
        p['contingency_percent']=10
        r=budget(p,self.store)
        self.assertEqual([s['cash_budget'] for s in r['delays']],[5544]*3)
        self.assertEqual(r['base']['fee_lines'][0]['covered_months'],12)
        self.assertEqual(r['base']['fee_lines'][0]['price_units'],12)
        p['months']=13
        self.assertEqual(budget(p,self.store)['base']['cash_budget'],11088)

    def test_yearly_prepaid_renewal_and_fx_are_recomputed_on_delay(self):
        p=example()
        p['fee_selection']={'revision':self.store.metadata['revision'],'items':[item('F002',2,7.8,'HKD')]}
        r=budget(p,self.store)
        # Manual base 160,000 + 2*2,310*7.8 = 196,036; add 10% reserve.
        self.assertEqual(r['base']['components']['reference_fees'],36036)
        self.assertEqual(r['base']['cash_budget'],215639.6)
        self.assertEqual(r['delays'][1]['cash_budget'],288279.2)
        self.assertEqual(r['delays'][1]['fee_lines'][0]['price_units'],2)
        self.assertAlmostEqual(r['base']['runway_months'],10.44)
        self.assertEqual(r['base']['runway_status'],'reference_fees_reserved_upfront')
        p['available_funds']=1000000
        self.assertEqual(budget(p,self.store)['base']['runway_months'],12)

    def test_accounts_apps_equipment_and_free_plan_remain_separate(self):
        p=empty_plan(self.store,item('F021',2,7.8,'HKD'),item('F022',1,7.8,'HKD'),
                     item('F025',1,1,'HKD'),item('F009',1,1,'HKD'),currency='HKD')
        r=budget(p,self.store)
        # Two Steam apps + one Play account + one monitor. No yearly recurrence.
        self.assertEqual([s['cash_budget'] for s in r['delays']],[3053]*3)
        self.assertEqual(r['base']['fee_lines'][-1]['cost'],0)
        self.assertEqual(r['base']['runway_status'],'no_monthly_cash_outflow')

    def test_unspecified_monthly_billing_requires_explicit_user_assumption(self):
        p=empty_plan(self.store,item('F019',3),months=5)
        with self.assertRaisesRegex(ValueError,'逐月'):budget(p,self.store)
        p['fee_selection']['items'][0]['billing_assumption']='monthly_flexible_user_assumption'
        r=budget(p,self.store)
        self.assertEqual([s['cash_budget'] for s in r['delays']],[60,96,132])
        self.assertEqual(r['fee_reference']['selections'][0]['reference']['billing_schedule'],'not_stated')

    def test_round_each_line_once_and_keep_export_evidence(self):
        p=empty_plan(self.store,item('F011',1,7.8123,'HKD'),currency='HKD')
        r=budget(p,self.store)
        self.assertEqual(r['base']['cash_budget'],156.17)
        self.assertEqual(r['base']['fee_lines'][0]['source_total'],19.99)
        self.assertEqual(r['fee_reference']['sources'][0]['url'],'https://www.aseprite.org/faq')
        self.assertEqual(r['fee_reference']['selections'][0]['reference']['accessed_on'],'2026-11-09')
        self.assertEqual(r['fee_reference']['metadata']['sha256'],self.store.metadata['sha256'])
        self.assertEqual(r['data_kind'],'user_assumptions_with_selected_fee_references')
        json.dumps(r,allow_nan=False)

    def test_reject_ineligible_rates_missing_confirmation_bad_fx_and_tampering(self):
        for fee_id in ['F004','F005','F006','F007','F008','F023','not_real']:
            with self.subTest(fee_id=fee_id),self.assertRaises(ValueError):budget(empty_plan(self.store,item(fee_id)),self.store)
        for key,value in [('quantity',True),('quantity',0),('quantity',1.5),('quantity',1001),
                          ('fx_rate',None),('fx_rate',0),('fx_rate',float('nan')),('fx_rate',float('inf')),
                          ('fx_rate',2),('target_currency','HKD'),('eligibility_confirmed',False),
                          ('eligibility_confirmed','true'),('amount',1),('fee_id',[])]:
            changed=item('F002');changed[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):budget(empty_plan(self.store,changed),self.store)
        for selections in [(item('F002'),item('F003')),(item('F002'),item('F002'))]:
            with self.assertRaisesRegex(ValueError,'同一工具'):budget(empty_plan(self.store,*selections),self.store)
        p=empty_plan(self.store,item('F021'));p['fee_selection']['revision']='stale'
        with self.assertRaisesRegex(ValueError,'版本'):budget(p,self.store)
        with self.assertRaises(ValueError):budget(empty_plan(self.store),self.store)

    def test_missing_catalogue_preserves_manual_budget_but_not_selected_prices(self):
        self.assertEqual(budget(example())['base']['cash_budget'],176000)
        with self.assertRaisesRegex(ValueError,'手動預算'):budget(empty_plan(self.store,item('F021')))


class FeeSourceTests(unittest.TestCase):
    def test_saved_observations_and_availability(self):
        data=FeeStore(ROOT).data
        self.assertEqual(data['metadata']['fee_count'],26)
        self.assertEqual(data['metadata']['source_count'],16)
        fees={r['fee_id']:r for r in data['fees']}
        self.assertIsNone(fees['F023']['amount'])
        self.assertIsNone(fees['F005']['calculation_mode'])
        self.assertIsNone(fees['F007']['calculation_mode'])
        self.assertEqual(fees['F003']['calculation_mode'],'committed_monthly')
        self.assertEqual(fees['F019']['calculation_mode'],'monthly_assumption_required')
        self.assertEqual(fees['F010']['sources'][0]['evidence_method'],'official_search_extract')

    def test_reject_invalid_csv_prices_and_broken_sources(self):
        origin=ROOT.parent/'Dataset/Development Fee References'
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            for name in ['fees','sources']:shutil.copyfile(origin/f'{name}.csv',folder/f'{name}.csv')
            with (folder/'fees.csv').open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            changes=[(0,'fee_id','F002'),(0,'amount','5'),(1,'amount','NaN'),(1,'amount',''),
                     (1,'source_ids','missing'),(1,'primary_source_url','https://example.com'),
                     (4,'amount','0'),(4,'rate_fraction',''),(4,'rate_fraction','1'),
                     (1,'commitment_months','0'),(24,'configuration',''),(1,'accessed_on','2026-11-10')]
            for index,key,value in changes:
                changed=copy.deepcopy(rows);changed[index][key]=value
                with (folder/'fees.csv').open('w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(changed)
                with self.subTest(index=index,key=key),self.assertRaises(ValueError):FeeStore(directory=folder)


class FeeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(SimpleNamespace(root=ROOT),0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.store=FeeStore(ROOT)

    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_catalogue_exact_source_csv_and_static_script(self):
        with urlopen(self.url+'/api/planning/fees') as r:self.assertEqual(json.load(r)['metadata']['revision'],self.store.metadata['revision'])
        for name in ['fees','sources']:
            with urlopen(self.url+'/api/planning/fees/csv/'+name) as r:self.assertEqual(r.read(),self.store.raw[name])
        with urlopen(self.url+'/fees.js') as r:self.assertEqual(r.status,200)
        with self.assertRaises(HTTPError) as caught:urlopen(self.url+'/api/planning/fees/csv/unknown')
        self.assertEqual(caught.exception.code,404);caught.exception.close()

    def test_source_linked_budget_and_stale_selection_response(self):
        p=empty_plan(self.store,item('F021'))
        request=lambda data:Request(self.url+'/api/planning/budget',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urlopen(request(p)) as r:self.assertEqual(json.load(r)['base']['cash_budget'],100)
        p['fee_selection']['revision']='old'
        with self.assertRaises(HTTPError) as caught:urlopen(request(p))
        self.assertEqual(caught.exception.code,400);caught.exception.close()


if __name__=='__main__':unittest.main()
