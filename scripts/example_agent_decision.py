"""Example: How to use Agent Decision Service.

This script demonstrates how to use the Agent Decision Service
to generate recommendations for decision cases.

Prerequisites:
1. Database must be running with test data
2. DeepSeek API key must be configured in .env
3. DecisionCase must exist with status='pending'

Usage:
    python scripts/example_agent_decision.py --case-id <id>
"""

import argparse
import logging
from app.core.database import SessionLocal
from app.agents.decision_service import AgentDecisionService
from app.tasks.agent_decision import agent_decision_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Agent Decision Example")
    parser.add_argument("--case-id", type=int, required=True, help="Decision case ID")
    parser.add_argument(
        "--async",
        action="store_true",
        help="Run as Celery task (requires Celery worker running)",
    )
    args = parser.parse_args()

    logger.info(f"Processing decision case {args.case_id}")

    if args.async:
        # Run as Celery async task
        logger.info("Dispatching as Celery task...")
        result = agent_decision_task.delay(args.case_id)
        logger.info(f"Task dispatched: task_id={result.id}")
        logger.info("Check Celery worker logs for task execution result")

    else:
        # Run synchronously (for testing)
        db = SessionLocal()

        try:
            service = AgentDecisionService(db)
            recommendation = service.generate_recommendation(args.case_id)

            if recommendation:
                logger.info("Recommendation generated successfully!")
                logger.info(f"  ID: {recommendation.id}")
                logger.info(f"  Summary: {recommendation.summary}")
                logger.info(f"  Confidence: {recommendation.confidence_score}")
                logger.info(f"  Requires Approval: {recommendation.requires_approval}")
                logger.info(f"  Evidence Items: {len(recommendation.evidence_list)}")
                logger.info(f"  LLM Tokens Used: {recommendation.llm_tokens_used}")
            else:
                logger.error("Failed to generate recommendation")

        finally:
            db.close()


if __name__ == "__main__":
    main()