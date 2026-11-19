import os
from contextlib import closing

import pymssql
from flask import Flask, jsonify, request

from app import service
from app.cors import setup_cors
from app.db import connect
from app.migrate import migrate_on_startup
from app.request_log import setup_logging
from app.schedule_client import ScheduleUnavailable

SCHEDULE_DOWN_MESSAGE = (
    "Booking is paused because the class schedule can't be reached right now. "
    "Nothing was saved. Please try again in a minute."
)

app = Flask(__name__)
setup_logging(app, "bookings")
setup_cors(app)


@app.get("/")
def home():
    return jsonify(service="bookings", bookings="/api/classes/<id>/bookings", health="/health")


@app.get("/health")
def health():
    version = os.environ.get("GIT_SHA", "dev")
    try:
        with closing(connect()) as conn:
            cursor = conn.cursor()
            # Proves this login can write: insert a row, then undo it.
            cursor.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (-1, 'health check')"
            )
            conn.rollback()
            cursor.execute("SELECT COUNT(*) FROM schema_migrations")
            cursor.fetchone()
    except (pymssql.Error, KeyError):
        return jsonify(status="unavailable", db="unavailable", version=version), 503
    return jsonify(status="ok", db="ok", version=version)


@app.get("/api/classes/<int:class_id>/bookings")
def list_bookings_api(class_id):
    return jsonify(service.list_bookings(class_id))


@app.post("/api/classes/<int:class_id>/bookings")
def book_api(class_id):
    data = request.get_json(silent=True) or {}
    try:
        status = service.book_class(
            class_id, str(data.get("member_name", "")), str(data.get("member_email", ""))
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except ScheduleUnavailable:
        return jsonify(error=SCHEDULE_DOWN_MESSAGE), 503
    return jsonify(status=status), 201


@app.post("/api/classes/<int:class_id>/bookings/<int:booking_id>/cancel")
def cancel_api(class_id, booking_id):
    try:
        promoted_id = service.cancel_booking(booking_id, class_id)
    except ValueError as error:
        return jsonify(error=str(error)), 404
    return jsonify(cancelled=booking_id, promoted=promoted_id)


if __name__ == "__main__":
    migrate_on_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
