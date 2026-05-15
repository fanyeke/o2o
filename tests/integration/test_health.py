"""Integration tests for health endpoint."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"
    assert "status" in data
    assert "database" in data
