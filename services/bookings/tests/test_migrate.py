import shutil
from contextlib import closing

import pymssql
import pytest

from app import migrate
from app.db import connect


def versions(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
    return [row[0] for row in cursor.fetchall()]


def test_fresh_database_gets_every_migration_once(empty_db_url):
    with closing(connect(empty_db_url)) as conn:
        assert migrate.apply_migrations(conn) == [1, 2]
        assert migrate.apply_migrations(conn) == []
        assert versions(conn) == [1, 2]


def test_unique_index_keeps_existing_bookings(empty_db_url, tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    shutil.copy(migrate.MIGRATIONS_DIR / "0001_create_bookings.sql", old)
    with closing(connect(empty_db_url)) as conn:
        migrate.apply_migrations(conn, old)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bookings (class_id, member_name, member_email, status) VALUES "
            "(1, 'Ana', 'ana@test.com', 'confirmed'), "
            "(1, 'Ana', 'ana@test.com', 'cancelled')"
        )
        conn.commit()

        assert migrate.apply_migrations(conn) == [2]

        cursor = conn.cursor(as_dict=True)
        cursor.execute("SELECT member_name, status FROM bookings ORDER BY id")
        assert cursor.fetchall() == [
            {"member_name": "Ana", "status": "confirmed"},
            {"member_name": "Ana", "status": "cancelled"},
        ]

        with pytest.raises(pymssql.IntegrityError):
            cursor.execute(
                "INSERT INTO bookings (class_id, member_name, member_email, status) "
                "VALUES (1, 'Ana', 'ana@test.com', 'waitlisted')"
            )
        conn.rollback()


def test_failing_migration_is_rolled_back_and_not_recorded(empty_db_url, tmp_path):
    (tmp_path / "0001_broken.sql").write_text(
        "CREATE TABLE half_done (id INT);\nGO\nSELECT * FROM table_that_does_not_exist;"
    )
    with closing(connect(empty_db_url)) as conn:
        with pytest.raises(pymssql.Error):
            migrate.apply_migrations(conn, tmp_path)
        assert versions(conn) == []


@pytest.mark.parametrize(
    "names, message", [(["add.sql"], "0001_name.sql"), (["0001_a.sql", "0001_b.sql"], "same version")]
)
def test_bad_migration_files_are_rejected(tmp_path, names, message):
    for name in names:
        (tmp_path / name).write_text("SELECT 1")
    with pytest.raises(ValueError, match=message):
        migrate.find_migrations(tmp_path)


def test_startup_retries_until_the_database_is_ready(monkeypatch, empty_db_url):
    monkeypatch.setenv("DATABASE_URL", empty_db_url)
    calls = []

    def flaky_connect():
        calls.append(1)
        if len(calls) < 2:
            raise pymssql.OperationalError("not ready")
        return connect()

    monkeypatch.setattr(migrate, "connect", flaky_connect)
    assert migrate.migrate_on_startup(attempts=3, delay_seconds=0) == [1, 2]


def test_startup_gives_up_after_the_last_attempt(monkeypatch):
    def broken_connect():
        raise pymssql.OperationalError("down")

    monkeypatch.setattr(migrate, "connect", broken_connect)
    with pytest.raises(pymssql.OperationalError):
        migrate.migrate_on_startup(attempts=2, delay_seconds=0)
