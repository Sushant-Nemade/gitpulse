import os
import secrets
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from gitpulse.core import Store
from gitpulse.github import GitHubClient


def create_app(store: Store, api_token: str, github_token: str = "", origins: tuple[str, ...] = ()) -> FastAPI:
    if len(api_token) < 32:
        raise ValueError("Configure an API_TOKEN with at least 32 characters locally")
    app = FastAPI(title="GitPulse", docs_url=None, redoc_url=None, openapi_url=None)
    sync_lock = Lock()
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=list(origins), allow_methods=["GET", "POST"], allow_headers=["Authorization"]
        )

    def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
        if not authorization or not secrets.compare_digest(authorization.encode(), f"Bearer {api_token}".encode()):
            raise HTTPException(status_code=401, detail="Authentication required")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/state", dependencies=[Depends(authorize)])
    def state() -> dict[str, Any]:
        return store.report()

    @app.post("/api/sync", dependencies=[Depends(authorize)])
    def sync() -> dict[str, Any]:
        if not sync_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Sync already running")
        client: GitHubClient | None = None
        try:
            client = GitHubClient(store.username, github_token)
            return store.sync(client)
        except Exception:
            raise HTTPException(status_code=502, detail="Sync failed; previous snapshot preserved") from None
        finally:
            try:
                if client is not None:
                    client.close()
            finally:
                sync_lock.release()

    frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="dashboard")
    return app


def application() -> FastAPI:
    return create_app(
        Store(Path(os.getenv("DATABASE_PATH", "data/gitpulse.sqlite")), os.getenv("GITHUB_USERNAME", "Sushant-Nemade")),
        os.getenv("API_TOKEN", ""),
        os.getenv("GITHUB_TOKEN", ""),
        tuple(filter(None, os.getenv("CORS_ORIGINS", "").split(","))),
    )
