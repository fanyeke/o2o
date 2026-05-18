from fastapi import FastAPI, Depends
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.middleware.auth import create_api_token_dependency
from app.api.v1.health import router as health_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.cases import router as cases_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.rules import router as rules_router

setup_logging()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Create authentication dependency for protected routes
api_token_auth = create_api_token_dependency(settings.api_token)

# Health check endpoint - no authentication required
app.include_router(health_router, prefix="/api/v1", tags=["health"])

# Feishu approval callback - requires only Feishu signature validation (not API Token)
app.include_router(
    approvals_router,
    prefix="/api/v1",
    tags=["approvals"],
)

# Protected endpoints - require API Token authentication
app.include_router(
    datasets_router,
    prefix="/api/v1",
    tags=["datasets"],
    dependencies=[Depends(api_token_auth)]
)
app.include_router(
    metrics_router,
    prefix="/api/v1/metrics",
    tags=["metrics"],
    dependencies=[Depends(api_token_auth)]
)
app.include_router(
    cases_router,
    prefix="/api/v1",
    tags=["cases"],
    dependencies=[Depends(api_token_auth)]
)
app.include_router(
    rules_router,
    prefix="/api/v1",
    tags=["rules"],
    dependencies=[Depends(api_token_auth)]
)
