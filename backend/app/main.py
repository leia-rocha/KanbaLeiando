"""Aplicacao FastAPI do KanbaLeiando.

Serve a API sob /api/v1 e os arquivos estaticos do frontend compilado pelo mesmo
dominio. Fallback de SPA apenas para rotas de interface: caminhos desconhecidos
de /api retornam erro JSON, nunca o index.html (secao 16.1).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import AppError, error_body
from app.routes import (
    admin,
    attachments,
    auth,
    boards,
    cards,
    internal,
    meta,
    public,
    sharing,
)
from app.utils.ids import new_request_id

logger = logging.getLogger("kanbaleiando")
logging.basicConfig(level=logging.INFO)

API_PREFIX = "/api/v1"

# Diretorio do frontend compilado (copiado para a imagem final).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="KanbaLeiando API",
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    if settings.cors_origins_list and not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Content-Security-Policy"] = _csp(settings)
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "unknown")
        if exc.status_code >= 500:
            logger.error("app_error code=%s rid=%s", exc.code, rid)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, rid, exc.details),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "unknown")
        logger.exception("unhandled rid=%s", rid)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Ocorreu um erro interno.", rid),
        )

    # Rotas da API
    api = [meta, auth, admin, boards, cards, sharing, public, attachments, internal]
    for module in api:
        app.include_router(module.router, prefix=API_PREFIX)

    _mount_spa(app)
    return app


def _csp(settings) -> str:
    firebase = "https://*.googleapis.com https://*.firebaseio.com https://*.firebaseapp.com"
    return (
        "default-src 'self'; "
        f"connect-src 'self' {firebase} https://*.cloudfunctions.net "
        "https://firestore.googleapis.com https://identitytoolkit.googleapis.com "
        "https://securetoken.googleapis.com https://storage.googleapis.com; "
        "img-src 'self' data: blob: https://storage.googleapis.com; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "frame-src 'self' blob:; object-src 'none'; base-uri 'self'; "
        "form-action 'self'"
    )


def _mount_spa(app: FastAPI) -> None:
    """Serve o SPA se a pasta static existir. Fallback apenas para interface."""
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        return

    assets = _STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> Response:
        # Caminhos de API desconhecidos nao caem no index.html.
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content=error_body("not_found", "Rota de API inexistente.", "unknown"),
            )
        file_path = _STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(index))


app = create_app()
