"""Celery task for rule scanning and decision case creation.

This task integrates:
- Loading rules from YAML files
- Scanning entity metrics against rules
- Creating DecisionCases for matching entities
- Optionally triggering Agent diagnosis

Task: T109, T110, T111
Phase: 5 - Rule Engine Configuration and Scanner
"""

from pathlib import Path
from typing import Dict, Any, Optional, List

from celery import shared_task

from app.tasks.celery_app import celery_app
from app.rules.yaml_loader import load_rules
from app.rules.scanner import scan_all_rules
from app.core.database import SessionLocal
from app.core.config import get_settings


settings = get_settings()


@celery_app.task(bind=True, max_retries=3)
def rule_scan_task(
    self,
    rule_ids: Optional[List[str]] = None,
    dry_run: bool = False,
    trigger_agent: bool = True
) -> Dict[str, Any]:
    """Execute rule scanning and create decision cases.

    This task:
    1. Loads rule configurations from YAML files
    2. Scans entity metrics against rule conditions
    3. Creates DecisionCases for matching entities
    4. Optionally triggers Agent diagnosis for each case

    Args:
        self: Celery task instance
        rule_ids: Optional list of specific rule IDs to scan.
                  If None, scans all rules.
        dry_run: If True, returns preview without creating cases.
                 Useful for testing rule impact.
        trigger_agent: If True, triggers Agent diagnosis for each created case.
                       Only applicable when dry_run=False.

    Returns:
        Dictionary containing:
        - status: Task execution status
        - merchant_matches: Count of merchant matches
        - user_matches: Count of user matches (placeholder)
        - coupon_matches: Count of coupon matches (placeholder)
        - total_matches: Total count of matches
        - decision_cases: List of created DecisionCase IDs (if not dry_run)
        - agent_triggered: Whether Agent diagnosis was triggered

    Raises:
        Exception: On failure, retries up to 3 times with 60-second countdown
    """
    try:
        # Load rules from YAML files using configured directory
        rules_dir = settings.get_rules_dir()

        rules = load_rules(rules_dir, rule_ids)

        if not rules:
            return {
                "status": "no_rules",
                "message": "No rules loaded from directory",
                "merchant_matches": 0,
                "user_matches": 0,
                "coupon_matches": 0,
                "total_matches": 0,
                "decision_cases": [],
                "agent_triggered": False,
                "dry_run": dry_run,
            }

        # Use database session with automatic cleanup
        with SessionLocal() as session:
            # Scan all rules against entity metrics
            scan_result = scan_all_rules(session, rules, dry_run)

            result = {
                "status": "success",
                "merchant_matches": len(scan_result["merchant_matches"]),
                "user_matches": len(scan_result["user_matches"]),
                "coupon_matches": len(scan_result["coupon_matches"]),
                "total_matches": scan_result["total_matches"],
                "decision_cases": [
                    case.id for case in scan_result["decision_cases"]
                ],
                "dry_run": dry_run,
                "agent_triggered": False,
            }

            # Trigger Agent diagnosis if not dry_run and trigger_agent=True
            if not dry_run and trigger_agent and scan_result["decision_cases"]:
                # Import Agent decision task (avoid circular import)
                from app.tasks.agent_decision import agent_decision_task

                # Trigger Agent for each case
                for case in scan_result["decision_cases"]:
                    agent_decision_task.delay(case.id)

                result["agent_triggered"] = True

        return result

    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)