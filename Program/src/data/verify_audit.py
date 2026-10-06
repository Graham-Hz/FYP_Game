"""Reconcile independent CSV/Arrow counts, report invariants and source preservation."""
import csv
import json
import pyarrow.compute as pc
import pyarrow.parquet as pq
from audit_common import *

def main():
    structure=json.loads((REPORTS/'structure_and_hashes.json').read_text())
    profiles={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (REPORTS/'profiles').glob('*.json')}
    verified=[]
    for item in sources():
        key=item['key'];profile=profiles[key]['table']
        if item['path'].suffix=='.csv':
            independent=structure[str(item['path'].relative_to(DATA))]['rows']
        else:
            independent=pq.ParquetFile(item['path']).metadata.num_rows
        assert profile['rows']==independent,(key,profile['rows'],independent)
        for col in profiles[key]['columns']:
            assert 0<=col['missing_count']<=independent,(key,col['column'])
            assert 0<=col['unique_nonmissing']<=independent-col['missing_count'],(key,col['column'])
            if col['invalid_count'] is not None:assert 0<=col['invalid_count']<=independent
        verified.append(key)
    hf=next(x for x in sources() if x['key']=='fronkon_hf')
    native=pq.read_table(hf['path'],columns=['tags'])
    assert pc.sum(pc.list_value_length(native['tags'])).as_py()==0
    assert profiles['google_games']['table']['rows']+profiles['google_sports_ambiguous']['table']['rows']==375996
    with (REPORTS/'google_categories.csv').open(encoding='utf-8-sig',newline='') as f:
        cats=list(csv.DictReader(f))
    assert sum(int(r['rows']) for r in cats)==profiles['google_all']['table']['rows']
    assert sum(int(r['rows']) for r in cats if r['included_as_game']=='True')==profiles['google_games']['table']['rows']
    with (REPORTS/'proposed_cohort_counts.csv').open(encoding='utf-8-sig',newline='') as f:
        previous={}
        for row in csv.DictReader(f):
            key=row['dataset'];remaining=int(row['remaining_rows']);removed=int(row['removed_at_step'])
            assert previous.get(key,remaining)-remaining==removed
            previous[key]=remaining
    with (REPORTS/'candidate_class_balance.csv').open(encoding='utf-8-sig',newline='') as f:
        totals={}
        for row in csv.DictReader(f):totals[row['dataset']]=totals.get(row['dataset'],0)+int(row['rows'])
    for key,total in totals.items():assert total==profiles[key]['table']['rows']
    preserved=[]
    for rel,entry in structure.items():
        p=DATA/rel
        assert p.stat().st_size==entry['bytes'],rel
        assert sha256(p)==entry['sha256'],rel
        preserved.append(rel)
    for name in ['dataset_inventory.csv','schema_comparison.csv','data_quality_summary.csv','target_feasibility.md','dataset_feasibility_report.md']:
        assert (REPORTS/name).stat().st_size>0,name
    result={'audit_date':DATE,'status':'passed','independent_count_checks':verified,'raw_files_rehashed_unchanged':preserved,'other_checks':['native Arrow empty tags','category count reconciliation','sequential cohort removals','class balance totals','profile count bounds','required deliverables present']}
    save_json(REPORTS/'verification.json',result)
    print('Verified',len(verified),'dataset profiles and',len(preserved),'unchanged raw files.',flush=True)

if __name__=='__main__':main()
