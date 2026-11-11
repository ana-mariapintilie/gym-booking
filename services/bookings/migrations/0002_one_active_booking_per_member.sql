-- Existing rows stay as they are; the index only blocks a second active
-- booking for the same email and class from now on.
CREATE UNIQUE INDEX ux_bookings_active_member
    ON bookings (class_id, member_email)
    WHERE status <> 'cancelled';
