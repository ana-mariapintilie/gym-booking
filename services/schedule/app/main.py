import os
from contextlib import closing

import pymssql
from flask import Flask, jsonify, request

from app import service
from app.cors import setup_cors
from app.db import connect
from app.migrate import migrate_on_startup
from app.request_log import setup_logging

app = Flask(__name__)
setup_logging(app, "schedule")
setup_cors(app)


@app.get("/")
def home():
    return jsonify(service="schedule", classes="/api/classes", health="/health")


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


@app.get("/api/classes")
def list_classes_api():
    return jsonify(service.list_classes())


@app.get("/api/classes/<int:class_id>")
def get_class_api(class_id):
    found = service.get_class(class_id)
    if found is None:
        return jsonify(error="Class not found"), 404
    return jsonify(found)


@app.post("/api/classes")
def create_class_api():
    data = request.get_json(silent=True) or {}
    try:
        duration_minutes = int(data.get("duration_minutes"))
        capacity = int(data.get("capacity"))
    except (TypeError, ValueError):
        return jsonify(error="Duration and capacity must be whole numbers"), 400
    try:
        class_id = service.create_class(
            str(data.get("name", "")),
            str(data.get("instructor", "")),
            str(data.get("starts_at", "")).replace("T", " "),
            duration_minutes,
            capacity,
            str(data.get("room") or "Main studio"),
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(service.get_class(class_id)), 201


if __name__ == "__main__":
    migrate_on_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
