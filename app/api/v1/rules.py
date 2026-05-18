"""Rules API endpoints for triggering rule scanning.

This module provides REST API endpoints for:
- Triggering rule scan manually
- Previewing rule matches (dry run mode)
- Checking rule scan task status

Task: T112, T113, T114
Phase: 5 - Rule Engine Configuration and Scanner
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from celery.result import AsyncResult

from app.schemas.rules import RuleScanRequest, RuleScanResponse
from app.tasks.rule_scan import rule_scan_task
from app.tasks.celery_app import celery_app


router = APIRouter()


@router.post("/rules/scan", response_model=RuleScanResponse)
async def trigger_rule_scan(
    request: RuleScanRequest,
    background_tasks: BackgroundTasks
):
    """Trigger rule scanning and decision case creation.

    This endpoint allows manual triggering of rule scanning with options:
    - rule_ids: Filter specific rules to scan (optional)
    - dry_run: Preview matches without creating cases

    Args:
        request: RuleScanRequest with rule_ids and dry_run parameters
        background_tasks: FastAPI background tasks for async execution

    Returns:
        RuleScanResponse with task ID for tracking

    Example:
        POST /api/v1/rules/scan
        {
            "rule_ids": ["merchant_redeemed_rate_drop"],
            "dry_run": true
        }

        Response:
        {
            "status": "accepted",
            "message": "Rule scan task accepted. Use task_id to check status.",
            "task_id": "abc123..."
        }
    """
    # Trigger Celery task asynchronously
    task = rule_scan_task.delay(
        rule_ids=request.rule_ids,
        dry_run=request.dry_run,
        trigger_agent=not request.dry_run  # Only trigger Agent if not dry_run
    )

    return RuleScanResponse(
        status="accepted",
        message=f"Rule scan task accepted. Use task_id '{task.id}' to check status.",
        task_id=task.id
    )


@router.get("/rules/scan/status/{task_id}")
async def get_rule_scan_status(task_id: str):
    """Get status of a rule scan task.

    Args:
        task_id: Celery task ID from previous rule scan

    Returns:
        Dictionary with task status and result (if completed)

    Example:
        GET /api/v1/rules/scan/status/abc123...

        Response (pending):
        {
            "task_id": "abc123...",
            "status": "PENDING",
            "result": null
        }

        Response (completed):
        {
            "task_id": "abc123...",
            "status": "SUCCESS",
            "result": {
                "merchant_matches": 5,
                "total_matches": 5,
                "decision_cases": [1, 2, 3, 4, 5],
                "dry_run": false,
                "agent_triggered": true
            }
        }
    """
    # Get task result from Celery
    task_result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }

    # Include result if task is completed
    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
        else:
            # Task failed
            response["error"] = str(task_result.result)

    return response


@router.get("/rules")
async def list_rules():
    """List all available rules from configuration.

    Returns:
        List of rule metadata (id, name, entity_type, severity)

    Example:
        GET /api/v1/rules

        Response:
        {
            "rules": [
                {
                    "id": "merchant_redeemed_rate_drop",
                    "name": "Merchant Redeemed Rate Drop",
                    "entity_type": "merchant",
                    "severity": "high",
                    "description": "..."
                },
                ...
            ]
        }
    """
    from pathlib import Path
    from app.rules.yaml_loader import load_rules
    from app.core.config import get_settings

    settings = get_settings()

    # Use configured rules directory (relative path resolved to absolute)
    rules_dir = settings.get_rules_dir()

    try:
        rules = load_rules(rules_dir)

        return {
            "rules": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "description": rule.description,
                    "entity_type": rule.entity_type,
                    "severity": rule.severity,
                    "conditions_count": len(rule.conditions),
                }
                for rule in rules
            ]
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Rules configuration directory not found"
        )