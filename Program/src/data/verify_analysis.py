"""Independently validate source membership, graph edges, partitions and feature policy."""
import ast
import hashlib
import json
import unicodedata

import pandas as pd

from audit_common import ROOT, INTERIM, connection, lit, save_json, sha256


def require(condition, message):
    if not condition: raise ValueError(message)


def main():
    config = json.loads((ROOT / "config/analysis_v1.json").read_text())
    policy = json.loads((ROOT / config["feature_policy_file"]).read_text())
    reports = ROOT / "reports" / config["date"] / config["version"]
    manifest_path = reports / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    verification_path = reports / "verification.json"
    verification_path.unlink(missing_ok=True)
    for section in ["inputs", "dependencies", "outputs"]:
        for path, digest in manifest[section].items():
            require(sha256(ROOT/path)==digest, f"Hash mismatch: {path}")
    out = ROOT / "data/processed" / config["version"]
    candidate_dir = INTERIM / config["input_cleaning_version"]
    edges = pd.read_parquet(out/"pc_developer_edges.parquet")
    source = pd.read_parquet(INTERIM/"artem_games_march2025_full.parquet",columns=["app_id","developers","price","estimated_owners","genres"])
    def normalize(value): return " ".join(unicodedata.normalize("NFKC",str(value)).split()).casefold()
    placeholders = set(config["developer_placeholder_tokens"])
    expected_edges = set()
    for row in source.itertuples():
        names = [] if pd.isna(row.developers) or not row.developers.strip() else ast.literal_eval(row.developers)
        expected_edges.update((row.app_id,normalize(name)) for name in names if normalize(name) not in placeholders)
    require(expected_edges == set(zip(edges.app_id,edges.developer_token)), "Full source developer edges differ")
    require(edges.groupby("developer_token").developer_group.nunique().max()==1,"Developer token spans components")
    require(edges.groupby("app_id").developer_group.nunique().max()==1,"Co-developers were separated")
    # Each component ID is a digest of its smallest normalized developer label.
    for group, name in edges.groupby("developer_group").developer_token.min().items():
        require(group == "pc_"+hashlib.sha256(name.encode()).hexdigest(),"Component identifier unstable")
    conn = connection()
    checks = []
    for platform in ["pc","mobile"]:
        split = pd.read_parquet(out/f"{platform}_labels_splits.parquet")
        features = pd.read_parquet(out/f"{platform}_features.parquet")
        ledger = pd.read_parquet(out/f"{platform}_cohort_ledger.parquet")
        candidates = pd.read_parquet(candidate_dir/f"{platform}_candidates.parquet")
        require(split.app_id.is_unique and features.app_id.is_unique and ledger.app_id.is_unique,"Duplicate IDs")
        require(split.app_id.tolist()==features.app_id.tolist(),"Feature/label row alignment differs")
        require(set(split.app_id)==set(ledger.loc[ledger.primary_eligible,"app_id"]),"Primary membership differs from ledger")
        require(split.target_tier.notna().all() and split.developer_group.notna().all(),"Missing target/group")
        common = split[split.app_id.isin(candidates.app_id)].merge(candidates[["app_id", "target_tier"]], on="app_id", suffixes=("_split", "_candidate"), validate="one_to_one")
        require(common.target_tier_split.equals(common.target_tier_candidate), "Frozen target differs from verified candidate")
        require(split.groupby("developer_group").split.nunique().max()==1,"Group crosses partitions")
        require(split[split.split.eq("train")].groupby("developer_group").cv_fold.nunique().max()==1,"Group crosses CV folds")
        require(split.loc[~split.split.eq("train"),"cv_fold"].isna().all(),"Held-out row assigned to training CV")
        require(set(features)-{"app_id"}==set(c for cols in policy[platform].values() for c in cols),"Feature artifact violates allowlist")
        require(not (set(features)-{"app_id"}).intersection(policy["forbidden_predictors"]),"Forbidden feature")
        require(features.age_days.ge(0).all(),"Invalid observation age")
        if platform=="pc":
            # Independently derive primary IDs from raw data + versioned base membership.
            base_ids=set(candidates.app_id)|set(config["pc_demo_exceptions"])
            require(set(ledger.app_id)==base_ids,"Base plus exception membership mismatch")
            known_ids=set(edges.app_id)
            cleaning=json.loads((ROOT/"config/cleaning_candidate_v1.json").read_text())
            software=set(cleaning["software_only_genres"])
            selected=set()
            for row in source.itertuples():
                genres=ast.literal_eval(row.genres) if pd.notna(row.genres) else []
                if row.app_id in base_ids and row.app_id in known_ids and row.estimated_owners!="0 - 0" and float(row.price)>0 and not (genres and set(genres)<=software):
                    selected.add(row.app_id)
            require(selected==set(split.app_id),"Independent source primary cohort mismatch")
            for app_id in config["pc_demo_exceptions"]:
                owner_text = source.set_index("app_id").loc[app_id,"estimated_owners"]
                require(owner_text == "0 - 20000", "Reviewed exception source target changed")
                require(split.set_index("app_id").loc[app_id,"target_tier"] == "O1_source_interval_up_to_20k", "Reviewed exception target mismatch")
            require(features.price_observed.gt(0).all(),"Nonpositive price in PC primary")
            actual_categories=set(x for xs in features.planning_categories for x in xs)
            require(actual_categories<=set(config["pc_planning_categories"]),"Unapproved Steam category")
            joined=split.merge(edges,on=["app_id","developer_group"],how="inner")
            require(set(joined.app_id)==set(split.app_id),"Missing graph membership")
            require(joined.groupby("developer_token").split.nunique().max()==1,"Shared developer leaks across partitions")
        else:
            require(set(split.app_id)==set(candidates.app_id),"Unexpected Mobile cohort exclusion")
            mobledger=pd.read_parquet(candidate_dir/"mobile_row_ledger.parquet").set_index("app_id")
            merged=features.merge(candidates,on="app_id",suffixes=("_feature","_source"),validate="one_to_one")
            conflict=merged.app_id.map(mobledger.flag_free_price_conflict)
            require(merged.loc[conflict,"free_feature"].isna().all(),"Free-price conflict not masked")
            require(merged.loc[~conflict,"free_feature"].reset_index(drop=True).equals(merged.loc[~conflict,"free_source"].reset_index(drop=True)),"Unrelated Free values changed")
            require(merged.price_usd_feature.equals(merged.price_usd_source),"USD values altered")
            normalized_by_id=candidates.set_index("app_id").developer_id.map(normalize)
            expected_group=split.app_id.map(normalized_by_id).map(lambda x:"mobile_"+hashlib.sha256(x.encode()).hexdigest())
            require(expected_group.equals(split.developer_group),"Mobile grouping differs from normalized source")
        conn.register("assignments",ledger)
        # Independently recompute deterministic assignments with SQL SHA256, not generator helpers.
        key=f"{config['seed']}|holdout|{platform}|"
        cvkey=f"{config['seed']}|cv|{platform}|"
        query=f"""WITH hashed AS (
          SELECT *, cast('0x'||substr(sha256({lit(key)}||developer_group),1,16) AS UBIGINT) / 18446744073709551616.0 AS u,
          cast('0x'||substr(sha256({lit(cvkey)}||developer_group),1,16) AS UBIGINT)%{config['train_cv_folds']} AS fold FROM assignments WHERE developer_group IS NOT NULL)
          SELECT count(*) FROM hashed WHERE assigned_split IS DISTINCT FROM
          CASE WHEN u<{config['train_threshold']} THEN 'train' WHEN u<{config['calibration_threshold']} THEN 'calibration' ELSE 'test' END
          OR assigned_cv_fold IS DISTINCT FROM CASE WHEN u<{config['train_threshold']} THEN fold END"""
        require(conn.execute(query).fetchone()[0]==0,"Independent SQL hash partition mismatch")
        all_labels=set(split.target_tier)
        require(len(all_labels)==3,"Expected three labels")
        for part in ["train","calibration","test"]:
            require(set(split.loc[split.split.eq(part),"target_tier"])==all_labels,"Partition missing a class")
        for fold in range(config["train_cv_folds"]):
            require(set(split.loc[split.split.eq("train") & split.cv_fold.eq(fold),"target_tier"])==all_labels,"CV fold missing a class")
        require(len(split)==manifest["summary"][platform]["primary_rows"],"Summary mismatch")
        checks.append({"platform":platform,"rows":len(split),"group_overlap":0,"fold_overlap":0,"independent_hash_assignment_mismatches":0})
    save_json(verification_path,{"status":"passed","manifest_sha256":sha256(manifest_path),"verifier_sha256":sha256(ROOT/"src/data/verify_analysis.py"),"checks":checks,
        "coverage":["all artifact/dependency hashes","complete source developer graph including excluded bridge games","independent primary ID derivation","group and training CV isolation","SQL hash partition recomputation","feature-target isolation","Mobile conflict masking and USD preservation","three classes in every partition and training fold"],"model_training":False})
    print(json.dumps({"status":"passed","checks":checks},indent=2))


if __name__=="__main__":main()
