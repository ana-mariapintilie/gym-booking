import os
from contextlib import closing
from urllib.parse import urlparse

import pytest

from app.db import connect
from app.migrate import apply_migrations

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
    url = recreate_database("schedule_test")
    with closing(connect(url)) as conn:
        apply_migrations(conn)
    return url


@pytest.fixture(autouse=True)
def clean_db(migrated_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_db_url)
    with closing(connect()) as conn:
        conn.cursor().execute("TRUNCATE TABLE classes")
        conn.commit()


@pytest.fixture
def empty_db_url():
    return recreate_database("schedule_migration_test")
