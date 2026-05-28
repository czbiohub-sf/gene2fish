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


def test_unknown_api_path_returns_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


def test_known_routes_not_shadowed_by_catchall(client):
    assert client.get("/api/health").status_code == 200
    # real route returns 200 (empty data) — never 404 from the catch-all
    assert client.get("/api/stages").status_code != 404
