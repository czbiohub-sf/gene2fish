import json

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
