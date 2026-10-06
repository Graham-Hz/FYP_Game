"""Capture public provenance and download only a pinned core Steam snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
REPOS = ["FronkonGames/steam-games-dataset", "atalaydenknalbant/video-games-dataset", "adde023/steam-reviews"]
KAGGLE = ["fronkongames/steam-games-dataset", "artermiloff/steam-games-dataset", "gauthamp10/google-playstore-apps", "nikdavis/steam-store-games", "antonkozyriev/game-recommendations-on-steam"]

def get(url):
    r = requests.get(url, timeout=(20, 90))
    r.raise_for_status()
    return r

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Audit date in the user's timezone")
    parser.add_argument("--download-steam", action="store_true")
    args = parser.parse_args()
    out = ROOT / "data/raw/source_metadata" / args.date
    out.mkdir(parents=True, exist_ok=True)
    lock_path = out / "sources_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {"audit_date": args.date, "hf": {}, "kaggle": {}}
    for repo in REPOS:
        slug = repo.replace("/", "__")
        if repo not in lock["hf"] or not (out / f"hf_{slug}.json").exists():
            suffix = "/revision/" + lock["hf"][repo]["revision"] if repo in lock["hf"] else ""
            meta = get("https://huggingface.co/api/datasets/" + repo + suffix).json()
            sha = meta["sha"]
            tree = get(f"https://huggingface.co/api/datasets/{repo}/tree/{sha}?recursive=true&limit=1000").json()
            (out / f"hf_{slug}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            (out / f"{slug}_tree.json").write_text(json.dumps(tree, indent=2), encoding="utf-8")
            card = get(f"https://huggingface.co/datasets/{repo}/raw/{sha}/README.md").text
            (out / f"{slug}_README.md").write_text(card, encoding="utf-8")
            lock["hf"][repo] = {**lock["hf"].get(repo, {}), "revision": sha, "last_modified": meta.get("lastModified"), "downloads_last_month": meta.get("downloads"), "license": (meta.get("cardData") or {}).get("license"), "files": [{k:x.get(k) for k in ("path","size","lfs")} for x in tree if x.get("type")=="file"]}
            lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        info = lock["hf"][repo]
        print(repo, info["revision"], "downloads(last month)", info["downloads_last_month"], "bytes", sum(x.get("size") or 0 for x in info["files"]), flush=True)
    for repo in KAGGLE:
        if repo in lock["kaggle"] and (out / ("kaggle_" + repo.replace("/", "__") + ".json")).exists():
            continue
        url = "https://www.kaggle.com/api/v1/datasets/view/" + repo
        try:
            response = get(url)
            meta = response.json()
            (out / ("kaggle_" + repo.replace("/", "__") + ".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
            lock["kaggle"][repo] = {"metadata_url": url, "status": "retrieved", "title": meta.get("title"), "lastUpdated": meta.get("lastUpdated"), "downloadCount": meta.get("downloadCount"), "licenseName": meta.get("licenseName"), "currentVersionNumber": meta.get("currentVersionNumber")}
        except Exception as exc:
            lock["kaggle"][repo] = {"metadata_url": url, "status": "unavailable", "error": str(exc)}
        print(repo, lock["kaggle"][repo], flush=True)
        lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    if args.download_steam:
        repo = REPOS[0]
        info = lock["hf"][repo]
        file = next(x for x in info["files"] if x["path"] == "data/train-00000-of-00001.parquet")
        target = ROOT / "data/raw/huggingface" / info["revision"] / "steam.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = (file.get("lfs") or {}).get("oid")
        if not target.exists():
            url = f"https://huggingface.co/datasets/{repo}/resolve/{info['revision']}/{file['path']}"
            with requests.get(url, stream=True, timeout=(20, 120)) as r:
                r.raise_for_status()
                with target.with_suffix(".part").open("wb") as f:
                    for chunk in r.iter_content(4*1024*1024):
                        f.write(chunk)
            target.with_suffix(".part").replace(target)
        with target.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if expected and digest != expected:
            raise ValueError("Downloaded Steam file hash does not match source LFS object")
        if target.stat().st_size != file["size"]:
            raise ValueError("Downloaded Steam file size mismatch")
        info["download"] = {"path": str(target.relative_to(ROOT)), "sha256": digest, "bytes": target.stat().st_size, "retrieved_date": args.date, "lfs_hash_verified": bool(expected)}
        lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        print("Verified", target, target.stat().st_size, digest, flush=True)

if __name__ == "__main__":
    main()
