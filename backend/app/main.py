"""GuardX backend — FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "GuardX backend starting | env=%s version=%s",
        settings.app_env,
        settings.app_version,
    )
    yield
    logger.info("GuardX backend shutting down")


app = FastAPI(
    title="GuardX",
    description="AI Autonomous Security Agent — incident detection & response",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS: dashboard origin(s) only.
origins = [settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level liveness probe (load balancers / compose healthchecks).
app.include_router(health.router)
# Versioned API.
app.include_router(api_router)
