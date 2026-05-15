from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/datasets", tags=["datasets"])


class ImportResponse(BaseModel):
    status: str
    message: str


@router.post("/import", response_model=ImportResponse)
async def import_datasets():
    from app.tasks.import_dataset import import_dataset_task
    task = import_dataset_task.delay()
    return ImportResponse(
        status="accepted",
        message=f"Import task submitted. Task ID: {task.id}",
    )
