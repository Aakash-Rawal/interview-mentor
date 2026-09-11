"""Interview Mentor — local web app.

    uvicorn app.main:app --host 127.0.0.1 --port 8765

One FastAPI process serves the HTML pages (Jinja2 + a little vanilla JS) and
the streaming endpoints the pages call. Designed to run as a launchd agent so
it is always available at http://127.0.0.1:8765 without touching a terminal.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import config
from app.routes import api, pages
from app.templating import templates

log = logging.getLogger("interview_mentor")

DB_BOOT_ATTEMPTS = 20      # launchd may start us before Postgres is up
DB_BOOT_DELAY_SEC = 3


def _init_db_with_retry() -> bool:
    from db.models import ensure_user, init_db
    for attempt in range(1, DB_BOOT_ATTEMPTS + 1):
        try:
            init_db()
            ensure_user(config.USER_ID)
            log.info("database ready")
            return True
        except psycopg2.Error as exc:
            log.warning("database not ready (attempt %d/%d): %s",
                        attempt, DB_BOOT_ATTEMPTS, str(exc).strip())
            time.sleep(DB_BOOT_DELAY_SEC)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for problem in config.validate():
        log.warning("config: %s", problem)
    app.state.db_ready = _init_db_with_retry()
    yield
    from db.connection import close_pool
    close_pool()


app = FastAPI(title="Interview Mentor", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")


def _error_page(request: Request, status: int, title: str, message: str, detail: str = ""):
    return templates.TemplateResponse(request, "error.html", {
        "title": title, "message": message, "detail": detail,
        # base.html expects these on every page
        "page": "error", "domain": "pe", "user": {}, "active_mock": None, "db_ready": True,
    }, status_code=status)


@app.exception_handler(psycopg2.Error)
async def db_error(request: Request, exc: psycopg2.Error):
    log.error("database error: %s", exc)
    return _error_page(request, 503, "Database unreachable",
                       "PostgreSQL is not answering. Start it with "
                       "`brew services start postgresql@18` and reload this page.",
                       str(exc).strip())


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return _error_page(request, 404, "Not found", "That page does not exist.")
