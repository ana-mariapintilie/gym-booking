import logging

import pytest

from app import service
from app.main import app

VALID = {
    "name": "Boxing", "instructor": "Carlos", "starts_at": "2026-10-14T19:00",
    "duration_minutes": 60, "capacity": 12, "room": "Ring",
}


@pytest.fixture
def client():
    return app.test_client()


def make_class(name="Yoga", capacity=10):
    return service.create_class(name, "Marta", "2026-10-10 18:00", 60, capacity)


def test_health_is_ok_when_the_database_answers(client, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc123")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "abc123"}


def test_health_is_503_when_the_database_is_unreachable(client, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@127.0.0.1:1/db")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"


def test_every_request_is_logged_with_method_path_and_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="schedule"):
        client.get("/health")
        client.get("/api/classes/999")
    assert "GET /health 200" in caplog.text
    assert "GET /api/classes/999 404" in caplog.text


def test_home_names_the_service(client):
    assert client.get("/").get_json()["service"] == "schedule"


def test_create_class_api_returns_201_and_the_saved_class(client):
    response = client.post("/api/classes", json=VALID)
    assert response.status_code == 201
    body = response.get_json()
    assert (body["name"], body["starts_at"], body["room"], body["capacity"]) == (
        "Boxing", "2026-10-14 19:00", "Ring", 12)
    assert service.get_class(body["id"])["name"] == "Boxing"


def test_room_defaults_to_main_studio(client):
    data = {key: value for key, value in VALID.items() if key != "room"}
    assert client.post("/api/classes", json=data).get_json()["room"] == "Main studio"


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"name": ""}, "Class name is required"),
        ({"starts_at": "tomorrow"}, "Start time"),
        ({"capacity": "lots"}, "whole numbers"),
        ({"duration_minutes": None}, "whole numbers"),
    ],
)
def test_create_class_api_rejects_bad_input_and_saves_nothing(client, bad, message):
    response = client.post("/api/classes", json={**VALID, **bad})
    assert response.status_code == 400
    assert message in response.get_json()["error"]
    assert service.list_classes() == []


def test_create_class_api_without_a_json_body_is_400(client):
    assert client.post("/api/classes", data="not json").status_code == 400


def test_class_api_returns_the_class(client):
    class_id = make_class(capacity=7)
    body = client.get(f"/api/classes/{class_id}").get_json()
    assert body["capacity"] == 7
    assert body["id"] == class_id


def test_class_api_returns_404_for_missing_class(client):
    response = client.get("/api/classes/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Class not found"}


def test_class_list_api(client):
    make_class("A")
    make_class("B")
    assert [c["name"] for c in client.get("/api/classes").get_json()] == ["A", "B"]


def test_cors_header_is_only_sent_to_the_ui_origin(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://ui.test")
    allowed = client.get("/api/classes", headers={"Origin": "http://ui.test"})
    other = client.get("/api/classes", headers={"Origin": "http://evil.test"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://ui.test"
    assert "Access-Control-Allow-Origin" not in other.headers


def test_cors_preflight_allows_a_json_post_from_the_ui(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://ui.test")
    response = client.options("/api/classes", headers={
        "Origin": "http://ui.test",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    })
    assert response.status_code == 200
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Headers"] == "Content-Type"
