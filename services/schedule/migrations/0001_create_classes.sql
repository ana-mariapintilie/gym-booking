CREATE TABLE classes (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    instructor NVARCHAR(100) NOT NULL,
    starts_at SMALLDATETIME NOT NULL,
    duration_minutes INT NOT NULL CHECK (duration_minutes > 0),
    capacity INT NOT NULL CHECK (capacity > 0)
);
