from datetime import datetime

from db import get_connection


def validate_class(name, instructor, starts_at, duration_minutes, capacity):
    if not name.strip():
        raise ValueError("Class name is required")
    if not instructor.strip():
        raise ValueError("Instructor is required")
    try:
        datetime.strptime(starts_at, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Start time must look like 2026-10-06 18:00")
    if duration_minutes <= 0:
        raise ValueError("Duration must be more than 0 minutes")
    if capacity <= 0:
        raise ValueError("Capacity must be at least 1")


def create_class(name, instructor, starts_at, duration_minutes, capacity):
    validate_class(name, instructor, starts_at, duration_minutes, capacity)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO classes (name, instructor, starts_at, duration_minutes, capacity) "
        "VALUES (?, ?, ?, ?, ?)",
        (name.strip(), instructor.strip(), starts_at, duration_minutes, capacity),
    )
    conn.commit()
    class_id = cursor.lastrowid
    conn.close()
    return class_id


def list_classes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM classes ORDER BY starts_at").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_class_capacity(class_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT capacity FROM classes WHERE id = ?", (class_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return row["capacity"]