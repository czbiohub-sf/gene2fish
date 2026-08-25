import json
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # load_data() runs in the app lifespan and requires GENE2IMAGE_DATA_DIR to
    # point at a dir with image_metadata.json. An empty JSON array is the
    # minimal valid dataset (empty indexes; every route still responds).
    (tmp_path / "image_metadata.json").write_text("[]")
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_has_typed_openapi_contract(client):
    # /health must expose a named ($ref) response schema, not an anonymous
    # inline object — so a future change to the return shape surfaces as a
    # breaking-change signal in the OpenAPI diff.
    schema = client.get("/openapi.json").json()
    content = schema["paths"]["/api/health"]["get"]["responses"]["200"]["content"]
    response_schema = content["application/json"]["schema"]
    assert "$ref" in response_schema
    model = schema["components"]["schemas"][response_schema["$ref"].split("/")[-1]]
    assert model["properties"]["status"]["type"] == "string"


def test_unknown_api_path_returns_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


def test_known_routes_not_shadowed_by_catchall(client):
    assert client.get("/api/health").status_code == 200
    # real route returns 200 (empty data) — never 404 from the catch-all
    assert client.get("/api/stages").status_code != 404


def test_image_proxy_restricts_to_zfin_imageloadup_urls(client):
    resp = client.get("/api/image-proxy?url=https://example.com/image.jpg")
    assert resp.status_code == 400

    resp = client.get("/api/image-proxy?url=https://zfin.org/ZDB-IMAGE-123")
    assert resp.status_code == 400


def test_image_proxy_returns_image_bytes(client, monkeypatch):
    from gene2image import routes

    class Headers:
        def get_content_type(self):
            return "image/jpeg"

    class FakeResponse:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"image-bytes"

    def fake_urlopen(request, timeout, context=None):
        assert request.full_url == "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"
        assert timeout == 15
        return FakeResponse()

    monkeypatch.setattr(routes, "urlopen", fake_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 200
    assert resp.content == b"image-bytes"
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers["access-control-allow-origin"] == "*"
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_image_proxy_rejects_non_image_content(client, monkeypatch):
    # Content-type hardening: the proxy serves only images. If ZFIN returns a
    # non-image (e.g. text/html) body, it must be refused — never returned so it
    # could render as a document on our own origin (XSS). Without the image/*
    # check this returns 200 + the HTML body.
    from gene2image import routes

    class Headers:
        def get_content_type(self):
            return "text/html"

    class FakeResponse:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"<script>alert(document.domain)</script>"

    monkeypatch.setattr(
        routes, "urlopen", lambda request, timeout, context=None: FakeResponse()
    )

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 502
    assert b"<script>" not in resp.content


def test_image_proxy_does_not_follow_redirects(client, monkeypatch):
    # SSRF guard: the allowlist only validates the *initial* URL. If ZFIN (or an
    # open redirect on it) 3xx-redirects to an internal host, the proxy must NOT
    # follow it. Stand up a local server that redirects to a "secret" path and
    # assert the secret is never fetched or returned to the caller.
    import http.server
    import threading

    from gene2image import routes

    secret = b"INTERNAL-SECRET"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/secret":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(secret)
            else:
                self.send_response(302)
                self.send_header("Location", "/secret")
                self.end_headers()

        def log_message(self, format, *args):  # silence test-server logging
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Bypass the zfin.org allowlist so the fetch can target the local
        # redirecting server; the redirect-following behavior is what we test.
        monkeypatch.setattr(routes, "_validate_zfin_image_url", lambda url: None)
        resp = client.get(
            "/api/image-proxy", params={"url": f"http://127.0.0.1:{port}/redirect"}
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    # Redirect refused → surfaced as a non-2xx error, and the secret body is
    # never returned. Without the no-redirect opener this returns 200 + secret.
    assert resp.status_code != 200
    assert secret not in resp.content


def test_image_proxy_returns_502_when_fetch_fails(client, monkeypatch):
    from gene2image import routes

    monkeypatch.setattr(routes.time, "sleep", lambda seconds: None)

    def fake_urlopen(request, timeout):
        raise URLError("certificate verify failed")

    monkeypatch.setattr(routes, "urlopen", fake_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 502


class _FakeImageResponse:
    class _Headers:
        def get_content_type(self):
            return "image/jpeg"

    headers = _Headers()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"image-bytes"


def test_image_proxy_retries_transient_failures(client, monkeypatch):
    # ZFIN fails intermittently (resets/timeouts/sporadic 5xx) even when it is
    # otherwise up; a transient failure must be retried and served, not
    # surfaced as a broken image (GEN-46).
    from gene2image import routes

    monkeypatch.setattr(routes.time, "sleep", lambda seconds: None)

    calls = {"n": 0}

    def flaky_urlopen(request, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise URLError("connection reset by peer")
        if calls["n"] == 2:
            raise HTTPError(request.full_url, 503, "Service Unavailable", None, None)
        return _FakeImageResponse()

    monkeypatch.setattr(routes, "urlopen", flaky_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 200
    assert resp.content == b"image-bytes"
    assert calls["n"] == 3


def test_image_proxy_does_not_retry_4xx(client, monkeypatch):
    # 4xx is definitive (e.g. a genuinely missing _annot.jpg variant) — the
    # proxy must fail fast so the plain-variant fallback isn't delayed by
    # pointless retries. The endpoint's annot→plain fallback means exactly two
    # fetches happen (one per URL), never more.
    from gene2image import routes

    monkeypatch.setattr(routes.time, "sleep", lambda seconds: None)

    urls = []

    def notfound_urlopen(request, timeout):
        urls.append(request.full_url)
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(routes, "urlopen", notfound_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1_annot.jpg"},
    )

    assert resp.status_code == 404
    assert urls == [
        "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1_annot.jpg",
        "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg",
    ]


def test_image_proxy_serves_from_s3_when_mirrored(client, monkeypatch):
    # When the mirror bucket is configured and holds the object, the proxy must
    # serve the S3 bytes and never touch ZFIN (GEN-22).
    from gene2image import routes, s3_images

    def boom(*args, **kwargs):  # ZFIN must not be hit on an S3 hit
        raise AssertionError("ZFIN should not be fetched when S3 has the image")

    monkeypatch.setattr(routes, "urlopen", boom)
    monkeypatch.setattr(s3_images, "s3_enabled", lambda: True)
    monkeypatch.setattr(
        s3_images, "fetch_image", lambda url: (b"s3-bytes", "image/jpeg")
    )

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 200
    assert resp.content == b"s3-bytes"
    assert resp.headers["cache-control"] == "public, max-age=86400"


def test_image_proxy_falls_back_to_zfin_when_not_mirrored(client, monkeypatch):
    # S3 enabled but object missing (fetch_image returns None) → live ZFIN fetch.
    from gene2image import routes, s3_images

    class Headers:
        def get_content_type(self):
            return "image/jpeg"

    class FakeResponse:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"zfin-bytes"

    monkeypatch.setattr(routes, "urlopen", lambda request, timeout, context=None: FakeResponse())
    monkeypatch.setattr(s3_images, "s3_enabled", lambda: True)
    monkeypatch.setattr(s3_images, "fetch_image", lambda url: None)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"},
    )

    assert resp.status_code == 200
    assert resp.content == b"zfin-bytes"


def test_image_proxy_falls_back_to_plain_when_annotated_missing(client, monkeypatch):
    # ZFIN has no `_annot.jpg` for many images (404); the proxy must retry the
    # plain `.jpg` server-side so the browser gets one 200 instead of a 404.
    from gene2image import routes

    class Headers:
        def get_content_type(self):
            return "image/jpeg"

    class FakeResponse:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"plain-bytes"

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("_annot.jpg"):
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        return FakeResponse()

    monkeypatch.setattr(routes, "urlopen", fake_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1_annot.jpg"},
    )

    assert resp.status_code == 200
    assert resp.content == b"plain-bytes"


def test_image_proxy_404s_when_both_annotated_and_plain_missing(client, monkeypatch):
    # A genuine 404 (neither variant exists) must still surface, not be masked.
    from gene2image import routes

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(routes, "urlopen", fake_urlopen)

    resp = client.get(
        "/api/image-proxy",
        params={"url": "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1_annot.jpg"},
    )

    assert resp.status_code == 404


def test_build_image_url_includes_medium():
    # The grid serves ZFIN's medium variant (~15KB, 500x374) instead of the
    # full-res image (~377KB) — the tiny 86x64 thumbnail looked blurry upscaled
    # into the grid cell (GEN-36); _build_image_url must expose `_medium.jpg`.
    from gene2image.routes import _build_image_url

    annot, plain, medium = _build_image_url("ZDB-PUB-051025-1", "ZDB-IMAGE-060130-333")
    base = "https://zfin.org/imageLoadUp/2005/ZDB-PUB-051025-1/ZDB-IMAGE-060130-333"
    assert annot == f"{base}_annot.jpg"
    assert plain == f"{base}.jpg"
    assert medium == f"{base}_medium.jpg"


def test_s3_key_for_url_mirrors_zfin_path():
    from gene2image import s3_images

    key = s3_images.s3_key_for_url(
        "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"
    )
    assert key == "gene2fish/zfin-images/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"
    assert s3_images.s3_key_for_url("https://example.com/x.jpg") is None


def test_s3_disabled_by_default(monkeypatch):
    # No bucket env → S3 path is skipped entirely (proxy stays a ZFIN passthrough).
    from gene2image import s3_images

    monkeypatch.delenv("GENE2IMAGE_IMAGE_S3_BUCKET", raising=False)
    assert s3_images.s3_enabled() is False
    assert s3_images.fetch_image(
        "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"
    ) is None


def test_catchall_does_not_swallow_options(client):
    # The catch-all 404 must not claim OPTIONS — let the framework/CORSMiddleware
    # own it. Otherwise an OPTIONS to an unknown /api/* path returns a 404 JSON
    # body (a latent CORS-preflight trap) instead of deferring method handling.
    resp = client.options("/api/does-not-exist")
    assert resp.status_code != 404
    assert "API endpoint not found" not in resp.text


def test_anatomy_genes_are_limited_after_alphabetical_sort(tmp_path, monkeypatch):
    records = [
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "actb2"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "neurod1"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))

    from gene2image.main import app

    with TestClient(app) as c:
        resp = c.get("/api/anatomy/hindbrain/genes?limit=2")

    assert resp.status_code == 200
    assert resp.json() == {
        "total": 3,
        "genes": [
            {"gene_symbol": "actb2", "image_count": 1},
            {"gene_symbol": "neurod1", "image_count": 1},
        ],
    }


def test_anatomy_genes_support_and_selection(tmp_path, monkeypatch):
    records = [
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "heart"}],
        },
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "pronephros"}],
        },
        {
            "gene": {"gene_symbol": "actb2"},
            "anatomical_locations": [{"anatomy_name": "heart"}],
        },
        {
            "gene": {"gene_symbol": "actb2"},
            "anatomical_locations": [{"anatomy_name": "pronephros"}],
        },
        {
            "gene": {"gene_symbol": "heartonly"},
            "anatomical_locations": [{"anatomy_name": "heart"}],
        },
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))

    from gene2image.main import app

    with TestClient(app) as c:
        resp = c.get("/api/anatomy/genes?anatomy=heart&anatomy=pronephros")

    assert resp.status_code == 200
    assert resp.json() == {
        "total": 2,
        "genes": [
            {"gene_symbol": "actb2", "image_count": 2},
            {"gene_symbol": "zic1", "image_count": 2},
        ],
    }


def test_anatomy_search_returns_available_options_without_query(tmp_path, monkeypatch):
    records = [
        {
            "gene": {"gene_symbol": "actb2"},
            "anatomical_locations": [{"anatomy_name": "pronephros"}],
        },
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "heart"}],
        },
        {
            "gene": {"gene_symbol": "zic1"},
            "anatomical_locations": [{"anatomy_name": "hindbrain"}],
        },
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))

    from gene2image.main import app

    with TestClient(app) as c:
        all_options = c.get("/api/anatomy/search?q=")
        limited_options = c.get("/api/anatomy/search?q=&limit=2")
        filtered = c.get("/api/anatomy/search?q=brain")

    assert all_options.status_code == 200
    assert all_options.json() == ["heart", "hindbrain", "pronephros"]
    assert limited_options.status_code == 200
    assert limited_options.json() == ["heart", "hindbrain"]
    assert filtered.status_code == 200
    assert filtered.json() == ["hindbrain"]


def _alias_dataset(tmp_path, monkeypatch):
    """A dataset with one gene (pou5f3) plus an alias sidecar mapping its stable
    gene ID to previous names (oct4, pou2, ...)."""
    records = [
        {
            "image_id": "ZDB-IMAGE-1",
            "gene": {
                "gene_id": "ZDB-GENE-990415-72",
                "gene_symbol": "pou5f3",
                "gene_name": "POU domain, class 5, transcription factor 3",
            },
            "developmental_stages": [{"begin_hours": "5.25", "end_hours": "5.66"}],
            "publication": {"publication_id": "ZDB-PUB-040907-1"},
            "anatomical_locations": [{"anatomy_name": "blastoderm"}],
        }
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    (tmp_path / "gene_aliases.json").write_text(
        json.dumps({"ZDB-GENE-990415-72": ["oct4", "pou2", "Spiel ohne grenzen", "pou5f3"]})
    )
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    return app


def test_gene_search_matches_previous_alias_names(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        # Current symbol still matches and carries no alias annotation.
        by_symbol = c.get("/api/genes/search?q=pou5").json()
        # A previous name resolves to the canonical symbol, annotated with the alias.
        by_alias = c.get("/api/genes/search?q=oct4").json()
        # Multi-word previous names are searchable by prefix too.
        by_phrase = c.get("/api/genes/search?q=spiel").json()

    assert by_symbol == [{"symbol": "pou5f3", "matched_alias": None}]
    assert by_alias == [{"symbol": "pou5f3", "matched_alias": "oct4"}]
    assert by_phrase == [{"symbol": "pou5f3", "matched_alias": "Spiel ohne grenzen"}]


def test_gene_search_does_not_duplicate_when_symbol_and_alias_both_match(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        # "pou" prefixes both the current symbol (pou5f3) and an alias (pou2),
        # but the gene must appear once, via its current symbol.
        results = c.get("/api/genes/search?q=pou").json()

    assert results == [{"symbol": "pou5f3", "matched_alias": None}]


def test_gene_images_resolve_alias_to_canonical_gene(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        via_alias = c.get("/api/genes/oct4/images").json()
        via_symbol = c.get("/api/genes/pou5f3/images").json()

    assert len(via_alias) == 1
    assert via_alias[0]["gene_symbol"] == "pou5f3"
    assert via_alias == via_symbol


def test_gene_batch_resolves_alias_to_canonical_gene(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        resp = c.post("/api/genes/batch", json={"genes": ["pou2"]}).json()

    assert len(resp["pou2"]) == 1
    assert resp["pou2"][0]["gene_symbol"] == "pou5f3"


def test_gene_search_without_alias_sidecar_still_works(tmp_path, monkeypatch):
    # No gene_aliases.json present — search degrades to symbol-only matching.
    records = [{"gene": {"gene_symbol": "pax2a", "gene_id": "ZDB-GENE-1"}}]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        assert c.get("/api/genes/search?q=pax").json() == [
            {"symbol": "pax2a", "matched_alias": None}
        ]
        assert c.get("/api/genes/search?q=oct4").json() == []


def test_gene_search_fails_closed_on_malformed_sidecar(tmp_path, monkeypatch):
    # A sidecar that isn't a {gene_id: [aliases]} object (here a list, and a gene
    # whose aliases are a bare string) must not crash startup or iterate string
    # characters — it degrades to symbol-only search.
    records = [{"gene": {"gene_symbol": "pax2a", "gene_id": "ZDB-GENE-1"}}]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    (tmp_path / "gene_aliases.json").write_text(json.dumps(["not", "a", "dict"]))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        assert c.get("/api/genes/search?q=pax").json() == [
            {"symbol": "pax2a", "matched_alias": None}
        ]
        # No alias matches surface, and nothing 500s.
        assert c.get("/api/genes/search?q=oct").json() == []


def test_gene_search_skips_non_list_and_non_string_aliases(tmp_path, monkeypatch):
    records = [
        {"gene": {"gene_symbol": "pax2a", "gene_id": "ZDB-GENE-1"}},
        {"gene": {"gene_symbol": "shha", "gene_id": "ZDB-GENE-2"}},
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    (tmp_path / "gene_aliases.json").write_text(
        json.dumps(
            {
                "ZDB-GENE-1": "oldpax",          # string, not a list → skipped
                "ZDB-GENE-2": ["sonic", 123, ""],  # list with junk → only "sonic" kept
            }
        )
    )
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        # The string value must not be iterated character-by-character: "oldpax"
        # would otherwise register single-letter aliases like "o".
        assert c.get("/api/genes/search?q=o").json() == []
        # The valid alias in the list still resolves; the int and "" are skipped.
        assert c.get("/api/genes/search?q=sonic").json() == [
            {"symbol": "shha", "matched_alias": "sonic"}
        ]


def test_resolve_gene_returns_canonical_symbol(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        # Exact current symbol resolves to itself with no alias annotation.
        exact = c.get("/api/genes/pou5f3/resolve")
        # A case-mismatched current symbol is normalized to the canonical casing.
        cased = c.get("/api/genes/POU5F3/resolve")
        # A previous/alias name resolves to the canonical symbol, annotated.
        via_alias = c.get("/api/genes/oct4/resolve")

    assert exact.status_code == 200
    assert exact.json() == {"symbol": "pou5f3", "matched_alias": None}
    assert cased.status_code == 200
    assert cased.json() == {"symbol": "pou5f3", "matched_alias": None}
    assert via_alias.status_code == 200
    assert via_alias.json() == {"symbol": "pou5f3", "matched_alias": "oct4"}


def test_resolve_gene_rejects_unknown_symbol(tmp_path, monkeypatch):
    app = _alias_dataset(tmp_path, monkeypatch)
    with TestClient(app) as c:
        resp = c.get("/api/genes/notagene/resolve")

    # An invalid name must 404 so the client never opens an empty column for it.
    assert resp.status_code == 404
    assert "notagene" in resp.json()["detail"]


def test_resolve_gene_without_alias_sidecar_still_validates_symbols(tmp_path, monkeypatch):
    records = [{"gene": {"gene_symbol": "pax2a", "gene_id": "ZDB-GENE-1"}}]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        assert c.get("/api/genes/pax2a/resolve").json() == {
            "symbol": "pax2a", "matched_alias": None
        }
        # No sidecar → previous names don't resolve and are rejected.
        assert c.get("/api/genes/oct4/resolve").status_code == 404


def test_gene_batch_includes_lightbox_identifier_metadata(tmp_path, monkeypatch):
    records = [
        {
            "image_id": "ZDB-IMAGE-060216-708",
            "image_info": {
                "image_id": "ZDB-IMAGE-060216-708",
                "figure_id": "ZDB-FIG-1",
                "image_preparation": "whole-mount",
            },
            "expression": {
                "est_id": "ZDB-CDNA-040425-55286",
                "est_symbol": "MGC:55286",
                "probe_quality": "1",
            },
            "gene": {
                "gene_id": "ZDB-GENE-040426-2596",
                "gene_symbol": "pacsin2",
                "gene_name": "protein kinase C and casein kinase substrate in neurons 2",
            },
            "developmental_stages": [
                {
                    "stage_name": "Gastrula:50%-epiboly",
                    "begin_hours": "5.25",
                    "end_hours": "5.66",
                }
            ],
            "publication": {
                "publication_id": "ZDB-PUB-040907-1",
                "pubmed_id": "123456",
            },
            "fish": {"fish_name": "wild type"},
            "human_orthologs": [{"human_symbol": "PACSIN2"}],
            "uniprot_ids": ["F1QC13"],
            "anatomical_locations": [
                {"anatomy_id": "ZFA:0001135", "anatomy_name": "neural tube"},
                {"anatomy_name": "unmapped region"},
            ],
        }
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))

    from gene2image.main import app

    with TestClient(app) as c:
        resp = c.post("/api/genes/batch", json={"genes": ["pacsin2"]})

    assert resp.status_code == 200
    image = resp.json()["pacsin2"][0]
    assert image["gene_id"] == "ZDB-GENE-040426-2596"
    assert image["gene_name"] == "protein kinase C and casein kinase substrate in neurons 2"
    assert image["est_id"] == "ZDB-CDNA-040425-55286"
    assert image["est_symbol"] == "MGC:55286"
    # Anatomy terms carry their ZFA ontology id so the lightbox can link to
    # ZFIN; a term without an id still passes through with anatomy_id None.
    assert image["anatomy_terms"] == [
        {"anatomy_name": "neural tube", "anatomy_id": "ZFA:0001135"},
        {"anatomy_name": "unmapped region", "anatomy_id": None},
    ]


def _facets_dataset(tmp_path, monkeypatch):
    """Two genes at disjoint stages/anatomy so union vs. single-gene facets differ."""
    records = [
        {
            "gene": {"gene_symbol": "early"},
            "developmental_stages": [{"begin_hours": "5.25"}],
            "anatomical_locations": [{"anatomy_name": "Hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "early"},
            "developmental_stages": [{"begin_hours": "5.25"}],
            "anatomical_locations": [{"anatomy_name": "Hindbrain"}],
        },
        {
            "gene": {"gene_symbol": "late"},
            "developmental_stages": [{"begin_hours": "42"}],
            "anatomical_locations": [{"anatomy_name": "heart"}],
        },
    ]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    return app


def test_gene_facets_unions_stages_and_anatomy_across_genes(tmp_path, monkeypatch):
    app = _facets_dataset(tmp_path, monkeypatch)

    with TestClient(app) as c:
        resp = c.post("/api/genes/facets", json={"genes": ["early", "late"]})

    assert resp.status_code == 200
    # Union of both genes: each gene's stage/anatomy is reported, with counts.
    # Anatomy names are lowercased ("Hindbrain" -> "hindbrain").
    assert resp.json() == {
        "stages": [
            {"begin_hours": 5.25, "image_count": 2},
            {"begin_hours": 42.0, "image_count": 1},
        ],
        "anatomy": {"hindbrain": 2, "heart": 1},
    }


def test_gene_facets_reflect_only_the_selected_genes(tmp_path, monkeypatch):
    app = _facets_dataset(tmp_path, monkeypatch)

    with TestClient(app) as c:
        resp = c.post("/api/genes/facets", json={"genes": ["early"]})

    # Only the "early" gene's stage/anatomy is present; "late" (42h, heart) is not.
    assert resp.json() == {
        "stages": [{"begin_hours": 5.25, "image_count": 2}],
        "anatomy": {"hindbrain": 2},
    }


def test_gene_facets_ignore_unknown_symbols(tmp_path, monkeypatch):
    app = _facets_dataset(tmp_path, monkeypatch)

    with TestClient(app) as c:
        resp = c.post("/api/genes/facets", json={"genes": ["early", "nosuchgene"]})

    # An unknown symbol contributes nothing rather than erroring.
    assert resp.json() == {
        "stages": [{"begin_hours": 5.25, "image_count": 2}],
        "anatomy": {"hindbrain": 2},
    }


def test_gene_facets_empty_gene_list_returns_empty_facets(tmp_path, monkeypatch):
    app = _facets_dataset(tmp_path, monkeypatch)

    with TestClient(app) as c:
        resp = c.post("/api/genes/facets", json={"genes": []})

    assert resp.json() == {"stages": [], "anatomy": {}}


def test_gene_facets_count_each_gene_once_for_duplicate_symbols(tmp_path, monkeypatch):
    app = _facets_dataset(tmp_path, monkeypatch)

    with TestClient(app) as c:
        resp = c.post("/api/genes/facets", json={"genes": ["early", "early"]})

    # A gene listed twice is not double-counted.
    assert resp.json() == {
        "stages": [{"begin_hours": 5.25, "image_count": 2}],
        "anatomy": {"hindbrain": 2},
    }


def test_batch_rejects_gene_list_over_limit(client):
    # >200 genes must be rejected at validation (422) before the handler runs
    # any per-gene work, so a giant POST fails fast instead of burning CPU (GEN-4).
    resp = client.post("/api/genes/batch", json={"genes": ["g"] * 201})
    assert resp.status_code == 422


def test_batch_accepts_gene_list_at_limit(client):
    # Exactly 200 is allowed (boundary); empty data → every gene maps to [].
    resp = client.post("/api/genes/batch", json={"genes": ["g"] * 200})
    assert resp.status_code == 200


def test_batch_rejects_n_images_out_of_range(client):
    # n_images must be within [1, 10]; 0 and 11 both 422.
    below = client.post("/api/genes/batch", json={"genes": ["g"], "n_images": 0})
    above = client.post("/api/genes/batch", json={"genes": ["g"], "n_images": 11})
    assert below.status_code == 422
    assert above.status_code == 422


def test_batch_accepts_n_images_at_bounds(client):
    lo = client.post("/api/genes/batch", json={"genes": ["g"], "n_images": 1})
    hi = client.post("/api/genes/batch", json={"genes": ["g"], "n_images": 10})
    assert lo.status_code == 200
    assert hi.status_code == 200


def test_giant_batch_post_fails_fast_at_validation(client):
    # A pathologically large gene list is rejected by request validation (422)
    # rather than iterating 50k symbols through the resolve/filter pipeline —
    # the CPU-exhaustion guard for /api/genes/batch (GEN-4).
    resp = client.post("/api/genes/batch", json={"genes": ["g"] * 50000})
    assert resp.status_code == 422


def test_case_insensitive_lookup_resolves_without_linear_scan(tmp_path, monkeypatch):
    # The lowercase index (GEN-4) must resolve a case-mismatched symbol to its
    # canonical casing across all the resolve paths, replacing the removed
    # per-request linear scan over every gene.
    records = [{"gene": {"gene_symbol": "Pax2a", "gene_id": "ZDB-GENE-1"}}]
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        assert c.get("/api/genes/PAX2A/resolve").json() == {
            "symbol": "Pax2a", "matched_alias": None
        }
        batch = c.post("/api/genes/batch", json={"genes": ["pax2A"]}).json()
        assert list(batch.keys()) == ["pax2A"]
        # Unknown symbol still resolves to nothing (empty column), not an error.
        assert c.get("/api/genes/nope/resolve").status_code == 404
