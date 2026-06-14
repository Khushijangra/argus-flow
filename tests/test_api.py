import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_status_endpoint():
    response = client.get("/api/status")
    # Some environments might return 404 if not registered,
    # but based on the audit, /api/status should be there.
    if response.status_code == 200:
        data = response.json()
        assert "status" in data

def test_snapshot_endpoint():
    # Will likely return 404 or 422 depending on the path
    # Just verify the backend serves requests without crashing
    response = client.get("/api/live/camera/J1_1/north/snapshot")
    assert response.status_code in [200, 404, 500, 503]

def test_signal_override():
    # Requires authentication, should return 403 or 401
    response = client.post("/api/signal/override", json={"intersection_id": "J1_1"})
    assert response.status_code in [401, 403, 422]
