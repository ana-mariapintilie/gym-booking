SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    member_name TEXT NOT NULL,
    member_email TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'waitlisted', 'cancelled')),
    created_at TEXT NOT NULL
);
"""