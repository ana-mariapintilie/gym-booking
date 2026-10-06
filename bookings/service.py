from datetime import datetime

from db import get_connection
from schedule.service import get_class_capacity


def decide_status(confirmed_count, capacity):
    if confirmed_count < capacity:
        return "confirmed"
    return "waitlisted"


def book_class(class_id, member_name, member_email):
    if not member_name.strip():
        raise ValueError("Name is required")
    if "@" not in member_email:
        raise ValueError("A valid email is required")

    capacity = get_class_capacity(class_id)
    if capacity is None:
        raise ValueError("Class not found")

    email = member_email.strip().lower()
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM bookings WHERE class_id = ? AND member_email = ? "
        "AND status != 'cancelled'",
        (class_id, email),
    ).fetchone()
    if existing is not None:
        conn.close()
        raise ValueError("You already have a booking for this class")

    confirmed_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE class_id = ? AND status = 'confirmed'",
        (class_id,),
    ).fetchone()[0]
    status = decide_status(confirmed_count, capacity)

    conn.execute(
        "INSERT INTO bookings (class_id, member_name, member_email, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (class_id, member_name.strip(), email, status,
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return status


def cancel_booking(booking_id):
    conn = get_connection()
    booking = conn.execute(
        "SELECT class_id, status FROM bookings WHERE id = ?", (booking_id,)
    ).fetchone()
    if booking is None or booking["status"] == "cancelled":
        conn.close()
        raise ValueError("Booking not found or already cancelled")

    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))

    promoted_id = None
    if booking["status"] == "confirmed":
        next_in_line = conn.execute(
            "SELECT id FROM bookings WHERE class_id = ? AND status = 'waitlisted' "
            "ORDER BY created_at, id LIMIT 1",
            (booking["class_id"],),
        ).fetchone()
        if next_in_line is not None:
            promoted_id = next_in_line["id"]
            conn.execute(
                "UPDATE bookings SET status = 'confirmed' WHERE id = ?", (promoted_id,)
            )

    conn.commit()
    conn.close()
    return promoted_id


def list_bookings(class_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM bookings WHERE class_id = ? ORDER BY created_at, id",
        (class_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]