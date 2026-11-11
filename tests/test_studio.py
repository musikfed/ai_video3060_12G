from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_web_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "10720" in response.text


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ai_generation"] is False


def test_invalid_media_id():
    response = client.get("/api/media/../../etc/passwd")
    assert response.status_code in (400, 404)


def test_empty_timeline_rejected():
    response = client.post("/api/render", json={"clips": []})
    assert response.status_code == 422


def test_unsupported_dimensions():
    response = client.post("/api/render", json={
        "clips": [{"media_id": "00000000-0000-0000-0000-000000000000"}],
        "width": 8192, "height": 8192,
    })
    assert response.status_code == 422


def test_unknown_job():
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
