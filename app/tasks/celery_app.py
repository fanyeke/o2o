from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "coupon_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.import_dataset",
        "app.tasks.refresh_features",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule_filename="/tmp/celerybeat-schedule",
    beat_schedule={
        "refresh-features-daily": {
            "task": "app.tasks.refresh_features.refresh_all_features",
            "schedule": 86400.0,
            "options": {"queue": "default"},
        },
    },
)
