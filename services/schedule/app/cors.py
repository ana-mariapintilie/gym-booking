"""Lets the browser call this service, but only from the UI's own address (CORS_ORIGINS)."""
import os

from flask import request


def allowed_origins():
    return [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",")
            if origin.strip()]


def setup_cors(app):
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin in allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response
