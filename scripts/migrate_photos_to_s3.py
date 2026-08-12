"""Copy every photograph off the previous vendor's CDN into the school's own S3.

    python scripts/migrate_photos_to_s3.py            # report only
    python scripts/migrate_photos_to_s3.py --apply

Why: anomaly D2. Every photo currently lives on cdn.vedmarg.com - the school's PREVIOUS
software vendor - and opens with no authentication. Two risks: if that CDN is switched
off every photo on EduFlow breaks at once, and 1,427 children's photographs are publicly
readable by anyone holding the link.

THIS SCRIPT SOLVES THE FIRST RISK ONLY, and deliberately says so. It takes our own copy
of every image into `{school_id}/uploads/...` and records the key on the student/staff
record as `photo_s3_key`. It does NOT repoint `photo_url`, because serving through the
app needs a `file_uploads` record per image (see routes/upload.py serve_file) - that is
a second, small step. Until it is done the photos are still SERVED from the public CDN.

Never deletes. Never overwrites an existing photo_s3_key. Skips anything already copied,
so it is safe to re-run after an interruption - the same property that saved the student
load when it timed out.
"""
from __future__ import annotations
import argparse, datetime, hashlib, os, sys
from pathlib import Path
import boto3, certifi, requests
from dotenv import load_dotenv
from pymongo import MongoClient

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / "backend" / ".env")
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BUCKET = "eduflow-files-ap-south-1-210447603820"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== {'APPLY' if args.apply else 'DRY RUN'} ===")
    mc = MongoClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(), serverSelectionTimeoutMS=30000)
    db = mc[os.environ["DB_NAME"]]
    s3 = boto3.client("s3", region_name="ap-south-1",
                      aws_access_key_id=os.environ["AWS_KEY"], aws_secret_access_key=os.environ["AWS_SEC"])
    jobs = []
    for coll, fields in (("students", ("photo_url", "mother_photo", "father_photo", "guardian_photo")),
                         ("staff", ("photo_url",))):
        for d in db[coll].find({"schoolId": SCHOOL_ID}, {"_id": 0}):
            for f in fields:
                u = d.get(f)
                if not u or not str(u).startswith("http"): continue
                if d.get(f"{f}_s3_key"): continue
                jobs.append((coll, d["id"], f, u))
    print(f"images to copy: {len(jobs)}")
    if not args.apply:
        print("--- DRY RUN, nothing copied ---"); return
    ok = fail = 0
    for n, (coll, did, f, url) in enumerate(jobs, 1):
        try:
            r = requests.get(url, timeout=45)
            if r.status_code != 200 or not r.content:
                fail += 1; continue
            ext = ".jpg" if "jpeg" in r.headers.get("content-type", "") or url.lower().endswith((".jpg", ".jpeg")) else ".png"
            key = f"{SCHOOL_ID}/uploads/{hashlib.sha256(url.encode()).hexdigest()[:24]}/{f}{ext}"
            s3.put_object(Bucket=BUCKET, Key=key, Body=r.content,
                          ContentType=r.headers.get("content-type", "image/jpeg"))
            db[coll].update_one({"id": did, "schoolId": SCHOOL_ID},
                                {"$set": {f"{f}_s3_key": key, f"{f}_s3_bytes": len(r.content)}})
            ok += 1
        except Exception:
            fail += 1
        if n % 200 == 0: print(f"  {n}/{len(jobs)}  copied={ok} failed={fail}", flush=True)
    print(f"DONE copied={ok} failed={fail}")
    db.audit_logs.insert_one({"id": os.urandom(8).hex(), "schoolId": SCHOOL_ID, "branch_id": "branch-joya",
        "action": "bulk_import", "collection": "students", "entity_id": "photo-s3-migration-2026-08-06",
        "changed_by": "layaa-ai-data-load", "changed_by_role": "system",
        "changes": {"copied": ok, "failed": fail, "bucket": BUCKET},
        "created_at": datetime.datetime.now().isoformat()})
    mc.close()

if __name__ == "__main__":
    main()
