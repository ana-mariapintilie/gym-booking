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


def copy_migrations(target, *names):
    target.mkdir(exist_ok=True)
    for name in names:
        shutil.copy(migrate.MIGRATIONS_DIR / name, target / name)
    return target


def test_fresh_database_gets_every_migration_and_the_seed(empty_db_url):
    with closing(connect(empty_db_url)) as conn:
        assert migrate.apply_migrations(conn) == [1, 2, 3]
        assert versions(conn) == [1, 2, 3]
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM classes")
        assert cursor.fetchone()[0] == 4


def test_second_run_applies_nothing_and_does_not_reseed(empty_db_url):
    with closing(connect(empty_db_url)) as conn:
        migrate.apply_migrations(conn)
        assert migrate.apply_migrations(conn) == []
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM classes")
        assert cursor.fetchone()[0] == 4


def test_adding_room_keeps_existing_classes(empty_db_url, tmp_path):
    old = copy_migrations(tmp_path / "old", "0001_create_classes.sql")
    with closing(connect(empty_db_url)) as conn:
        migrate.apply_migrations(conn, old)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO classes (name, instructor, starts_at, duration_minutes, capacity) "
            "OUTPUT INSERTED.id VALUES ('Kettlebells', 'Ana', '2026-11-20 07:30', 30, 8)"
        )
        existing_id = cursor.fetchone()[0]
        conn.commit()

        assert migrate.apply_migrations(conn) == [2, 3]

        cursor = conn.cursor(as_dict=True)
        cursor.execute("SELECT * FROM classes")
        rows = cursor.fetchall()

    # The seed only fills an empty table, so the existing class is the only one.
    assert len(rows) == 1
    assert rows[0]["id"] == existing_id
    assert rows[0]["name"] == "Kettlebells"
    assert rows[0]["capacity"] == 8
    assert rows[0]["room"] == "Main studio"


def test_failing_migration_is_rolled_back_and_not_recorded(empty_db_url, tmp_path):
    folder = copy_migrations(tmp_path / "m", "0001_create_classes.sql")
    (folder / "0002_broken.sql").write_text(
        "CREATE TABLE half_done (id INT);\nGO\nSELECT * FROM table_that_does_not_exist;"
    )
    with closing(connect(empty_db_url)) as conn:
        with pytest.raises(pymssql.Error):
            migrate.apply_migrations(conn, folder)
        assert versions(conn) == [1]
        cursor = conn.cursor()
        cursor.execute("SELECT OBJECT_ID('half_done')")
        assert cursor.fetchone()[0] is None


def test_badly_named_file_is_rejected(tmp_path):
    (tmp_path / "add_stuff.sql").write_text("SELECT 1")
    with pytest.raises(ValueError, match="0001_name.sql"):
        migrate.find_migrations(tmp_path)


def test_duplicate_version_is_rejected(tmp_path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1")
    (tmp_path / "0001_b.sql").write_text("SELECT 1")
    with pytest.raises(ValueError, match="same version"):
        migrate.find_migrations(tmp_path)


def test_startup_retries_until_the_database_is_ready(monkeypatch, empty_db_url):
    monkeypatch.setenv("DATABASE_URL", empty_db_url)
    calls = []

    def flaky_connect():
        calls.append(1)
        if len(calls) < 3:
            raise pymssql.OperationalError("not ready")
        return connect()

    monkeypatch.setattr(migrate, "connect", flaky_connect)
    assert migrate.migrate_on_startup(attempts=5, delay_seconds=0) == [1, 2, 3]
    assert len(calls) == 3


def test_startup_gives_up_after_the_last_attempt(monkeypatch):
    def broken_connect():
        raise pymssql.OperationalError("down")

    monkeypatch.setattr(migrate, "connect", broken_connect)
    with pytest.raises(pymssql.OperationalError):
        migrate.migrate_on_startup(attempts=2, delay_seconds=0)
