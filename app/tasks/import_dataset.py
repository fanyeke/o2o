from app.tasks.celery_app import celery_app
from scripts.import_dataset import import_offline_train, import_offline_test


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def import_dataset_task(self):
    try:
        train_rows = import_offline_train()
        test_rows = import_offline_test()
        return {
            "status": "success",
            "train_rows": train_rows,
            "test_rows": test_rows,
        }
    except Exception as exc:
        raise self.retry(exc=exc)
