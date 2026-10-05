"""Serve the mirrored ZFIN Thisse images from our own S3 bucket (GEN-22, GEN-45).

The bucket holds exactly the image package ZFIN provided for the Thisse
datasets, which is all legal cleared us to host. The backend image proxy serves
images from this bucket and nowhere else: it never fetches from ZFIN itself, so
it can't be used to redistribute images outside that package. An image that
isn't mirrored is a 404, and the browser then hotlinks it straight from zfin.org
(see frontend/src/utils/imageProxy.js).

This module keeps the bucket private: it fetches objects with the deployment's
own AWS credentials (standard credential chain) rather than exposing the bucket
publicly. When ``GENE2IMAGE_IMAGE_S3_BUCKET`` is unset nothing is mirrored, so
every lookup is a miss and every image loads from zfin.org (e.g. in local dev).

The S3 key layout mirrors the ZFIN path 1:1, so a canonical ZFIN image URL maps
to a key by a simple prefix swap (see ``s3_key_for_url``).
"""

from __future__ import annotations

import os
import threading

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Canonical ZFIN image URL prefix (matches routes._build_image_url output).
ZFIN_IMAGELOADUP_PREFIX = "https://zfin.org/imageLoadUp/"

DEFAULT_PREFIX = "gene2fish/zfin-images"
DEFAULT_REGION = "us-west-2"


class ImageMirrorError(Exception):
    """The mirror could not be read (credentials, permissions, network, bad object).

    Distinct from a miss: the proxy reports it as an error instead of passing it
    off as "not mirrored", so a broken mirror is visible rather than silent.
    """


# boto3 client is built lazily and cached. A failed construction is not cached:
# it raises and is retried on the next request.
_client = None
_client_lock = threading.Lock()


def _bucket() -> str | None:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_BUCKET") or None


def _prefix() -> str:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_PREFIX", DEFAULT_PREFIX).rstrip("/")


def s3_key_for_url(url: str) -> str | None:
    """Map a canonical ZFIN imageLoadUp URL to its S3 key, or None if not one."""
    if not url.startswith(ZFIN_IMAGELOADUP_PREFIX):
        return None
    rel = url[len(ZFIN_IMAGELOADUP_PREFIX):]  # imageLoadUp/{year}/{pub}/{file}
    return f"{_prefix()}/imageLoadUp/{rel}"


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                region = os.environ.get("GENE2IMAGE_IMAGE_S3_REGION", DEFAULT_REGION)
                _client = boto3.client(
                    "s3",
                    config=Config(
                        region_name=region,
                        retries={"max_attempts": 2, "mode": "standard"},
                    ),
                )
    return _client


def fetch_image(url: str) -> tuple[bytes, str] | None:
    """Return ``(bytes, media_type)`` for a mirrored image, or None if it isn't mirrored.

    None means the image is not in the mirror: no bucket is configured, the URL
    is not a ZFIN imageLoadUp URL, or the object does not exist. Anything else
    (credentials, permissions, network, a non-image object) raises
    ImageMirrorError.
    """
    bucket = _bucket()
    if not bucket:
        return None
    key = s3_key_for_url(url)
    if not key:
        return None
    try:
        client = _get_client()
        resp = client.get_object(Bucket=bucket, Key=key)
        stream = resp["Body"]
        try:
            body = stream.read()
        finally:
            stream.close()  # release the HTTP connection back to the pool
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") == "NoSuchKey":
            return None
        raise ImageMirrorError(f"S3 read failed for {key}") from err
    except Exception as err:  # credentials / network / stream errors
        raise ImageMirrorError(f"S3 read failed for {key}") from err
    media_type = resp.get("ContentType") or "image/jpeg"
    if not media_type.startswith("image/"):
        # The proxy serves these bytes from our own origin: a non-image (e.g.
        # HTML) object must never be returned where it could render as a page.
        raise ImageMirrorError(f"S3 object {key} is not an image ({media_type})")
    return body, media_type
