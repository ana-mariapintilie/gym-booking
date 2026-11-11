IF DB_ID('schedule') IS NULL CREATE DATABASE schedule;
IF DB_ID('bookings') IS NULL CREATE DATABASE bookings;
GO
IF SUSER_ID('schedule_user') IS NULL CREATE LOGIN schedule_user WITH PASSWORD = '$(SCHEDULE_PWD)', CHECK_POLICY = OFF;
IF SUSER_ID('bookings_user') IS NULL CREATE LOGIN bookings_user WITH PASSWORD = '$(BOOKINGS_PWD)', CHECK_POLICY = OFF;
GO
USE schedule;
GO
IF USER_ID('schedule_user') IS NULL CREATE USER schedule_user FOR LOGIN schedule_user;
ALTER ROLE db_ddladmin ADD MEMBER schedule_user;
ALTER ROLE db_datareader ADD MEMBER schedule_user;
ALTER ROLE db_datawriter ADD MEMBER schedule_user;
GO
USE bookings;
GO
IF USER_ID('bookings_user') IS NULL CREATE USER bookings_user FOR LOGIN bookings_user;
ALTER ROLE db_ddladmin ADD MEMBER bookings_user;
ALTER ROLE db_datareader ADD MEMBER bookings_user;
ALTER ROLE db_datawriter ADD MEMBER bookings_user;
GO