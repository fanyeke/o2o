"""Approval callback API endpoint.

Task: T083-T084
Phase: 4 - US1 Approval Callback Flow

Endpoint:
- POST /api/v1/approvals/callback: Receive approval callback from Feishu with signature validation
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.config import get_settings
from app.integrations.feishu.signature_validator import create_feishu_validator_dependency
from app.schemas.approvals import ApprovalCallbackRequest, ApprovalCallbackResponse
from app.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)

router = APIRouter()

# Create Feishu signature validation dependency with environment-aware validation
settings = get_settings()
feishu_validator = create_feishu_validator_dependency(
    settings.feishu_verification_token,
    is_production=settings.is_production
)


@router.post(
    "/approvals/callback",
    response_model=ApprovalCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Approval callback endpoint",
    description="Receive approval callback from Feishu with signature validation",
)
async def approval_callback(
    request: Request,
    body: ApprovalCallbackRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(feishu_validator),  # Signature validation
):
    """Process approval callback with Feishu signature validation.

    Args:
        request: FastAPI request object (for signature validation)
        body: Approval callback request body
        db: Database session
        _: Signature validation result (injected via dependency)

    Returns:
        Approval processing result

    Raises:
        HTTPException: 401/403 if signature validation fails, 404 if case not found, 400 if invalid status, 409 if concurrent conflict
    """
    logger.info(
        f"Approval callback received: case_id={body.case_id}, "
        f"action={body.action_type}, operator={body.operator_id}"
    )

    # Handle Feishu challenge verification (first-time setup)
    if body.challenge:
        logger.info(f"Feishu challenge verification: {body.challenge}")
        return ApprovalCallbackResponse(
            status="success",
            message="Challenge verified",
            case_id=None,
            new_status=None,
        )

    try:
        service = ApprovalService(db)
        result = service.process_approval(
            case_id=body.case_id,
            action_type=body.action_type,
            operator_id=body.operator_id,
            operator_name=None,  # Could extract from Feishu API if needed
            comment=body.comment,
        )

        logger.info(
            f"Approval processed successfully: case_id={result['case_id']}, "
            f"new_status={result['new_status']}"
        )

        return ApprovalCallbackResponse(
            status="success",
            message=result["message"],
            case_id=result["case_id"],
            new_status=result["new_status"],
        )

    except ValueError as e:
        logger.error(f"Approval validation error: {e}")

        # Determine error type
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": error_msg,
                        "details": {"case_id": body.case_id},
                    }
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "STATE_TRANSITION_ERROR",
                        "message": error_msg,
                        "details": {
                            "case_id": body.case_id,
                            "action_type": body.action_type,
                        },
                    }
                },
            )

    except IntegrityError as e:
        logger.error(f"Concurrent approval conflict: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONCURRENT_APPROVAL_ERROR",
                    "message": f"案例 {body.case_id} 发生并发审批冲突，状态已被其他操作更新",
                    "details": {
                        "case_id": body.case_id,
                        "operator_id": body.operator_id,
                    },
                }
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error during approval processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"审批处理发生内部错误: {str(e)}",
                    "details": {},
                }
            },
        )