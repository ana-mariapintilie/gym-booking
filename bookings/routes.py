from flask import Blueprint, redirect, render_template, request, url_for

from bookings import service

bookings_bp = Blueprint("bookings", __name__)


def render_page(class_id, error=None, status_code=200):
    return render_template(
        "bookings.html",
        class_id=class_id,
        bookings=service.list_bookings(class_id),
        error=error,
    ), status_code


@bookings_bp.route("/classes/<int:class_id>/bookings")
def bookings_page(class_id):
    return render_page(class_id)


@bookings_bp.route("/classes/<int:class_id>/bookings", methods=["POST"])
def book_route(class_id):
    try:
        service.book_class(
            class_id, request.form["member_name"], request.form["member_email"]
        )
    except ValueError as error:
        return render_page(class_id, error=str(error), status_code=400)
    return redirect(url_for("bookings.bookings_page", class_id=class_id))


@bookings_bp.route(
    "/classes/<int:class_id>/bookings/<int:booking_id>/cancel", methods=["POST"]
)
def cancel_route(class_id, booking_id):
    try:
        service.cancel_booking(booking_id)
    except ValueError as error:
        return render_page(class_id, error=str(error), status_code=400)
    return redirect(url_for("bookings.bookings_page", class_id=class_id))