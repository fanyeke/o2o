"""Unit tests for API Token authentication middleware."""

import pytest
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.testclient import TestClient
from unittest.mock import Mock

from app.middleware.auth import APITokenAuth, create_api_token_dependency


class TestAPITokenAuth:
    """Unit tests for APITokenAuth class."""

    def test_init_with_valid_token(self):
        """Test initialization with valid API token."""
        auth = APITokenAuth("test-token-123")
        assert auth.api_token == "test-token-123"

    def test_call_with_valid_token(self):
        """Test authentication with valid token in header."""
        app = FastAPI()
        auth = APITokenAuth("test-token-123")

        @app.get("/protected")
        async def protected_endpoint(request: Request):
            token = await auth(request)
            return {"token": token}

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Token": "test-token-123"})
        assert response.status_code == 200
        assert response.json() == {"token": "test-token-123"}

    def test_call_with_missing_token(self):
        """Test authentication fails when token is missing."""
        app = FastAPI()
        auth = APITokenAuth("test-token-123")

        @app.get("/protected")
        async def protected_endpoint(request: Request):
            token = await auth(request)
            return {"token": token}

        client = TestClient(app)
        response = client.get("/protected")
        assert response.status_code == 401
        assert "API Token required" in response.json()["detail"]

    def test_call_with_invalid_token(self):
        """Test authentication fails with invalid token."""
        app = FastAPI()
        auth = APITokenAuth("test-token-123")

        @app.get("/protected")
        async def protected_endpoint(request: Request):
            token = await auth(request)
            return {"token": token}

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Token": "wrong-token"})
        assert response.status_code == 403
        assert "Invalid API Token" in response.json()["detail"]


class TestCreateAPITokenDependency:
    """Unit tests for create_api_token_dependency function."""

    def test_create_dependency_returns_callable(self):
        """Test that dependency factory returns callable."""
        dependency = create_api_token_dependency("test-token")
        assert callable(dependency)

    def test_dependency_integration_with_fastapi(self):
        """Test dependency integration with FastAPI Depends."""
        from fastapi import Depends

        app = FastAPI()
        auth_dependency = create_api_token_dependency("test-token")

        @app.get("/protected")
        async def protected_endpoint(token: str = Depends(auth_dependency)):
            return {"authenticated": True}

        client = TestClient(app)

        # Valid token
        response = client.get("/protected", headers={"X-API-Token": "test-token"})
        assert response.status_code == 200
        assert response.json() == {"authenticated": True}

        # Missing token
        response = client.get("/protected")
        assert response.status_code == 401

        # Invalid token
        response = client.get("/protected", headers={"X-API-Token": "wrong"})
        assert response.status_code == 403