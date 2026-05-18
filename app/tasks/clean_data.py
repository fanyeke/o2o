"""Celery task for data cleaning from raw to staging layer."""

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.data_cleaning_service import DataCleaningService


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def clean_data_task(self):
    """Celery task to clean raw data and transform to staging events.

    This task processes data from raw.offline_train and creates:
    - Coupon receipt events in staging.coupon_receipt_event
    - Consumption events in staging.consumption_event

    Returns:
        dict: Summary of processed events
    """
    try:
        with SessionLocal() as session:
            service = DataCleaningService(session)
            result = service.clean_all_data(batch_size=10000)
            return {
                "status": "success",
                "receipt_events": result["receipt_events"],
                "consumption_events": result["consumption_events"],
            }
    except Exception as exc:
        raise self.retry(exc=exc)