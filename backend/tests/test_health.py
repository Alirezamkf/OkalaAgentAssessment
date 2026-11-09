from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.json() == {"status": "healthy", "service": "backend"}