"""FastAPI application factory."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape
from sqlalchemy.engine import Engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from setu import __version__

from .db import AppDatabase
from .errors import ApiError, api_error_handler, body, validation_error_handler
from .i18n import Catalog
from .routes_auth import router as auth_router
from .routes_learn import router as learn_router
from .routes_rules import router as rules_router
from .routes_ui import router as ui_router

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _templates(catalog: Catalog) -> Environment:
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      undefined=StrictUndefined)
    env.globals.update(
        t=catalog.get,
        num=catalog.number,
        # Telugu always sits in an element marked lang="te" (screen readers, fonts).
        te=lambda s: Markup('<span lang="te">') + escape(s) + Markup("</span>"),
    )
    return env


class _LazyWriter:
    """The OutcomeWriter, built on first use. It reads its own credentials; with none set (development and tests)
    it uses the app's engine and switches to setu_writer per transaction."""

    def __init__(self, db):
        self._db, self._writer = db, None

    def __getattr__(self, name):
        if self._writer is None:
            from setu.store.outcome_writer import OutcomeWriter

            self._writer = OutcomeWriter.from_environment(fallback=self._db.engine)
        return getattr(self._writer, name)


def create_app(*, engine: Engine | None = None, cookie_secure: bool = True) -> FastAPI:
    app = FastAPI(title="setu", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = AppDatabase(engine)
    app.state.writer = _LazyWriter(app.state.db)
    app.state.cookie_secure = cookie_secure
    app.state.catalog = Catalog.load(ROOT / "locale/hi.yaml", pending_file=ROOT / "locale/pending.txt")
    app.state.templates = _templates(app.state.catalog)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def not_found(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
            html = app.state.templates.get_template("learner/message.html").render(
                title_key="page.not_found", message_key="err.not_found", user=None)
            return HTMLResponse(html, status_code=404)
        return JSONResponse(body("not_found" if exc.status_code == 404 else "generic"), status_code=exc.status_code)

    app.add_exception_handler(StarletteHTTPException, not_found)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(auth_router, prefix="/api")  # JSON API; the Hindi pages live at the root
    app.include_router(ui_router)
    app.include_router(rules_router)  # before /learn/{name}
    app.include_router(learn_router)
    return app


app = create_app()
