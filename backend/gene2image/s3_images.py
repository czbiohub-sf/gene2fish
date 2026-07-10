"""Map ZFIN image URLs to our public S3 mirror (GEN-22, GEN-27).

The in-situ images are mirrored into our own S3 bucket (``zfin_image_mirror.py``)
and that prefix is served **publicly** (the images are ZFIN's, under CC BY 4.0 —
there is nothing private to protect). Serving them publicly means neither the
backend nor the browser needs any AWS credentials: the app just points at the
public object URL. This is what makes image loading work identically in local,
staging and prod — there is no auth to configure per environment (GEN-27).

The S3 key layout mirrors the ZFIN path 1:1, so a canonical ZFIN image URL maps
to a public URL by a simple prefix swap:

    https://zfin.org/imageLoadUp/{year}/{pub}/{file}
        → https://{bucket}.s3.{region}.amazonaws.com/{prefix}/imageLoadUp/{year}/{pub}/{file}

Everything is overridable by env var (e.g. to point at a CloudFront distribution
via ``GENE2IMAGE_IMAGE_BASE_URL``), but the defaults work with no configuration.
"""

from __future__ import annotations

import os

# Canonical ZFIN image URL prefix (matches routes._build_image_url output).
ZFIN_IMAGELOADUP_PREFIX = "https://zfin.org/imageLoadUp/"

DEFAULT_BUCKET = "czbsf-rnaquarium"
DEFAULT_PREFIX = "gene2fish/zfin-images"
DEFAULT_REGION = "us-west-2"


def _bucket() -> str:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_BUCKET") or DEFAULT_BUCKET


def _prefix() -> str:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_PREFIX", DEFAULT_PREFIX).strip("/")


def _region() -> str:
    return os.environ.get("GENE2IMAGE_IMAGE_S3_REGION") or DEFAULT_REGION


def base_url() -> str:
    """Public base URL for mirrored images (S3 virtual-hosted, or a CDN override)."""
    override = os.environ.get("GENE2IMAGE_IMAGE_BASE_URL")
    if override:
        return override.rstrip("/")
    return f"https://{_bucket()}.s3.{_region()}.amazonaws.com"


def s3_key_for_url(url: str) -> str | None:
    """Map a canonical ZFIN imageLoadUp URL to its S3 key, or None if not one."""
    if not url.startswith(ZFIN_IMAGELOADUP_PREFIX):
        return None
    rel = url[len(ZFIN_IMAGELOADUP_PREFIX):]  # imageLoadUp/{year}/{pub}/{file}
    return f"{_prefix()}/imageLoadUp/{rel}"


def public_image_prefix() -> str:
    """Public URL prefix under which all mirrored images live."""
    return f"{base_url()}/{_prefix()}/imageLoadUp/"


def public_url(zfin_url: str) -> str | None:
    """Public mirror URL for a canonical ZFIN image URL, or None if not one."""
    key = s3_key_for_url(zfin_url)
    if key is None:
        return None
    return f"{base_url()}/{key}"


def is_mirror_url(url: str) -> bool:
    """True if the URL points at our public image mirror (used to gate the proxy)."""
    return url.startswith(public_image_prefix())
