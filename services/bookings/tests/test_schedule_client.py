import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import schedule_client
from app.schedule_client import ScheduleUnavailable


class FakeScheduleHandler(BaseHTTPRequestHandler):
    """Answers like the schedule service; the class id picks the behaviour."""

    def do_GET(self):
        class_id = self.path.rsplit("/", 1)[-1]
        if class_id == "1":
            self.reply(200, json.dumps({"id": 1, "capacity": 5}).encode())
        elif class_id == "2":
            self.reply(404, b'{"error": "Class not found"}')
        elif class_id == "3":
            self.reply(500, b"boom")
        elif class_id == "4":
            self.reply(200, b"not json")
        elif class_id == "5":
            time.sleep(2)
            self.reply(200, b"{}")

    def reply(self, status, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_schedule(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeScheduleHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("SCHEDULE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("SCHEDULE_TIMEOUT_SECONDS", "0.5")
    yield
    server.shutdown()
    server.server_close()


def test_existing_class_is_returned(fake_schedule):
    assert schedule_client.get_class(1) == {"id": 1, "capacity": 5}


def test_missing_class_is_none(fake_schedule):
    assert schedule_client.get_class(2) is None


@pytest.mark.parametrize("class_id", [3, 4])
def test_server_error_or_bad_body_means_unavailable(fake_schedule, class_id):
    with pytest.raises(ScheduleUnavailable):
        schedule_client.get_class(class_id)


def test_slow_schedule_times_out_instead_of_hanging(fake_schedule):
    started = time.monotonic()
    with pytest.raises(ScheduleUnavailable):
        schedule_client.get_class(5)
    assert time.monotonic() - started < 1.5


def test_schedule_that_is_not_running_means_unavailable(monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]
    monkeypatch.setenv("SCHEDULE_URL", f"http://127.0.0.1:{free_port}")
    with pytest.raises(ScheduleUnavailable):
        schedule_client.get_class(1)
