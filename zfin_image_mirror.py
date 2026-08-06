#!/usr/bin/env python3
"""ZFIN Image Mirror → S3.

Downloads the Thisse in-situ hybridization images referenced by
``image_metadata.json`` from ZFIN and uploads them to our own S3 bucket, so the
application can serve them from our cloud (via the backend ``/api/image-proxy``
endpoint) instead of hotlinking ZFIN live. This protects the UI from temporary
ZFIN outages (GEN-22).

For every image it mirrors:
  - the plain      ``{image_id}.jpg``        (present for every image)
  - the annotated  ``{image_id}_annot.jpg``  (present only for some
    publications; 404s are recorded as "missing" and skipped, not errors)

The S3 layout mirrors the ZFIN path 1:1 so the backend can map a canonical ZFIN
image URL to an object key with a simple prefix swap::

    https://zfin.org/imageLoadUp/{year}/{pub_id}/{file}
        → s3://{bucket}/{prefix}/imageLoadUp/{year}/{pub_id}/{file}

The run is resumable: objects already present under the prefix are listed once
up front and skipped, so re-running only fetches what is missing.

Credentials are read from the standard AWS chain (env vars, shared config, or an
instance/role profile). Never hard-code keys here.

Usage::

    export GENE2IMAGE_DATA_DIR=/path/to/gene2image_data   # holds image_metadata*.json
    export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-west-2
    python zfin_image_mirror.py                            # mirror everything
    python zfin_image_mirror.py --limit 50 --dry-run       # smoke test, no uploads
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_BUCKET = "czbsf-rnaquarium"
DEFAULT_PREFIX = "gene2fish/zfin-images"
DEFAULT_REGION = "us-west-2"
USER_AGENT = "gene2fish image mirror (GEN-22)"

ZFIN_HOST_PREFIX = "https://zfin.org/imageLoadUp/"


def build_image_urls(pub_id: str, image_id: str) -> tuple[str, str, str]:
    """Return (annotated_url, plain_url, medium_url) — mirrors backend ``_build_image_url``."""
    try:
        year = "20" + pub_id.split("-")[2][:2]
    except (IndexError, AttributeError):
        year = "2000"
    base = f"{ZFIN_HOST_PREFIX}{year}/{pub_id}/{image_id}"
    return f"{base}_annot.jpg", f"{base}.jpg", f"{base}_medium.jpg"


def url_to_key(url: str, prefix: str) -> str:
    """Map a ZFIN imageLoadUp URL to its S3 object key under ``prefix``."""
    rel = url[len(ZFIN_HOST_PREFIX):]  # imageLoadUp/{year}/{pub}/{file}
    return f"{prefix.rstrip('/')}/imageLoadUp/{rel}"


def load_metadata(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"\bNaN\b", "null", raw)  # pandas exports bare NaN
    return json.loads(raw)


def find_metadata_file(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    data_dir = os.environ.get("GENE2IMAGE_DATA_DIR")
    if not data_dir:
        sys.exit(
            "No metadata file given. Pass --metadata PATH or set GENE2IMAGE_DATA_DIR."
        )
    for name in ("image_metadata_v2.json", "image_metadata.json"):
        candidate = Path(data_dir) / name
        if candidate.exists():
            return candidate
    sys.exit(f"No image_metadata*.json found in {data_dir}")


def list_existing_keys(s3, bucket: str, prefix: str) -> set[str]:
    """Return every object key already under ``prefix`` (for resume/skip)."""
    keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix.rstrip('/')}/"):
        for obj in page.get("Contents") or []:
            keys.add(obj["Key"])
    return keys


def download(url: str, retries: int = 3) -> bytes | None:
    """Fetch image bytes. Returns None on a definitive 404 (image variant absent)."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as resp:
                return resp.read()
        except HTTPError as err:
            if err.code == 404:
                return None  # this variant simply does not exist
            last_err = err
        except (URLError, TimeoutError) as err:
            last_err = err
        if attempt < retries - 1:  # no point sleeping after the final attempt
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed to download {url}: {last_err}")


class Counts:
    def __init__(self) -> None:
        self.uploaded = 0
        self.skipped = 0
        self.missing = 0
        self.errors = 0
        self._lock = threading.Lock()

    def add(self, field: str) -> None:
        with self._lock:
            setattr(self, field, getattr(self, field) + 1)

    def total(self) -> int:
        return self.uploaded + self.skipped + self.missing + self.errors


def mirror_one(
    s3,
    bucket: str,
    url: str,
    key: str,
    existing: set[str],
    counts: Counts,
    *,
    overwrite: bool,
    dry_run: bool,
) -> None:
    if not overwrite and key in existing:
        counts.add("skipped")
        return
    try:
        data = download(url)
    except RuntimeError as err:
        print(f"  ERROR {err}", file=sys.stderr)
        counts.add("errors")
        return
    if data is None:
        counts.add("missing")
        return
    if dry_run:
        counts.add("uploaded")
        return
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg")
        counts.add("uploaded")
    except (BotoCoreError, ClientError) as err:
        print(f"  ERROR uploading {key}: {err}", file=sys.stderr)
        counts.add("errors")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror ZFIN images into S3 (GEN-22).")
    parser.add_argument("--metadata", help="Path to image_metadata*.json")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N images")
    parser.add_argument("--skip-annot", action="store_true", help="Mirror only plain .jpg")
    parser.add_argument("--overwrite", action="store_true", help="Re-upload even if present")
    parser.add_argument("--dry-run", action="store_true", help="Download but do not upload")
    args = parser.parse_args()

    meta_path = find_metadata_file(args.metadata)
    print(f"Loading metadata from {meta_path} ...")
    records = load_metadata(meta_path)
    if args.limit:
        records = records[: args.limit]
    print(f"{len(records)} image records.")

    # Build the (url, key) work list — plain + medium always, annotated unless
    # skipped. The grid serves the medium variant (GEN-36), so mirroring it keeps
    # the grid resilient to ZFIN outages just like the full-res lightbox image.
    tasks: list[tuple[str, str]] = []
    for r in records:
        image_id = r.get("image_id") or ""
        pub_id = (r.get("publication") or {}).get("publication_id") or ""
        if not image_id or not pub_id:
            continue
        annot_url, plain_url, medium_url = build_image_urls(pub_id, image_id)
        tasks.append((plain_url, url_to_key(plain_url, args.prefix)))
        tasks.append((medium_url, url_to_key(medium_url, args.prefix)))
        if not args.skip_annot:
            tasks.append((annot_url, url_to_key(annot_url, args.prefix)))
    print(f"{len(tasks)} image files to consider (plain + medium + annotated).")

    config = Config(region_name=args.region, retries={"max_attempts": 5, "mode": "standard"})
    s3 = boto3.client("s3", config=config)

    print(f"Listing existing objects under s3://{args.bucket}/{args.prefix}/ ...")
    existing = set() if args.overwrite else list_existing_keys(s3, args.bucket, args.prefix)
    print(f"{len(existing)} objects already present (will be skipped).")

    counts = Counts()
    total = len(tasks)
    start = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                mirror_one, s3, args.bucket, url, key, existing, counts,
                overwrite=args.overwrite, dry_run=args.dry_run,
            )
            for url, key in tasks
        ]
        for i, _ in enumerate(as_completed(futures), 1):
            if i % 500 == 0 or i == total:
                rate = i / max(time.monotonic() - start, 1e-6)
                print(
                    f"  {i}/{total} processed "
                    f"(uploaded={counts.uploaded} skipped={counts.skipped} "
                    f"missing={counts.missing} errors={counts.errors}) "
                    f"{rate:.0f}/s",
                    flush=True,
                )

    elapsed = time.monotonic() - start
    print(
        f"\nDone in {elapsed:.0f}s. uploaded={counts.uploaded} "
        f"skipped={counts.skipped} missing={counts.missing} errors={counts.errors}"
    )
    return 1 if counts.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
