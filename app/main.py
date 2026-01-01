import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.responses import RedirectResponse

from app.api.routes import router
from app.config import load_settings
from app.storage.db import migrate
from app.utils.session import get_session
from app.utils.logging_config import configure_logging
from app.utils.paths import ensure_dirs


def create_app() -> FastAPI:
    settings = load_settings()
    ensure_dirs([settings.db_dir, settings.files_dir, settings.logs_dir])
    configure_logging(settings.logs_dir)
    logging.getLogger("app").info("starting application")
    migrate(settings.db_path)

    app = FastAPI()

    @app.middleware("http")
    async def session_guard_middleware(request: Request, call_next):
        if request.url.path.endswith("/static/manage.html"):
            token = request.cookies.get("session_id")
            if not get_session(token):
                return Response(status_code=403)
        return await call_next(request)

    @app.get("/")
    def index_redirect():
        return RedirectResponse(url="/static/index.html")

    app.include_router(router)
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()
