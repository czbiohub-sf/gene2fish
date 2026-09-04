"""Security response headers are attached to every response (GEN-6).

The middleware in ``gene2image.main`` adds Content-Security-Policy,
X-Content-Type-Options and Referrer-Policy to both API and static-file
responses. These tests pin that contract and the CSP shape the SPA needs
(Vite bundles, inline analytics bootstrap, ZFIN images, the ZebraHub iframe
embed, and temporary Biohub-owned Vercel preview embeds during DNS cutovers).
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

EXPECTED = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "image_metadata.json").write_text("[]")
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        yield c


def test_api_responses_carry_security_headers(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    for header, value in EXPECTED.items():
        assert resp.headers[header] == value
    assert "content-security-policy" in resp.headers


def test_csp_supports_spa_and_zfin_images(client):
    csp = client.get("/api/health").headers["content-security-policy"]
    # Same-origin default, ZFIN images allowed, inline analytics bootstrap and
    # the Plausible script permitted, and clickjacking locked down.
    assert "default-src 'self'" in csp
    assert "img-src 'self' data: https://zfin.org" in csp
    # JetBrains Mono is base64-inlined as data: URIs in the built CSS, so
    # font-src must permit data: (verified against the real SPA in a browser).
    assert "font-src 'self' data:" in csp
    assert "https://plausible.io" in csp
    # @sentry/react POSTs error envelopes to the ingest endpoint from the
    # browser (GEN-37); connect-src must allow it or events are dropped.
    assert "connect-src 'self' https://plausible.io https://o4508060872409088.ingest.us.sentry.io" in csp
    assert "frame-ancestors 'self' https://*.czbiohub.org https://*-czbiohub.vercel.app" in csp
    assert "https://*.vercel.app" not in csp


def test_embeddable_in_zebrahub_but_not_elsewhere(client):
    # Gene2Fish is embedded in an iframe inside ZebraHub for the public launch
    # (GEN-46): frame-ancestors must allow Biohub origins and Biohub-owned
    # Vercel previews only, and X-Frame-Options must be absent — DENY would be
    # honored by browsers that predate frame-ancestors and it cannot express an
    # allowlist.
    resp = client.get("/api/health")
    csp = resp.headers["content-security-policy"]
    assert "frame-ancestors 'self' https://*.czbiohub.org https://*-czbiohub.vercel.app" in csp
    assert "https://*.vercel.app" not in csp
    assert "frame-ancestors 'none'" not in csp
    assert "x-frame-options" not in resp.headers


def test_image_proxy_keeps_single_nosniff_header(client, monkeypatch):
    # The image proxy sets X-Content-Type-Options itself; the middleware uses
    # setdefault, so the header must appear exactly once (not duplicated).
    from gene2image import s3_images

    monkeypatch.setattr(s3_images, "s3_enabled", lambda: True)
    monkeypatch.setattr(s3_images, "fetch_image", lambda url: (b"bytes", "image/jpeg"))

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )
    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    # Starlette joins duplicate headers with ", "; a single value proves no dup.
    assert resp.headers.get_list("x-content-type-options") == ["nosniff"]


def test_static_files_carry_security_headers(tmp_path):
    # Reload the module with a mounted frontend so the middleware is exercised
    # against a StaticFiles response, then restore a clean module for later tests.
    from gene2image import main

    (tmp_path / "index.html").write_text("<html><body>hi</body></html>")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "image_metadata.json").write_text("[]")

    old_front = os.environ.get("GENE2IMAGE_FRONTEND_DIR")
    old_data = os.environ.get("GENE2IMAGE_DATA_DIR")
    os.environ["GENE2IMAGE_FRONTEND_DIR"] = str(tmp_path)
    os.environ["GENE2IMAGE_DATA_DIR"] = str(data_dir)
    try:
        importlib.reload(main)
        with TestClient(main.app) as c:
            resp = c.get("/")
        assert resp.status_code == 200
        for header, value in EXPECTED.items():
            assert resp.headers[header] == value
        assert "default-src 'self'" in resp.headers["content-security-policy"]
    finally:
        for key, old in (
            ("GENE2IMAGE_FRONTEND_DIR", old_front),
            ("GENE2IMAGE_DATA_DIR", old_data),
        ):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        importlib.reload(main)
