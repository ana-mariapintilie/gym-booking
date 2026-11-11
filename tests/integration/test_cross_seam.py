"""Runs against the real stack: start it first with `docker compose up -d --build`."""
import json
import os
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

SCHEDULE = os.environ.get("SCHEDULE_BASE_URL", "http://localhost:8001")
BOOKINGS = os.environ.get("BOOKINGS_BASE_URL", "http://localhost:8002")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def call(method, url, form=None):
    data = urlencode(form).encode() if form else None
    try:
        with urlopen(Request(url, data=data, method=method), timeout=10) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def get_json(url):
    status, body = call("GET", url)
    assert status == 200, body
    return json.loads(body)


def create_class(capacity):
    name = f"Integration {uuid.uuid4().hex[:8]}"
    status, _ = call("POST", f"{SCHEDULE}/classes", {
        "name": name, "instructor": "Test", "starts_at": "2026-12-01T09:00",
        "duration_minutes": "45", "capacity": str(capacity),
    })
    assert status == 200  # urllib followed the redirect to /classes
    return next(c["id"] for c in get_json(f"{SCHEDULE}/api/classes") if c["name"] == name)


def book(class_id, email):
    return call("POST", f"{BOOKINGS}/classes/{class_id}/bookings",
                {"member_name": email.split("@")[0], "member_email": email})


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
    assert get_json(f"{SCHEDULE}/health") == {"status": "ok"}
    assert get_json(f"{BOOKINGS}/health") == {"status": "ok"}


def test_bookings_uses_capacity_from_the_schedule_service():
    class_id = create_class(capacity=1)

    assert book(class_id, "first@test.com")[0] == 200
    assert book(class_id, "second@test.com")[0] == 200

    bookings = get_json(f"{BOOKINGS}/api/classes/{class_id}/bookings")
    assert [b["status"] for b in bookings] == ["confirmed", "waitlisted"]


def test_bookings_page_shows_class_name_fetched_from_schedule():
    class_id = create_class(capacity=3)
    status, page = call("GET", f"{BOOKINGS}/classes/{class_id}/bookings")
    assert status == 200
    assert "Integration" in page


def test_class_unknown_to_schedule_cannot_be_booked():
    status, page = book(999999, "ghost@test.com")
    assert status == 400
    assert "Class not found" in page


def test_booking_fails_fast_and_cleanly_while_schedule_is_down():
    class_id = create_class(capacity=5)
    compose("stop", "schedule")
    try:
        started = time.monotonic()
        status, page = book(class_id, "during-outage@test.com")
        assert status == 503
        assert "Booking is paused" in page
        assert time.monotonic() - started < 5
        assert get_json(f"{BOOKINGS}/api/classes/{class_id}/bookings") == []
        assert call("GET", f"{BOOKINGS}/classes/{class_id}/bookings")[0] == 200
    finally:
        compose("start", "schedule")
        wait_until_healthy(SCHEDULE)

    assert book(class_id, "after-outage@test.com")[0] == 200
