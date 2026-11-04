"""Upload the tour site to S3-compatible storage (Selectel by default).

    python tour/upload.py <bucket> [--prefix tour/] [--delete] [--share]

Keys are read from ~/.aws/credentials, section [selectel] (--profile), never from the command line or the chat.
Needs boto3 (not in the project venv: pip install boto3 in a separate one). The page is sent with no-cache so a
re-upload shows at once; panoramas are cached for a day, and a new panorama gets a new file name anyway.
If Python rejects the endpoint's certificate, point AWS_CA_BUNDLE at the macOS roots (security find-certificate
-a -p /System/Library/Keychains/SystemRootCertificates.keychain > roots.pem).

--share also uploads share.html, the page with every file behind a presigned URL, and prints a link to it that
works for 7 days while the bucket itself stays private. Re-running keeps old share links working: they sign
the key share.html, not its content.
"""

import argparse
import mimetypes
from pathlib import Path

import boto3
from botocore.config import Config

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("bucket")
ap.add_argument("--dir", default="renders/tour_site", help="site folder (default: renders/tour_site)")
ap.add_argument("--prefix", default="", help="folder inside the bucket, e.g. tour/")
ap.add_argument("--profile", default="selectel")
ap.add_argument("--endpoint", default="https://s3.ru-1.storage.selcloud.ru")
ap.add_argument("--region", default="ru-1")
ap.add_argument("--delete", action="store_true", help="remove objects under the prefix that the site no longer has")
ap.add_argument("--share", action="store_true", help="also upload share.html and print a 7-day link to it")
ap.add_argument("--only", nargs="+", help="upload just these files (e.g. index.html after a page fix); share.html still "
                                         "links every file of the site")
ap.add_argument("--changed", action="store_true", help="upload only files changed since the last upload of this folder "
                                                      "(the folder's .uploaded stamp)")
args = ap.parse_args()

s3 = boto3.Session(profile_name=args.profile).client(
    "s3", endpoint_url=args.endpoint, region_name=args.region,
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
stamp = Path(args.dir) / ".uploaded"
since = stamp.stat().st_mtime if args.changed and stamp.exists() else 0.0
sent = set()
for f in sorted(Path(args.dir).iterdir()):
    if not f.is_file() or f.name.startswith("."):
        continue
    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    if ctype.startswith("text/"):
        ctype += "; charset=utf-8"
    key = args.prefix + f.name
    sent.add(key)
    if (args.only and f.name not in args.only) or f.stat().st_mtime < since:
        continue
    s3.upload_file(str(f), args.bucket, key, ExtraArgs={
        "ContentType": ctype, "CacheControl": "no-cache" if f.suffix == ".html" else "max-age=86400"})
    print(f"uploaded {key} ({ctype}, {f.stat().st_size // 1024} KB)")

if args.share:
    week = 7 * 24 * 3600
    sign = lambda key: s3.generate_presigned_url("get_object", Params={"Bucket": args.bucket, "Key": key}, ExpiresIn=week)
    page = (Path(args.dir) / "index.html").read_text()
    for key in sorted(sent):
        page = page.replace(f'"{key.removeprefix(args.prefix)}"', f'"{sign(key)}"')
    key = args.prefix + "share.html"
    s3.put_object(Bucket=args.bucket, Key=key, Body=page.encode(), ContentType="text/html; charset=utf-8",
                  CacheControl="no-cache")
    sent.add(key)
    print(f"share link, valid 7 days:\n{sign(key)}")

if not args.only:
    stamp.touch()  # the next --changed upload sends only what changed after this one

pages = s3.get_paginator("list_objects_v2").paginate(Bucket=args.bucket, Prefix=args.prefix)
stale = sorted({o["Key"] for page in pages for o in page.get("Contents", [])} - sent)
for key in stale:
    if args.delete:
        s3.delete_object(Bucket=args.bucket, Key=key)
    print(("deleted " if args.delete else "left in the bucket (not in the site; --delete removes it): ") + key)
