"""Export reproducible local evidence for design decisions without altering snapshots."""
import json

import pandas as pd

from audit_common import ROOT, INTERIM, save_csv, save_json, sha256
from group_splits import normalize_developer


def main():
    out=ROOT/"reports/2026-10-06/analysis_v1"
    paths=[INTERIM/"artem_games_march2025_full.parquet",INTERIM/"cleaning_candidate_v1/pc_row_ledger.parquet",INTERIM/"cleaning_candidate_v1/mobile_candidates.parquet",INTERIM/"cleaning_candidate_v1/mobile_row_ledger.parquet"]
    pc=pd.read_parquet(paths[0],columns=["app_id","name","genres","developers","short_description","price","estimated_owners"])
    ledger=pd.read_parquet(paths[1])
    reviewed=ledger.exclude_demo_playtest_title_heuristic & ~ledger.exclude_genres_unavailable & ~ledger.exclude_title_missing
    evidence=pc[pc.app_id.isin(ledger.loc[reviewed,"app_id"])].copy()
    # A pointer and summary suffice; do not duplicate full descriptions in research reports.
    evidence=evidence[["app_id","name","genres","price"]].sort_values("app_id")
    evidence["decision"]="retain_trial_title_exclusion_scope_heuristic"
    evidence.loc[evidence.app_id.eq("1129080"),"decision"]="explicit_exception_based_on_local_description"
    save_csv(out/"demo_title_review.csv",evidence.to_dict("records"))
    mobile=pd.read_parquet(paths[2])
    mobile["normalized_developer"]=mobile.developer_id.map(normalize_developer)
    names=mobile[["developer_id","normalized_developer"]].drop_duplicates()
    collisions=names.groupby("normalized_developer").filter(lambda df:len(df)>1).sort_values(["normalized_developer","developer_id"])
    save_csv(out/"mobile_developer_normalization_review.csv",collisions.to_dict("records"))
    ml=pd.read_parquet(paths[3]).set_index("app_id")
    conflict=mobile[mobile.app_id.map(ml.flag_free_price_conflict)]
    checks={"source_sha256":{p.relative_to(ROOT).as_posix():sha256(p) for p in paths},
        "demo_rule_survivors_after_other_base_rules":len(evidence),"explicit_demo_exceptions":int(evidence.app_id.eq("1129080").sum()),
        "mobile_original_developer_labels":int(names.developer_id.nunique()),"mobile_normalized_developer_labels":int(names.normalized_developer.nunique()),
        "mobile_normalization_collision_groups":int(collisions.normalized_developer.nunique()),
        "mobile_conflict_rows":len(conflict),"mobile_conflict_missing_currency":int(conflict.currency.isna().sum()),
        "interpretation":"Normalization variants are reviewable strings, not proof of company identity. Current Steam API responses never replace historical fields."}
    save_json(out/"data_question_diagnostics.json",checks)
    matrix=json.loads((out/"literature_matrix.json").read_text(encoding="utf-8"))
    save_csv(out/"literature_matrix.csv",matrix["papers"])
    print(json.dumps(checks,indent=2))


if __name__=="__main__":main()
