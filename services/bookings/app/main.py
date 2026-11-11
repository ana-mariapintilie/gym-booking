import os
from contextlib import closing

import pymssql
from flask import Flask, jsonify, redirect, render_template, request, url_for

from app import schedule_client, service
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


def schedule_public_url():
    return os.environ.get("SCHEDULE_PUBLIC_URL", "http://localhost:8001")


def render_page(class_id, error=None, status_code=200, schedule_down=False):
    found = None
    if not schedule_down:
        try:
            found = schedule_client.get_class(class_id)
        except ScheduleUnavailable:
            schedule_down = True
    if found is None and not schedule_down and status_code == 200:
        error, status_code = "Class not found", 404
    return render_template(
        "bookings.html",
        class_id=class_id,
        gym_class=found,
        schedule_down=schedule_down,
        bookings=service.list_bookings(class_id),
        error=error,
        schedule_url=schedule_public_url(),
    ), status_code


@app.get("/")
def home():
    return redirect(f"{schedule_public_url()}/classes")


@app.get("/health")
def health():
    try:
        with closing(connect()) as conn:
            conn.cursor().execute("SELECT 1")
    except (pymssql.Error, KeyError):
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")


@app.get("/classes/<int:class_id>/bookings")
def bookings_page(class_id):
    return render_page(class_id)


@app.post("/classes/<int:class_id>/bookings")
def book_route(class_id):
    try:
        service.book_class(
            class_id, request.form["member_name"], request.form["member_email"]
        )
    except ValueError as error:
        return render_page(class_id, error=str(error), status_code=400)
    except ScheduleUnavailable:
        return render_page(class_id, error=SCHEDULE_DOWN_MESSAGE, status_code=503,
                           schedule_down=True)
    return redirect(url_for("bookings_page", class_id=class_id))


@app.post("/classes/<int:class_id>/bookings/<int:booking_id>/cancel")
def cancel_route(class_id, booking_id):
    try:
        service.cancel_booking(booking_id)
    except ValueError as error:
        return render_page(class_id, error=str(error), status_code=400)
    return redirect(url_for("bookings_page", class_id=class_id))


@app.get("/api/classes/<int:class_id>/bookings")
def list_bookings_api(class_id):
    return jsonify(service.list_bookings(class_id))


if __name__ == "__main__":
    migrate_on_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
