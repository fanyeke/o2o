"""Celery task for agent decision generation."""

import logging
from celery import shared_task
from app.core.database import SessionLocal
from app.agents.decision_service import generate_recommendation

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.agent_decision.agent_decision_task",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def agent_decision_task(self, case_id: int):
    """Celery task to generate agent decision for a case.

    Args:
        self: Celery task instance
        case_id: DecisionCase ID to process

    Returns:
        Recommendation ID if successful, None if failed
    """
    logger.info(f"Starting agent_decision_task for case {case_id}")

    db = SessionLocal()

    try:
        recommendation = generate_recommendation(db, case_id)

        if recommendation:
            logger.info(
                f"Agent decision task completed successfully for case {case_id}, "
                f"recommendation_id={recommendation.id}"
            )
            return recommendation.id
        else:
            logger.error(f"Agent decision task failed for case {case_id}")
            return None

    except Exception as e:
        logger.error(f"Agent decision task error for case {case_id}: {e}")

        # Retry task if not max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying agent_decision_task (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)

        return None

    finally:
        db.close()


@shared_task(name="app.tasks.agent_decision.batch_decision_task")
def batch_decision_task(case_ids: list):
    """Process multiple decision cases in batch.

    Args:
        case_ids: List of DecisionCase IDs to process

    Returns:
        List of recommendation IDs
    """
    logger.info(f"Starting batch_decision_task for {len(case_ids)} cases")

    results = []

    for case_id in case_ids:
        # Trigger individual task for each case
        recommendation_id = agent_decision_task.delay(case_id)
        results.append(recommendation_id)

    logger.info(f"Batch decision task initiated {len(results)} individual tasks")

    return results