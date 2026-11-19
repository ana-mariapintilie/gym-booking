import logging

import pytest

from app import service
from app.main import app


@pytest.fixture
def client(schedule):
    schedule.classes[1] = {
        "id": 1, "name": "Spinning", "instructor": "Leo", "starts_at": "2026-10-13 18:00",
        "room": "Main studio", "capacity": 1,
    }
    return app.test_client()


def book(client, name="Ana", email="ana@test.com", class_id=1):
    return client.post(f"/api/classes/{class_id}/bookings",
                       json={"member_name": name, "member_email": email})


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
    with caplog.at_level(logging.INFO, logger="bookings"):
        client.get("/health")
        book(client, email="bad")
    assert "GET /health 200" in caplog.text
    assert "POST /api/classes/1/bookings 400" in caplog.text


def test_home_names_the_service(client):
    assert client.get("/").get_json()["service"] == "bookings"


def test_booking_returns_201_and_waitlists_when_full(client):
    first = book(client, "Ana", "ana@test.com")
    second = book(client, "Luis", "luis@test.com")
    assert (first.status_code, first.get_json()) == (201, {"status": "confirmed"})
    assert (second.status_code, second.get_json()) == (201, {"status": "waitlisted"})


def test_bookings_are_listed(client):
    book(client)
    listed = client.get("/api/classes/1/bookings").get_json()
    assert [(b["member_email"], b["status"]) for b in listed] == [("ana@test.com", "confirmed")]


@pytest.mark.parametrize(
    "kwargs, message",
    [({"name": " "}, "Name is required"), ({"class_id": 999}, "Class not found")],
)
def test_booking_errors_are_400_with_a_message(client, kwargs, message):
    response = book(client, **kwargs)
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_booking_without_a_json_body_is_400(client):
    response = client.post("/api/classes/1/bookings", data="not json")
    assert response.status_code == 400


def test_booking_when_schedule_is_down_fails_gracefully(client, schedule):
    schedule.down = True
    response = book(client)
    assert response.status_code == 503
    assert "Booking is paused" in response.get_json()["error"]
    assert service.list_bookings(1) == []


def test_bookings_are_still_listed_when_schedule_is_down(client, schedule):
    book(client)
    schedule.down = True
    response = client.get("/api/classes/1/bookings")
    assert response.status_code == 200
    assert response.get_json()[0]["member_email"] == "ana@test.com"


def test_cancel_returns_who_was_promoted(client):
    book(client, "Ana", "ana@test.com")
    book(client, "Luis", "luis@test.com")
    ana_id, luis_id = (b["id"] for b in service.list_bookings(1))
    response = client.post(f"/api/classes/1/bookings/{ana_id}/cancel")
    assert response.status_code == 200
    assert response.get_json() == {"cancelled": ana_id, "promoted": luis_id}


def test_cancel_missing_booking_is_404(client):
    response = client.post("/api/classes/1/bookings/999/cancel")
    assert response.status_code == 404
    assert "Booking not found" in response.get_json()["error"]


def test_cancel_refuses_a_booking_from_another_class(client, schedule):
    schedule.classes[2] = {"id": 2, "name": "Yoga", "capacity": 5}
    book(client, "Ana", "ana@test.com", class_id=2)
    ana_id = service.list_bookings(2)[0]["id"]

    response = client.post(f"/api/classes/1/bookings/{ana_id}/cancel")

    assert response.status_code == 404
    assert service.list_bookings(2)[0]["status"] == "confirmed"


def test_cors_header_is_only_sent_to_the_ui_origin(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://ui.test")
    allowed = client.get("/health", headers={"Origin": "http://ui.test"})
    other = client.get("/health", headers={"Origin": "http://evil.test"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://ui.test"
    assert "Access-Control-Allow-Origin" not in other.headers
