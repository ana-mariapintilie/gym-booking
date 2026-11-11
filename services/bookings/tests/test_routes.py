import logging

import pytest

from app import service
from app.main import app


@pytest.fixture
def client(schedule, monkeypatch):
    monkeypatch.setenv("SCHEDULE_PUBLIC_URL", "http://schedule.test")
    schedule.classes[1] = {
        "id": 1, "name": "Spinning", "instructor": "Leo", "starts_at": "2026-10-13 18:00",
        "room": "Main studio", "capacity": 1,
    }
    return app.test_client()


def book(client, name="Ana", email="ana@test.com", class_id=1):
    return client.post(f"/classes/{class_id}/bookings",
                       data={"member_name": name, "member_email": email})


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
    with caplog.at_level(logging.INFO, logger="bookings"):
        client.get("/health")
        book(client, email="bad")
    assert "GET /health 200" in caplog.text
    assert "POST /classes/1/bookings 400" in caplog.text


def test_home_redirects_to_the_schedule(client):
    assert client.get("/").headers["Location"] == "http://schedule.test/classes"


def test_page_shows_class_details_from_schedule(client):
    page = client.get("/classes/1/bookings").get_data(as_text=True)
    assert "Spinning with Leo" in page
    assert "http://schedule.test/classes" in page


def test_page_for_unknown_class_is_404(client):
    response = client.get("/classes/999/bookings")
    assert response.status_code == 404
    assert "Class not found" in response.get_data(as_text=True)


def test_booking_redirects_and_is_listed(client):
    assert book(client).status_code == 302
    assert client.get("/api/classes/1/bookings").get_json()[0]["status"] == "confirmed"


def test_booking_error_is_shown(client):
    response = book(client, name=" ")
    assert response.status_code == 400
    assert "Name is required" in response.get_data(as_text=True)


def test_page_still_works_when_schedule_is_down(client, schedule):
    book(client)
    schedule.down = True
    response = client.get("/classes/1/bookings")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Class details are temporarily unavailable" in page
    assert "ana@test.com" in page


def test_booking_when_schedule_is_down_fails_gracefully(client, schedule):
    schedule.down = True
    response = book(client)
    assert response.status_code == 503
    assert "Booking is paused" in response.get_data(as_text=True)
    assert service.list_bookings(1) == []


def test_cancel_route_promotes_and_redirects(client):
    book(client, "Ana", "ana@test.com")
    book(client, "Luis", "luis@test.com")
    ana_id = service.list_bookings(1)[0]["id"]
    response = client.post(f"/classes/1/bookings/{ana_id}/cancel")
    assert response.status_code == 302
    assert service.list_bookings(1)[1]["status"] == "confirmed"


def test_cancel_route_shows_error_for_missing_booking(client):
    response = client.post("/classes/1/bookings/999/cancel")
    assert response.status_code == 400
    assert "Booking not found" in response.get_data(as_text=True)
