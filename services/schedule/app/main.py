import os
from contextlib import closing

import pymssql
from flask import Flask, jsonify, redirect, render_template, request, url_for

from app import service
from app.db import connect
from app.migrate import migrate_on_startup
from app.request_log import setup_logging

app = Flask(__name__)
setup_logging(app, "schedule")


def render_classes(error=None, status_code=200):
    return render_template(
        "classes.html",
        classes=service.list_classes(),
        error=error,
        bookings_url=os.environ.get("BOOKINGS_PUBLIC_URL", "http://localhost:8002"),
    ), status_code


@app.get("/")
def home():
    return redirect(url_for("classes_page"))


@app.get("/health")
def health():
    try:
        with closing(connect()) as conn:
            conn.cursor().execute("SELECT 1")
    except (pymssql.Error, KeyError):
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")


@app.get("/classes")
def classes_page():
    return render_classes()


@app.post("/classes")
def create_class_route():
    try:
        service.create_class(
            request.form["name"],
            request.form["instructor"],
            request.form["starts_at"].replace("T", " "),
            int(request.form["duration_minutes"]),
            int(request.form["capacity"]),
            request.form.get("room", "Main studio"),
        )
    except ValueError as error:
        return render_classes(error=str(error), status_code=400)
    return redirect(url_for("classes_page"))


@app.get("/api/classes")
def list_classes_api():
    return jsonify(service.list_classes())


@app.get("/api/classes/<int:class_id>")
def get_class_api(class_id):
    found = service.get_class(class_id)
    if found is None:
        return jsonify(error="Class not found"), 404
    return jsonify(found)


if __name__ == "__main__":
    migrate_on_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
