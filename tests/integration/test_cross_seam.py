"""Runs against the real stack: start it first with `docker compose up -d --build`."""
import json
import os
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

SCHEDULE = os.environ.get("SCHEDULE_BASE_URL", "http://localhost:8001")
BOOKINGS = os.environ.get("BOOKINGS_BASE_URL", "http://localhost:8002")
UI = os.environ.get("UI_BASE_URL", "http://localhost:8080")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def call(method, url, body=None, headers=None):
    """Returns (status, parsed JSON or None, response headers)."""
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(headers or {})
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, method=method, headers=headers), timeout=10) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None, r.headers
    except HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else None, error.headers


def create_class(capacity):
    status, body, _ = call("POST", f"{SCHEDULE}/api/classes", {
        "name": f"Integration {uuid.uuid4().hex[:8]}", "instructor": "Test",
        "starts_at": "2026-12-01T09:00", "duration_minutes": 45, "capacity": capacity,
    })
    assert status == 201, body
    return body["id"]


def book(class_id, email):
    return call("POST", f"{BOOKINGS}/api/classes/{class_id}/bookings",
                {"member_name": email.split("@")[0], "member_email": email})


def list_bookings(class_id):
    status, body, _ = call("GET", f"{BOOKINGS}/api/classes/{class_id}/bookings")
    assert status == 200, body
    return body


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)


def wait_until_healthy(url, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if call("GET", f"{url}/health")[0] == 200:
                return
        except OSError:
            pass  # container started but the app is not listening yet
        time.sleep(1)
    raise AssertionError(f"{url} did not become healthy")


@pytest.fixture(scope="module", autouse=True)
def stack_is_up():
    wait_until_healthy(SCHEDULE)
    wait_until_healthy(BOOKINGS)


def test_both_services_report_healthy():
    for url in (SCHEDULE, BOOKINGS):
        status, body, _ = call("GET", f"{url}/health")
        assert status == 200
        assert (body["status"], body["db"]) == ("ok", "ok")


def test_ui_is_served_and_both_services_allow_its_origin():
    with urlopen(f"{UI}/", timeout=10) as response:
        assert "Gym classes" in response.read().decode()
    for url in (SCHEDULE, BOOKINGS):
        headers = call("GET", f"{url}/health", headers={"Origin": UI})[2]
        assert headers["Access-Control-Allow-Origin"] == UI


def test_bookings_uses_capacity_from_the_schedule_service():
    class_id = create_class(capacity=1)

    assert book(class_id, "first@test.com")[:2] == (201, {"status": "confirmed"})
    assert book(class_id, "second@test.com")[:2] == (201, {"status": "waitlisted"})
    assert [b["status"] for b in list_bookings(class_id)] == ["confirmed", "waitlisted"]


def test_class_unknown_to_schedule_cannot_be_booked():
    assert book(999999, "ghost@test.com")[:2] == (400, {"error": "Class not found"})


def test_booking_fails_fast_and_cleanly_while_schedule_is_down():
    class_id = create_class(capacity=5)
    compose("stop", "schedule")
    try:
        started = time.monotonic()
        status, body, _ = book(class_id, "during-outage@test.com")
        assert status == 503
        assert "Booking is paused" in body["error"]
        assert time.monotonic() - started < 5
        assert list_bookings(class_id) == []
    finally:
        compose("start", "schedule")
        wait_until_healthy(SCHEDULE)

    assert book(class_id, "after-outage@test.com")[0] == 201
