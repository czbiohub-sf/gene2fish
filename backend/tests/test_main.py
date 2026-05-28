import pytest
from fastapi import FastAPI

from gene2image.main import _maybe_mount_frontend


def test_no_env_var_mounts_nothing(monkeypatch):
    monkeypatch.delenv("GENE2IMAGE_FRONTEND_DIR", raising=False)
    app = FastAPI()
    _maybe_mount_frontend(app)
    assert not any(r.name == "frontend" for r in app.routes)


def test_valid_dir_mounts_static(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html/>")
    monkeypatch.setenv("GENE2IMAGE_FRONTEND_DIR", str(tmp_path))
    app = FastAPI()
    _maybe_mount_frontend(app)
    assert any(r.name == "frontend" for r in app.routes)


def test_nonexistent_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GENE2IMAGE_FRONTEND_DIR", str(tmp_path / "nope"))
    app = FastAPI()
    with pytest.raises(RuntimeError, match="must be an existing directory"):
        _maybe_mount_frontend(app)
