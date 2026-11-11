from contextlib import closing

import pymssql

from app import schedule_client
from app.db import connect

ALREADY_BOOKED = "You already have a booking for this class"


def decide_status(confirmed_count, capacity):
    if confirmed_count < capacity:
        return "confirmed"
    return "waitlisted"


def book_class(class_id, member_name, member_email):
    """Raises ValueError for bad input, ScheduleUnavailable if the class can't be checked."""
    if not member_name.strip():
        raise ValueError("Name is required")
    if "@" not in member_email:
        raise ValueError("A valid email is required")

    found = schedule_client.get_class(class_id)
    if found is None:
        raise ValueError("Class not found")

    email = member_email.strip().lower()
    with closing(connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM bookings WHERE class_id = %s AND member_email = %s "
            "AND status <> 'cancelled'",
            (class_id, email),
        )
        if cursor.fetchone()[0] > 0:
            raise ValueError(ALREADY_BOOKED)

        # UPDLOCK + HOLDLOCK keeps two people from taking the last spot at once.
        cursor.execute(
            "SELECT COUNT(*) FROM bookings WITH (UPDLOCK, HOLDLOCK) "
            "WHERE class_id = %s AND status = 'confirmed'",
            (class_id,),
        )
        status = decide_status(cursor.fetchone()[0], found["capacity"])

        try:
            cursor.execute(
                "INSERT INTO bookings (class_id, member_name, member_email, status) "
                "VALUES (%s, %s, %s, %s)",
                (class_id, member_name.strip(), email, status),
            )
        except pymssql.IntegrityError:
            raise ValueError(ALREADY_BOOKED)
        conn.commit()
    return status


def cancel_booking(booking_id):
    with closing(connect()) as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            "SELECT class_id, status FROM bookings WITH (UPDLOCK) WHERE id = %s",
            (booking_id,),
        )
        booking = cursor.fetchone()
        if booking is None or booking["status"] == "cancelled":
            raise ValueError("Booking not found or already cancelled")

        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = %s", (booking_id,))

        promoted_id = None
        if booking["status"] == "confirmed":
            cursor.execute(
                "SELECT TOP 1 id FROM bookings WITH (UPDLOCK) "
                "WHERE class_id = %s AND status = 'waitlisted' ORDER BY created_at, id",
                (booking["class_id"],),
            )
            next_in_line = cursor.fetchone()
            if next_in_line is not None:
                promoted_id = next_in_line["id"]
                cursor.execute(
                    "UPDATE bookings SET status = 'confirmed' WHERE id = %s", (promoted_id,)
                )
        conn.commit()
    return promoted_id


def list_bookings(class_id):
    with closing(connect()) as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            "SELECT id, class_id, member_name, member_email, status, created_at "
            "FROM bookings WHERE class_id = %s ORDER BY created_at, id",
            (class_id,),
        )
        rows = cursor.fetchall()
    for row in rows:
        row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return rows
