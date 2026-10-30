"""FastAPI application factory."""
from fastapi import FastAPI

from setu import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="setu", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
