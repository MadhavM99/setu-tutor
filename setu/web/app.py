"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.engine import Engine

from setu import __version__

from .db import AppDatabase
from .errors import ApiError, api_error_handler, validation_error_handler
from .routes_auth import router as auth_router


def create_app(*, engine: Engine | None = None, cookie_secure: bool = True) -> FastAPI:
    app = FastAPI(title="setu", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = AppDatabase(engine)
    app.state.cookie_secure = cookie_secure
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    app.include_router(auth_router)
    return app


app = create_app()
