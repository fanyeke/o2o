"""Feishu Message Client for sending and updating approval cards.

M6 Milestone: Feishu Closed-loop Integration

This module provides async client for:
- Sending approval cards to Feishu
- Updating card status after approval/rejection
- Retry mechanism for network failures
"""

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from app.integrations.feishu.card_builder import FeishuCardBuilder

logger = logging.getLogger(__name__)


class FeishuMessageClient:
    """Async client for Feishu Bot messaging.

    Handles:
    - Token refresh for API authentication
    - Card sending with retry mechanism
    - Card updates for status changes
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        webhook_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """Initialize Feishu message client.

        Args:
            app_id: Feishu app ID
            app_secret: Feishu app secret
            webhook_url: Optional webhook URL for sending messages
            max_retries: Maximum retry attempts for failed requests (>= 3)
            retry_delay: Base delay between retries in seconds
            timeout: Request timeout in seconds
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self.max_retries = max(3, max_retries)  # Ensure at least 3 retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.card_builder = FeishuCardBuilder()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _get_access_token(self) -> str:
        """Get or refresh Feishu access token.

        Returns:
            Valid access token

        Raises:
            ValueError: If token acquisition fails
        """
        # Check if current token is still valid
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # Request new token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    token_url,
                    json={
                        "app_id": self.app_id,
                        "app_secret": self.app_secret,
                    },
                )

                if response.status_code != 200:
                    raise ValueError(f"Token request failed: {response.status_code}")

                data = response.json()
                if data.get("code") != 0:
                    raise ValueError(f"Token error: {data.get('msg', 'unknown')}")

                self._access_token = data["app_access_token"]
                # Token expires in 2 hours, refresh 10 minutes early
                self._token_expires_at = time.time() + 7000

                logger.info("Feishu access token refreshed successfully")
                return self._access_token

            except Exception as e:
                logger.error(f"Failed to get Feishu access token: {e}")
                raise ValueError(f"Token acquisition failed: {e}")

    async def _send_with_retry(
        self,
        url: str,
        method: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Send request with retry mechanism.

        Args:
            url: Request URL
            method: HTTP method (POST/PUT)
            payload: Request body
            headers: Optional headers

        Returns:
            Response data

        Raises:
            ValueError: If all retries fail
        """
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method == "POST":
                        response = await client.post(url, json=payload, headers=default_headers)
                    elif method == "PUT":
                        response = await client.put(url, json=payload, headers=default_headers)
                    else:
                        raise ValueError(f"Unsupported method: {method}")

                    if response.status_code >= 500:
                        raise Exception(f"Server error: {response.status_code}")

                    data = response.json()

                    if data.get("code") == 0:
                        return {
                            "success": True,
                            "data": data.get("data", {}),
                        }

                    # Non-zero code means Feishu API error
                    if data.get("code") in [99991400, 99991401]:
                        # Token expired, refresh and retry
                        await self._get_access_token()
                        continue

                    raise Exception(f"Feishu API error: {data.get('msg', 'unknown')}")

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Feishu request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        logger.error(f"All {self.max_retries} retries failed: {last_error}")
        raise ValueError(f"Request failed after {self.max_retries} retries: {last_error}")

    async def send_approval_card(
        self,
        case_data: dict[str, Any],
        recommendation: dict[str, Any],
        receive_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send approval card to Feishu.

        Args:
            case_data: Decision case data
            recommendation: Recommendation data
            receive_id: Optional receiver ID (user/group)

        Returns:
            Result with success status and message_id

        Raises:
            ValueError: If sending fails or configuration missing
        """
        # Check configuration (fail closed in production)
        if not self.webhook_url and not receive_id:
            raise ValueError("Webhook URL or receive_id required for sending card")

        # Build card
        card = self.card_builder.build_approval_card(case_data, recommendation)

        if self.webhook_url:
            # Send via webhook
            result = await self._send_with_retry(
                url=self.webhook_url,
                method="POST",
                payload={"msg_type": "interactive", "card": card["card"]},
            )
        else:
            # Send via API with access token
            token = await self._get_access_token()
            message_url = "https://open.feishu.cn/open-apis/im/v1/messages"

            result = await self._send_with_retry(
                url=message_url,
                method="POST",
                payload={
                    "receive_id": receive_id,
                    "msg_type": "interactive",
                    "content": card,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        message_id = result.get("data", {}).get("message_id")

        logger.info(f"Approval card sent successfully: message_id={message_id}")

        return {
            "success": True,
            "message_id": message_id,
        }

    async def update_card_status(
        self,
        message_id: str,
        case_id: int,
        new_status: str,
        operator_name: str,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update card status after approval/rejection.

        Args:
            message_id: Feishu message ID to update
            case_id: Decision case ID
            new_status: New case status
            operator_name: Operator who performed the action
            comment: Optional comment

        Returns:
            Result with success status

        Raises:
            ValueError: If update fails
        """
        # Build status update card
        card = self.card_builder.build_status_update_card(
            case_id=case_id,
            new_status=new_status,
            operator_name=operator_name,
            comment=comment,
        )

        # Get access token for API call
        token = await self._get_access_token()
        update_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"

        result = await self._send_with_retry(
            url=update_url,
            method="PUT",
            payload={
                "msg_type": "interactive",
                "content": card,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        logger.info(f"Card status updated: message_id={message_id}, status={new_status}")

        return {
            "success": True,
            "message_id": message_id,
        }

    async def send_message(
        self,
        content: str,
        receive_id: str,
        msg_type: str = "text",
    ) -> dict[str, Any]:
        """Send a simple text message.

        Args:
            content: Message content
            receive_id: Receiver ID
            msg_type: Message type (text/interactive)

        Returns:
            Result with success status and message_id
        """
        token = await self._get_access_token()
        message_url = "https://open.feishu.cn/open-apis/im/v1/messages"

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": {"text": content} if msg_type == "text" else content,
        }

        result = await self._send_with_retry(
            url=message_url,
            method="POST",
            payload=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

        return {
            "success": True,
            "message_id": result.get("data", {}).get("message_id"),
        }


def create_message_client_from_config() -> FeishuMessageClient:
    """Create FeishuMessageClient from app configuration.

    Returns:
        Configured FeishuMessageClient instance

    Raises:
        ValueError: If required configuration is missing
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        if settings.is_production:
            raise ValueError(
                "Feishu configuration required in production. "
                "Set FEISHU_APP_ID and FEISHU_APP_SECRET environment variables."
            )
        else:
            logger.warning("Feishu configuration not set. Using placeholder values.")

    return FeishuMessageClient(
        app_id=settings.feishu_app_id or "",
        app_secret=settings.feishu_app_secret or "",
        webhook_url=None,  # Configure via environment if needed
        max_retries=3,
    )