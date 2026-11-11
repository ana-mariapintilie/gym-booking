from contextlib import closing
from datetime import datetime

from app.db import connect

COLUMNS = "id, name, instructor, starts_at, duration_minutes, capacity, room"


def validate_class(name, instructor, starts_at, duration_minutes, capacity, room):
    if not name.strip():
        raise ValueError("Class name is required")
    if not instructor.strip():
        raise ValueError("Instructor is required")
    if not room.strip():
        raise ValueError("Room is required")
    try:
        datetime.strptime(starts_at, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Start time must look like 2026-10-06 18:00")
    if duration_minutes <= 0:
        raise ValueError("Duration must be more than 0 minutes")
    if capacity <= 0:
        raise ValueError("Capacity must be at least 1")


def to_dict(row):
    row = dict(row)
    row["starts_at"] = row["starts_at"].strftime("%Y-%m-%d %H:%M")
    return row


def create_class(name, instructor, starts_at, duration_minutes, capacity,
                 room="Main studio"):
    validate_class(name, instructor, starts_at, duration_minutes, capacity, room)
    with closing(connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO classes (name, instructor, starts_at, duration_minutes, capacity, room) "
            "OUTPUT INSERTED.id VALUES (%s, %s, %s, %s, %s, %s)",
            (name.strip(), instructor.strip(), starts_at, duration_minutes, capacity,
             room.strip()),
        )
        class_id = cursor.fetchone()[0]
        conn.commit()
    return class_id


def list_classes():
    with closing(connect()) as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(f"SELECT {COLUMNS} FROM classes ORDER BY starts_at, id")
        return [to_dict(row) for row in cursor.fetchall()]


def get_class(class_id):
    with closing(connect()) as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(f"SELECT {COLUMNS} FROM classes WHERE id = %s", (class_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return to_dict(row)
