"""API Token authentication middleware for protected endpoints."""

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional


class APITokenAuth:
    """API Token authentication using header-based token validation."""

    def __init__(self, api_token: str):
        """
        Initialize API Token authentication.

        Args:
            api_token: Expected API token value
        """
        self.api_token = api_token
        self.api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

    async def __call__(self, request: Request) -> Optional[str]:
        """
        Validate API token from request header.

        Args:
            request: FastAPI request object

        Returns:
            Token value if valid

        Raises:
            HTTPException: If token is missing or invalid
        """
        token = await self.api_key_header(request)

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Token required in X-API-Token header",
            )

        if token != self.api_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Token",
            )

        return token


def create_api_token_dependency(api_token: str):
    """
    Create a FastAPI dependency for API token authentication.

    Args:
        api_token: Expected API token value

    Returns:
        Callable dependency for use in FastAPI endpoints
    """
    auth = APITokenAuth(api_token)
    return auth