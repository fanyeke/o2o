from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    db_status = "unhealthy"
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "version": get_settings().app_version,
        "database": db_status,
    }
