"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .data_loader import load_data
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data = load_data()
    yield


app = FastAPI(title="gene2image API", lifespan=lifespan)

# The Vite dev server (:5173) calls the API cross-origin during local
# development. Deployed containers serve the built frontend same-origin
# (GENE2IMAGE_FRONTEND_DIR is set in the image), so these localhost origins are
# only needed — and only trusted — when the frontend is NOT mounted. Excluding
# them from deployed environments keeps prod from trusting a localhost page.
_LOCAL_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _cors_allow_origins() -> list[str]:
    if os.environ.get("GENE2IMAGE_FRONTEND_DIR"):
        return []
    return list(_LOCAL_DEV_ORIGINS)


# Deploy targets are wildcard subdomains, which allow_origins (exact match
# only) can't express — Starlette fullmatches this regex against the Origin
# header and echoes back the specific origin. https only; no credentials.
_ALLOWED_ORIGIN_REGEX = (
    r"https://[A-Za-z0-9-]+\."
    r"(apps-staging\.czbiohub\.org"
    r"|apps\.czbiohub\.org"
    r"|dev-biohub\.dev\.czi\.team"
    r"|staging-biohub\.staging\.czi\.team"
    r"|prod-biohub\.prod\.czi\.team)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)

def _maybe_mount_frontend(app: FastAPI) -> None:
    frontend_dir = os.environ.get("GENE2IMAGE_FRONTEND_DIR")
    if not frontend_dir:
        return
    frontend_path = Path(frontend_dir).resolve()
    if not frontend_path.is_dir():
        raise RuntimeError(
            f"GENE2IMAGE_FRONTEND_DIR must be an existing directory: {frontend_dir}"
        )
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


_maybe_mount_frontend(app)
