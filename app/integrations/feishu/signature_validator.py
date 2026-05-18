"""Feishu signature validation for webhook callbacks.

Implements signature verification according to Feishu Bot webhook security requirements.
"""

import hashlib
import logging
import time
from typing import Optional
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


class FeishuSignatureValidator:
    """Validate Feishu webhook request signatures."""

    def __init__(
        self,
        verification_token: str,
        max_timestamp_diff: int = 300,
        is_production: bool = False
    ):
        """
        Initialize Feishu signature validator.

        Args:
            verification_token: Feishu verification token from app config
            max_timestamp_diff: Maximum allowed timestamp difference in seconds (default: 5 minutes)
            is_production: If True, enforces strict validation. If False (dev mode),
                         allows skipping validation when token is not configured.
        """
        self.verification_token = verification_token
        self.max_timestamp_diff = max_timestamp_diff
        self.is_production = is_production

    async def validate_request(self, request: Request) -> bool:
        """
        Validate Feishu webhook request signature.

        Args:
            request: FastAPI request object

        Returns:
            True if signature is valid

        Raises:
            HTTPException: If signature validation fails
        """
        # Check if verification token is configured
        if not self.verification_token:
            if self.is_production:
                # CRITICAL: In production, missing token means misconfiguration
                logger.error(
                    "Feishu verification token not configured in production environment. "
                    "This is a security risk. Set FEISHU_VERIFICATION_TOKEN environment variable."
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": {
                            "code": "MISCONFIGURED_WEBHOOK",
                            "message": "Webhook validation is misconfigured. Contact administrator.",
                            "details": {}
                        }
                    }
                )
            else:
                # In development mode, allow skipping validation
                logger.warning(
                    "Feishu verification token not configured. "
                    "Skipping signature validation (development mode only)."
                )
                return True

        # Get headers
        timestamp = request.headers.get("X-Lark-Timestamp")
        nonce = request.headers.get("X-Lark-Nonce")
        signature = request.headers.get("X-Lark-Signature")

        if not all([timestamp, nonce, signature]):
            logger.error("Missing required Feishu signature headers")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "MISSING_SIGNATURE_HEADERS",
                        "message": "Feishu webhook request missing required signature headers",
                        "details": {
                            "required_headers": ["X-Lark-Timestamp", "X-Lark-Nonce", "X-Lark-Signature"]
                        }
                    }
                }
            )

        # Validate timestamp to prevent replay attacks
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            time_diff = abs(current_time - request_time)

            if time_diff > self.max_timestamp_diff:
                logger.error(f"Feishu request timestamp too old: {time_diff}s")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": {
                            "code": "TIMESTAMP_EXPIRED",
                            "message": f"Request timestamp expired (difference: {time_diff}s)",
                            "details": {
                                "timestamp": timestamp,
                                "current_time": current_time,
                                "max_diff": self.max_timestamp_diff
                            }
                        }
                    }
                )
        except ValueError:
            logger.error(f"Invalid timestamp format: {timestamp}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_TIMESTAMP",
                        "message": "Invalid timestamp format in header",
                        "details": {"timestamp": timestamp}
                    }
                }
            )

        # Read request body for signature calculation
        body = await request.body()
        body_str = body.decode("utf-8")

        # Calculate expected signature
        # Feishu signature algorithm: SHA256(timestamp + nonce + verification_token + body)
        sign_data = f"{timestamp}{nonce}{self.verification_token}{body_str}"
        expected_signature = hashlib.sha256(sign_data.encode("utf-8")).hexdigest()

        # Compare signatures
        if signature != expected_signature:
            logger.error(
                f"Feishu signature mismatch: expected={expected_signature}, actual={signature}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "SIGNATURE_MISMATCH",
                        "message": "Feishu webhook signature validation failed",
                        "details": {}
                    }
                }
            )

        logger.info("Feishu signature validation successful")
        return True


def create_feishu_validator_dependency(
    verification_token: str,
    is_production: bool = False
):
    """
    Create a FastAPI dependency for Feishu signature validation.

    Args:
        verification_token: Feishu verification token from config
        is_production: If True, enforces strict validation. If False (dev mode),
                     allows skipping validation when token is not configured.

    Returns:
        Callable validator for use in FastAPI endpoints
    """
    validator = FeishuSignatureValidator(
        verification_token,
        is_production=is_production
    )

    async def validate_dependency(request: Request) -> bool:
        return await validator.validate_request(request)

    return validate_dependency