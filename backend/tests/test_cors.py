import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_data_s3_env(monkeypatch):
    monkeypatch.delenv("GENE2IMAGE_DATA_S3_BUCKET", raising=False)
    monkeypatch.delenv("GENE2IMAGE_DATA_S3_PREFIX", raising=False)
    monkeypatch.delenv("GENE2IMAGE_DATA_S3_REGION", raising=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # CORSMiddleware acts before routing, but the app lifespan still runs on
    # TestClient enter and needs GENE2IMAGE_DATA_DIR. An empty JSON array is the
    # minimal valid dataset (see test_routes.py).
    (tmp_path / "image_metadata.json").write_text("[]")
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    with TestClient(app) as c:
        yield c


ALLOWED_ORIGINS = [
    "https://gene2fish.apps-staging.czbiohub.org",
    "https://gene2fish.apps.czbiohub.org",
    "https://gene2fish.dev-biohub.dev.czi.team",
    "https://gene2fish.staging-biohub.staging.czi.team",
    "https://gene2fish.prod-biohub.prod.czi.team",
    "http://localhost:5173",
]

# Look-alikes that must NOT match: a wrong subdomain, a suffix-attack domain,
# and a plain-http variant of an https-only deploy origin.
DISALLOWED_ORIGINS = [
    "https://evil.example.com",
    "https://gene2fish.apps.czbiohub.org.evil.com",
    "https://evil-apps.czbiohub.org",
    "http://gene2fish.apps.czbiohub.org",
]


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_preflight_echoes_allowed_origin(client, origin):
    resp = client.options(
        "/api/genes/batch",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    # A tightened policy echoes the specific origin back, never the "*" wildcard.
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_preflight_rejects_unknown_origin(client, origin):
    resp = client.options(
        "/api/genes/batch",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") is None


def test_preflight_limits_methods_to_get_post(client):
    resp = client.options(
        "/api/genes/batch",
        headers={
            "Origin": "https://gene2fish.apps.czbiohub.org",
            "Access-Control-Request-Method": "POST",
        },
    )
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods
    assert "POST" in allow_methods
    assert "DELETE" not in allow_methods
    assert "PUT" not in allow_methods
