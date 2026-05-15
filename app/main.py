from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.v1.health import router as health_router
from app.api.v1.datasets import router as datasets_router

setup_logging()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(datasets_router, prefix="/api/v1", tags=["datasets"])
