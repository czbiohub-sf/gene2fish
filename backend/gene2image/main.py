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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

frontend_dir = os.environ.get("GENE2IMAGE_FRONTEND_DIR")
if frontend_dir:
    frontend_path = Path(frontend_dir)
    if not frontend_path.exists():
        raise RuntimeError(f"GENE2IMAGE_FRONTEND_DIR does not exist: {frontend_dir}")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
