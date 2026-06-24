"""Serve mirrored ZFIN images from our own S3 bucket (GEN-22).

The application used to hotlink in-situ images straight from zfin.org, so a
momentary ZFIN outage broke image loading in the UI. To decouple from ZFIN's
live availability, the images are mirrored into our own bucket
(``zfin_image_mirror.py``) and the backend image proxy now tries S3 first,
falling back to live ZFIN only when the object is missing or S3 is unreachable.

This module keeps the bucket private: it fetches objects with the deployment's
own AWS credentials (standard credential chain) rather than exposing the bucket
publicly. It is *opt-in*: when ``GENE2IMAGE_IMAGE_S3_BUCKET`` is unset, S3 is
skipped entirely and the proxy behaves exactly as before (a ZFIN passthrough),
so the change is a no-op until the bucket is configured in deployment.

The S3 key layout mirrors the ZFIN path 1:1, so a canonical ZFIN image URL maps
to a key by a simple prefix swap (see ``s3_key_for_url``).
"""

from __future__ import annotations

import os
import threading

# Canonical ZFIN image URL prefix (matches routes._build_image_url output).
ZFIN_IMAGELOADUP_PREFIX = "https://zfin.org/imageLoadUp/"

DEFAULT_PREFIX = "gene2fish/zfin-images"
DEFAULT_REGION = "us-west-2"

# boto3 client is built lazily and cached. _client_unavailable latches True once
# construction fails (e.g. boto3 missing) so we don't retry it on every request.
_client = None
_client_unavailable = False
_client_lock = threading.Lock()


def _bucket() -> str | None:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_BUCKET") or None


def _prefix() -> str:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_PREFIX", DEFAULT_PREFIX).rstrip("/")


def s3_enabled() -> bool:
    """True when a mirror bucket is configured (otherwise the proxy is ZFIN-only)."""
    return _bucket() is not None


def s3_key_for_url(url: str) -> str | None:
    """Map a canonical ZFIN imageLoadUp URL to its S3 key, or None if not one."""
    if not url.startswith(ZFIN_IMAGELOADUP_PREFIX):
        return None
    rel = url[len(ZFIN_IMAGELOADUP_PREFIX):]  # imageLoadUp/{year}/{pub}/{file}
    return f"{_prefix()}/imageLoadUp/{rel}"


def _get_client():
    global _client, _client_unavailable
    if _client is not None or _client_unavailable:
        return _client
    with _client_lock:
        if _client is None and not _client_unavailable:
            try:
                import boto3
                from botocore.config import Config

                region = os.environ.get("GENE2IMAGE_IMAGE_S3_REGION", DEFAULT_REGION)
                _client = boto3.client(
                    "s3",
                    config=Config(
                        region_name=region,
                        retries={"max_attempts": 2, "mode": "standard"},
                    ),
                )
            except Exception:  # noqa: BLE001 — any failure → fall back to ZFIN
                _client_unavailable = True
    return _client


def fetch_image(url: str) -> tuple[bytes, str] | None:
    """Return ``(bytes, media_type)`` for a mirrored image, or None to fall back.

    Returns None — signalling the caller to fetch live from ZFIN — when no bucket
    is configured, the URL is not a ZFIN imageLoadUp URL, the object is absent, or
    any S3/credential error occurs. The goal is that S3 can only *improve*
    availability and never breaks image loading.
    """
    bucket = _bucket()
    if not bucket:
        return None
    key = s3_key_for_url(url)
    if not key:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        media_type = resp.get("ContentType") or "image/jpeg"
        return body, media_type
    except Exception:  # noqa: BLE001 — missing key / network / creds → ZFIN fallback
        return None
