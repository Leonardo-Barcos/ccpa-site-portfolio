"""Application entry point — CCPA site and membership."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import settings
from .database import init_db
from .paths import STATIC_DIR
from .routers import admin, membership, site, webhooks
from .routers.admin import LoginRequired

logging.basicConfig(
    level=logging.INFO if settings.is_prod else logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CCPA — site e associados",
    # The interactive API docs are a development convenience, not something to
    # expose on a public site.
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(site.router)
app.include_router(membership.router)
app.include_router(admin.router)
app.include_router(webhooks.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; "
        "connect-src 'self' https://viacep.com.br; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.is_prod:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(LoginRequired)
async def redirect_to_login(request: Request, exc):  # noqa: ARG001
    return RedirectResponse("/admin/entrar", status_code=303)


@app.exception_handler(404)
async def not_found(request: Request, exc):  # noqa: ARG001
    """Branded 404 for the site, plain JSON for API callers."""
    from .templating import templates

    if request.url.path.startswith(("/webhooks", "/healthz")):
        return JSONResponse({"detail": "not found"}, status_code=404)
    return templates.TemplateResponse(
        request, "site/404.html", {"request": request}, status_code=404
    )


@app.get("/healthz", include_in_schema=False)
def healthz():
    return JSONResponse({"status": "ok"})
