from flask import Blueprint, redirect, render_template, request, url_for

from schedule import service

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/classes")
def classes_page():
    return render_template("classes.html", classes=service.list_classes(), error=None)


@schedule_bp.route("/classes", methods=["POST"])
def create_class_route():
    try:
        service.create_class(
            request.form["name"],
            request.form["instructor"],
            request.form["starts_at"].replace("T", " "),
            int(request.form["duration_minutes"]),
            int(request.form["capacity"]),
        )
    except ValueError as error:
        return render_template(
            "classes.html", classes=service.list_classes(), error=str(error)
        ), 400
    return redirect(url_for("schedule.classes_page"))