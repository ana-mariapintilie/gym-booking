import os
from contextlib import closing
from urllib.parse import urlparse

import pytest

from app import schedule_client
from app.db import connect
from app.migrate import apply_migrations
from app.schedule_client import ScheduleUnavailable

# Tests need the SQL Server from docker compose (`docker compose up -d mssql`).
ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "mssql://sa:GymBooking_Dev_2026@localhost:1433/master"
)


def recreate_database(name):
    with closing(connect(ADMIN_URL, autocommit=True)) as conn:
        conn.cursor().execute(
            f"IF DB_ID('{name}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{name}]; END; "
            f"CREATE DATABASE [{name}];"
        )
    return urlparse(ADMIN_URL)._replace(path=f"/{name}").geturl()


@pytest.fixture(scope="session")
def migrated_db_url():
    url = recreate_database("bookings_test")
    with closing(connect(url)) as conn:
        apply_migrations(conn)
    return url


@pytest.fixture(autouse=True)
def clean_db(migrated_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_db_url)
    with closing(connect()) as conn:
        conn.cursor().execute("TRUNCATE TABLE bookings")
        conn.commit()


@pytest.fixture
def empty_db_url():
    return recreate_database("bookings_migration_test")


@pytest.fixture
def schedule(monkeypatch):
    """Stands in for the schedule service: add classes to the dict, or set down=True."""
    class FakeSchedule:
        classes = {}
        down = False

        def get_class(self, class_id):
            if self.down:
                raise ScheduleUnavailable("fake outage")
            return self.classes.get(class_id)

    fake = FakeSchedule()
    fake.classes = {}
    monkeypatch.setattr(schedule_client, "get_class", fake.get_class)
    return fake
