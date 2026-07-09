"""FastAPI application entrypoint (app factory + router includes)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.db import init_db
from app.routers import admin, api, game
from app.templating import templates
from app.utils.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("scissors")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    logger.info("scissors startup complete")
    yield
    stop_scheduler()


# NOTE: no root_path= here - see app/templating.py for why.
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="session",
    max_age=settings.SESSION_COOKIE_MAX_AGE,
    same_site="lax",
    https_only=settings.SESSION_COOKIE_SECURE,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(game.router, tags=["game"])
app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render an HTML error page for browser-facing errors, JSON otherwise."""
    if exc.status_code in (403, 404, 500):
        message = exc.detail if isinstance(exc.detail, str) else "An error occurred"
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error_code": exc.status_code, "message": message},
            status_code=exc.status_code,
            headers=exc.headers,
        )
    detail = exc.detail if isinstance(exc.detail, str) else "Error"
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"error_code": 500, "message": "Internal server error"},
        status_code=500,
    )
