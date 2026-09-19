"""API endpoint tests using Flask test client."""
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert "status" in data
    assert "services" in data

def test_models_endpoint(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.get_json()
    assert "models" in data
    assert "default_model" in data

def test_skills_endpoint(client):
    res = client.get("/api/skills")
    assert res.status_code == 200
    data = res.get_json()
    assert "skills" in data
    assert len(data["skills"]) >= 1

def test_vectordb_stats_endpoint(client):
    res = client.get("/api/vectordb/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_chunks" in data
    assert "total_documents" in data
    assert "db_size_mb" in data

def test_telemetry_endpoint(client):
    res = client.get("/api/telemetry")
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert "charts" in data

def test_logs_endpoint(client):
    res = client.get("/api/logs")
    assert res.status_code == 200
    data = res.get_json()
    assert "conversations" in data
    assert "statistics" in data
