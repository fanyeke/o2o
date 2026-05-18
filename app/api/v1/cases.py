"""Decision cases API router.

Task: T093-T096
Phase: 4 - DecisionCase Query APIs
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.domain.application.action_execution import ActionExecution
from app.schemas.cases import (
    DecisionCaseListResponse,
    DecisionCaseDetailResponse,
    DecisionCaseResponse,
    RecommendationResponse,
    EvidenceItem,
    SuggestedAction,
    ApprovalLogItem,
    ActionExecutionItem,
)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/", response_model=DecisionCaseListResponse)
async def list_cases(
    status: Optional[str] = Query(None, description="Filter by status"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    case_type: Optional[str] = Query(None, description="Filter by case type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(20, ge=1, le=1000, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """List decision cases with optional filters and pagination.

    Args:
        status: Filter by case status
        merchant_id: Filter by merchant ID
        case_type: Filter by case type
        start_date: Filter cases created after this date
        end_date: Filter cases created before this date
        limit: Maximum number of results to return
        offset: Number of results to skip
        db: Database session

    Returns:
        List of decision cases with pagination metadata

    Raises:
        HTTPException: If invalid filter parameters provided
    """
    # Validate status if provided
    valid_statuses = [
        "pending",
        "recommended",
        "approved",
        "rejected",
        "executed",
        "completed",
        "failed",
    ]
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    # Validate case_type if provided
    valid_case_types = ["商户异常", "券策略复核", "用户召回"]
    if case_type and case_type not in valid_case_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case_type. Must be one of: {valid_case_types}",
        )

    # Build query with filters
    query = db.query(DecisionCase)

    if status:
        query = query.filter(DecisionCase.status == status)

    if merchant_id:
        query = query.filter(DecisionCase.merchant_id == merchant_id)

    if case_type:
        query = query.filter(DecisionCase.case_type == case_type)

    if start_date:
        query = query.filter(DecisionCase.created_at >= start_date)

    if end_date:
        query = query.filter(DecisionCase.created_at <= end_date)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    cases = query.order_by(DecisionCase.created_at.desc()).offset(offset).limit(limit).all()

    # Convert to response format
    case_responses = [
        DecisionCaseResponse(
            id=case.id,
            case_type=case.case_type,
            severity_level=case.severity_level,
            merchant_id=case.merchant_id,
            trigger_rule_id=case.trigger_rule_id,
            status=case.status,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )
        for case in cases
    ]

    return DecisionCaseListResponse(
        total=total,
        limit=limit,
        offset=offset,
        data=case_responses,
    )


@router.get("/{case_id}", response_model=DecisionCaseDetailResponse)
async def get_case_detail(
    case_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific decision case.

    Args:
        case_id: ID of the decision case
        db: Database session

    Returns:
        Detailed case information including recommendation, approval logs, and action executions

    Raises:
        HTTPException: If case not found
    """
    # Query case with related data
    case = (
        db.query(DecisionCase)
        .filter(DecisionCase.id == case_id)
        .first()
    )

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get recommendation (latest one)
    recommendation_response = None
    recommendations = db.query(Recommendation).filter(Recommendation.case_id == case_id).order_by(Recommendation.created_at.desc()).all()
    if recommendations:
        latest_recommendation = recommendations[0]
        recommendation_response = RecommendationResponse(
            id=latest_recommendation.id,
            summary=latest_recommendation.summary,
            evidence_list=[
                EvidenceItem(
                    type=evidence.get("type", ""),
                    content=evidence.get("content", ""),
                )
                for evidence in latest_recommendation.evidence_list
            ],
            suggested_actions=[
                SuggestedAction(
                    action_type=action.get("action_type", ""),
                    params=action.get("params", {}),
                    risk_level=action.get("risk_level", ""),
                )
                for action in latest_recommendation.suggested_actions
            ],
            risk_alerts=latest_recommendation.risk_alerts,
            confidence_score=latest_recommendation.confidence_score,
            requires_approval=latest_recommendation.requires_approval,
            created_at=latest_recommendation.created_at,
        )

    # Get approval logs
    approval_logs = db.query(ApprovalLog).filter(ApprovalLog.case_id == case_id).order_by(ApprovalLog.created_at.asc()).all()
    approval_log_responses = [
        ApprovalLogItem(
            operator_name=log.operator_name,
            action=log.action,
            comment=log.comment,
            created_at=log.created_at,
        )
        for log in approval_logs
    ]

    # Get action executions
    action_executions = db.query(ActionExecution).filter(ActionExecution.case_id == case_id).order_by(ActionExecution.executed_at.asc()).all()
    action_execution_responses = [
        ActionExecutionItem(
            action_type=execution.action_type,
            execution_status=execution.execution_status,
            executed_at=execution.executed_at,
        )
        for execution in action_executions
    ]

    return DecisionCaseDetailResponse(
        id=case.id,
        case_type=case.case_type,
        severity_level=case.severity_level,
        merchant_id=case.merchant_id,
        trigger_rule_id=case.trigger_rule_id,
        trigger_metrics_snapshot=case.trigger_metrics_snapshot,
        status=case.status,
        recommendation=recommendation_response,
        approval_logs=approval_log_responses,
        action_executions=action_execution_responses,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )