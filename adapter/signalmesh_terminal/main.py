"""SignalMesh Terminal adapter — FastAPI app factory.

A separate process, a separate port, a separate .env (SMT_*). It mounts:
  /api/terminal/*   the read-only terminal contract (see routes.py)
  /                 the built web UI (web/dist), when present

It never imports SignalMesh code and never opens SignalMesh's database. The only thing it
writes is its own forecast journal file (journal.py) on its own volume.
Removing this directory removes the terminal; SignalMesh does not notice.
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .routes import router

log = logging.getLogger("signalmesh_terminal")


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.provider == "fixture" and settings.env == "production":
        raise RuntimeError("SMT_PROVIDER=fixture is forbidden with SMT_ENV=production — a fixture is not a market")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # the terminal's own journal + scorer; reads SignalMesh candles (GET), writes only its own file
        from .routes import start_recorder
        start_recorder()
        yield

    app = FastAPI(title="SignalMesh Terminal (read-only adapter)", version=__version__, lifespan=lifespan,
                  docs_url=None if settings.env == "production" else "/api/terminal/docs",
                  redoc_url=None, openapi_url="/api/terminal/openapi.json")

    from .auth import session_gate

    @app.middleware("http")
    async def security_and_auth(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/terminal/") and path not in ("/api/terminal/health", "/api/terminal/openapi.json", "/api/terminal/docs"):
            # operator bypass for scripts: whoever holds the SignalMesh read key may read the terminal
            opkey = request.headers.get("x-terminal-key", "")
            operator = bool(opkey) and bool(settings.signalmesh_api_key) and hmac.compare_digest(opkey, settings.signalmesh_api_key)
            if operator:
                pass
            elif settings.auth == "token":
                got = request.headers.get("x-terminal-token") or request.cookies.get("smt_token") or ""
                if not settings.access_token or not hmac.compare_digest(got, settings.access_token):
                    return JSONResponse({"detail": "terminal access token required", "auth": "token"}, status_code=401)
            elif settings.auth == "signalmesh":
                verdict = session_gate(request.cookies.get("bb_session", ""))
                if not verdict.ok:
                    return JSONResponse({"detail": "login required", "auth": "signalmesh",
                                         "login_url": settings.login_path, "why": verdict.why}, status_code=401)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                           allow_methods=["GET", "POST"], allow_headers=["*"], allow_credentials=True)

    app.include_router(router)

    dist = (Path(__file__).resolve().parent.parent / settings.web_dist).resolve() if not Path(settings.web_dist).is_absolute() else Path(settings.web_dist)
    index = dist / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index)
    else:
        log.warning("web UI not built (no %s) — API only", index)

        @app.get("/", include_in_schema=False)
        def no_ui():
            return JSONResponse({"terminal": "API only — build the web UI (cd web && npm run build)",
                                 "api": "/api/terminal/health"})

    return app


app = create_app()
