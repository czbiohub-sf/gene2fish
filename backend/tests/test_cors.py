import pytest
from fastapi.testclient import TestClient


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


def test_local_dev_origins_dropped_when_frontend_mounted(monkeypatch):
    # Deployed containers set GENE2IMAGE_FRONTEND_DIR and serve the frontend
    # same-origin, so the localhost dev origins must not be trusted there. Local
    # dev (no mounted frontend) still allows the Vite dev-server origins.
    from gene2image import main

    monkeypatch.setenv("GENE2IMAGE_FRONTEND_DIR", "/app/frontend/dist")
    assert main._cors_allow_origins() == []

    monkeypatch.delenv("GENE2IMAGE_FRONTEND_DIR", raising=False)
    assert "http://localhost:5173" in main._cors_allow_origins()


def test_preflight_rejects_localhost_when_frontend_mounted(tmp_path, monkeypatch):
    # End-to-end: with a deploy-like config (frontend mounted same-origin) the
    # CORS middleware rejects the localhost dev origin while still echoing a
    # deployed origin. Reloads the module so the import-time middleware wiring
    # picks up the env, and restores it afterward for other tests.
    import importlib

    (tmp_path / "image_metadata.json").write_text("[]")
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>")
    monkeypatch.setenv("GENE2IMAGE_FRONTEND_DIR", str(dist))

    from gene2image import main as main_module

    importlib.reload(main_module)
    try:
        with TestClient(main_module.app) as c:
            deployed = c.options(
                "/api/genes/batch",
                headers={
                    "Origin": "https://gene2fish.apps.czbiohub.org",
                    "Access-Control-Request-Method": "POST",
                },
            )
            local = c.options(
                "/api/genes/batch",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
        assert (
            deployed.headers.get("access-control-allow-origin")
            == "https://gene2fish.apps.czbiohub.org"
        )
        assert local.headers.get("access-control-allow-origin") is None
    finally:
        # Restore the default (unmounted) module state for subsequent tests.
        monkeypatch.delenv("GENE2IMAGE_FRONTEND_DIR", raising=False)
        importlib.reload(main_module)


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
