import logging

import pytest

from app import service
from app.main import app


@pytest.fixture
def client():
    return app.test_client()


def make_class(name="Yoga", capacity=10):
    return service.create_class(name, "Marta", "2026-10-10 18:00", 60, capacity)


def test_health_is_ok_when_the_database_answers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


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


def test_home_redirects_to_classes(client):
    assert client.get("/").headers["Location"] == "/classes"


def test_classes_page_lists_classes_and_links_to_bookings(client, monkeypatch):
    monkeypatch.setenv("BOOKINGS_PUBLIC_URL", "http://bookings.test")
    class_id = make_class("Spinning")
    page = client.get("/classes").get_data(as_text=True)
    assert "Spinning" in page
    assert f"http://bookings.test/classes/{class_id}/bookings" in page


def test_create_class_form_saves_and_redirects(client):
    response = client.post("/classes", data={
        "name": "Boxing", "instructor": "Carlos", "starts_at": "2026-10-14T19:00",
        "duration_minutes": "60", "capacity": "12", "room": "Ring",
    })
    assert response.status_code == 302
    saved = service.list_classes()[0]
    assert (saved["name"], saved["starts_at"], saved["room"]) == (
        "Boxing", "2026-10-14 19:00", "Ring")


def test_create_class_form_shows_validation_error(client):
    response = client.post("/classes", data={
        "name": "", "instructor": "Carlos", "starts_at": "2026-10-14T19:00",
        "duration_minutes": "60", "capacity": "12",
    })
    assert response.status_code == 400
    assert "Class name is required" in response.get_data(as_text=True)


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
