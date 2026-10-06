#!/usr/bin/env python3
"""ZFIN Thisse image package → S3 mirror.

Uploads the Thisse in-situ hybridization image package that ZFIN provided
(``thisse-images.tar``) into our own S3 bucket, so the backend serves the images
from our cloud through ``/api/image-proxy`` (GEN-22, GEN-45).

The mirror must hold exactly that package and nothing else: legal cleared us to
host the Thisse images ZFIN sent, and rights for other ZFIN images are decided
case by case. So this script never downloads from zfin.org. It reads the
tarball, and if any file in it falls outside the five Thisse publications or
the expected layout it uploads nothing at all.

The package's paths map 1:1 onto the key layout the backend looks up (see
``backend/gene2image/s3_images.py``)::

    opt/zfin/loadUp/pubs/{year}/{pub_id}/{file}
        → s3://{bucket}/{prefix}/imageLoadUp/{year}/{pub_id}/{file}

The run is resumable: objects already present under the prefix are listed once
up front and skipped, so re-running only uploads what is missing.

Credentials are read from the standard AWS chain (env vars, shared config, or an
instance/role profile). Never hard-code keys here.

Usage::

    python zfin_image_mirror.py --package thisse-images.tar --bucket BUCKET --dry-run
    python zfin_image_mirror.py --package thisse-images.tar --bucket BUCKET
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_PREFIX = "gene2fish/zfin-images"
DEFAULT_REGION = "us-west-2"

# The five Thisse publications in ZFIN's package (also the extractor's default
# publication filter in zfin_image_metadata_extractor.py).
THISSE_PUBLICATIONS = frozenset({
    "ZDB-PUB-010810-1",   # Thisse 2001
    "ZDB-PUB-040907-1",   # Thisse 2004
    "ZDB-PUB-051025-1",   # Thisse 2005
    "ZDB-PUB-080220-1",   # Thisse 2008
    "ZDB-PUB-080227-22",  # Thisse 2008
})

# opt/zfin/loadUp/pubs/{year}/{pub_id}/{image_id}{variant}.jpg, as ZFIN packaged it.
MEMBER_RE = re.compile(
    r"^(?:\./)?opt/zfin/loadUp/pubs/(?P<year>\d{4})/(?P<pub>ZDB-PUB-\d{6}-\d+)/"
    r"(?P<file>ZDB-IMAGE-\d{6}-\d+(?:_annot|_medium|_thumb|_annot_medium)?\.jpg)$"
)


def member_key(name: str, prefix: str) -> str:
    """Map a package member to its S3 key; ValueError if it isn't a Thisse image."""
    match = MEMBER_RE.match(name)
    if not match:
        raise ValueError(f"unexpected path in package: {name}")
    year, pub, file = match.group("year", "pub", "file")
    if pub not in THISSE_PUBLICATIONS:
        raise ValueError(f"not a Thisse publication: {name}")
    if year != "20" + pub.split("-")[2][:2]:
        # The backend derives the year directory from the publication ID, so a
        # mismatched year would upload objects the proxy never looks up.
        raise ValueError(f"year directory does not match {pub}: {name}")
    return f"{prefix.rstrip('/')}/imageLoadUp/{year}/{pub}/{file}"


def plan_uploads(tf: tarfile.TarFile, prefix: str) -> list[tuple[tarfile.TarInfo, str]]:
    """Validate every package member before anything is uploaded.

    Fails closed: a single member that isn't a Thisse image in the expected
    layout means this is not the package we were cleared to host.
    """
    plan: list[tuple[tarfile.TarInfo, str]] = []
    problems: list[str] = []
    for member in tf.getmembers():
        if member.isdir():
            continue
        if not member.isfile():
            problems.append(f"not a regular file: {member.name}")
            continue
        try:
            plan.append((member, member_key(member.name, prefix)))
        except ValueError as err:
            problems.append(str(err))
    keys = [key for _, key in plan]
    if len(set(keys)) != len(keys):
        problems.append("the package holds the same image path more than once")
    if problems:
        shown = "\n  ".join(problems[:20])
        sys.exit(
            f"Refusing to upload anything: {len(problems)} problem(s) in the package "
            f"(only the ZFIN-provided Thisse images may be mirrored):\n  {shown}"
        )
    if not plan:
        sys.exit("Refusing to upload: the package contains no images.")
    return plan


def list_existing_keys(s3, bucket: str, prefix: str) -> set[str]:
    """Return every object key already under ``prefix`` (for resume/skip)."""
    keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix.rstrip('/')}/"):
        for obj in page.get("Contents") or []:
            keys.add(obj["Key"])
    return keys


def upload_all(s3, bucket: str, tf: tarfile.TarFile, todo, workers: int) -> tuple[int, int]:
    """Upload ``todo`` and return ``(uploaded, errors)``."""

    def put(key: str, data: bytes) -> bool:
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg")
            return True
        except (BotoCoreError, ClientError) as err:
            print(f"  ERROR uploading {key}: {err}", file=sys.stderr)
            return False

    uploaded = errors = 0

    def tally(done) -> None:
        nonlocal uploaded, errors
        for future in done:
            if future.result():
                uploaded += 1
            else:
                errors += 1

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = set()
        for i, (member, key) in enumerate(todo, 1):
            fileobj = tf.extractfile(member)
            if fileobj is None:  # plan_uploads keeps regular files only
                sys.exit(f"Cannot read {member.name} from the package.")
            pending.add(pool.submit(put, key, fileobj.read()))
            # Bound the in-flight uploads so the package isn't buffered in memory.
            if len(pending) >= workers * 4:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                tally(done)
            if i % 5000 == 0 or i == len(todo):
                rate = i / max(time.monotonic() - start, 1e-6)
                print(f"  {i}/{len(todo)} read ({rate:.0f}/s)", flush=True)
        tally(wait(pending).done)
    return uploaded, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upload the ZFIN-provided Thisse image package to the S3 mirror (GEN-22, GEN-45)."
    )
    parser.add_argument("--package", required=True, type=Path, help="Path to ZFIN's thisse-images.tar")
    parser.add_argument("--bucket", required=True, help="Mirror bucket, e.g. gene2fish-zfin-images-dev")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--overwrite", action="store_true", help="Re-upload objects that already exist")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate the package and report what would be uploaded"
    )
    args = parser.parse_args(argv)

    # "r:" = uncompressed only: random access per member stays cheap on a 9 GB tar.
    with tarfile.open(args.package, "r:") as tf:
        print(f"Validating {args.package} ...")
        plan = plan_uploads(tf, args.prefix)
        print(f"{len(plan)} files, all Thisse images in the expected layout.")

        config = Config(region_name=args.region, retries={"max_attempts": 5, "mode": "standard"})
        s3 = boto3.client("s3", config=config)
        print(f"Listing existing objects under s3://{args.bucket}/{args.prefix}/ ...")
        existing = set() if args.overwrite else list_existing_keys(s3, args.bucket, args.prefix)
        todo = [(member, key) for member, key in plan if key not in existing]
        skipped = len(plan) - len(todo)

        if args.dry_run:
            print(f"Dry run: would upload {len(todo)}, skip {skipped} already in the mirror.")
            return 0
        uploaded, errors = upload_all(s3, args.bucket, tf, todo, args.workers)

    print(f"\nDone. uploaded={uploaded} skipped={skipped} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
