-- No foreign key to classes: that table lives in the schedule database.
-- The bookings service checks the class through the schedule API instead.
CREATE TABLE bookings (
    id INT IDENTITY(1,1) PRIMARY KEY,
    class_id INT NOT NULL,
    member_name NVARCHAR(100) NOT NULL,
    member_email NVARCHAR(254) NOT NULL,
    status NVARCHAR(10) NOT NULL CHECK (status IN ('confirmed', 'waitlisted', 'cancelled')),
    created_at DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE INDEX ix_bookings_class_status ON bookings (class_id, status);
