from app.tasks.celery_app import celery_app


@celery_app.task(bind=True)
def refresh_all_features(self):
    print("Feature refresh task executed (placeholder).")
    return {"status": "placeholder", "message": "Not yet implemented."}
