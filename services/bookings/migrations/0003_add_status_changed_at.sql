-- Records when each booking last changed status: booked, cancelled, or moved up
-- from the waitlist. The table already holds bookings, so they are kept and
-- backfilled with created_at, the last moment we know their status was set.
ALTER TABLE bookings ADD status_changed_at DATETIME NULL;
GO
UPDATE bookings SET status_changed_at = created_at WHERE status_changed_at IS NULL;
GO
ALTER TABLE bookings ALTER COLUMN status_changed_at DATETIME NOT NULL;
GO
ALTER TABLE bookings ADD CONSTRAINT df_bookings_status_changed_at
    DEFAULT GETDATE() FOR status_changed_at;
