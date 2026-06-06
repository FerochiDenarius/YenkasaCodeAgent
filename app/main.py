from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.logging import configure_logging
from app.core.orchestrator import YenkasaCodeOrchestrator
from app.middleware import RequestIDMiddleware
from app.routers.agent import router as agent_router
from app.routers.health import router as health_router
from app.services.mongodb_service import MongoDBService


LOGGER = logging.getLogger("yenkasa_code.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.mongodb = MongoDBService(settings)
    app.state.orchestrator = YenkasaCodeOrchestrator(mongodb=app.state.mongodb)
    LOGGER.info("YenkasaCode Agent started environment=%s", settings.environment)
    yield
    await app.state.mongodb.close()
    LOGGER.info("YenkasaCode Agent stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        LOGGER.warning("Request validation failed path=%s errors=%s", request.url.path, exc.errors())
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        LOGGER.exception("Unhandled request error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    app.add_middleware(RequestIDMiddleware)
    app.include_router(health_router)
    app.include_router(agent_router)
    return app


app = create_app()
