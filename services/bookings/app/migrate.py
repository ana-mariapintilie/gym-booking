import logging
import re
import time
from contextlib import closing
from pathlib import Path

import pymssql

from app.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
FILE_NAME = re.compile(r"^(\d{4})_\w+\.sql$")
GO_LINE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

CREATE_MIGRATIONS_TABLE = """
IF OBJECT_ID('schema_migrations') IS NULL
CREATE TABLE schema_migrations (
    version INT PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT GETDATE()
)
"""

log = logging.getLogger(__name__)


def find_migrations(directory=MIGRATIONS_DIR):
    migrations = []
    for path in sorted(Path(directory).glob("*.sql")):
        match = FILE_NAME.match(path.name)
        if match is None:
            raise ValueError(f"Migration file must be named like 0001_name.sql: {path.name}")
        migrations.append((int(match.group(1)), path))
    versions = [version for version, _ in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("Two migration files share the same version number")
    return migrations


def applied_versions(conn):
    cursor = conn.cursor()
    cursor.execute(CREATE_MIGRATIONS_TABLE)
    conn.commit()
    cursor.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations(conn, directory=MIGRATIONS_DIR):
    """Apply every migration not yet in schema_migrations, each in its own transaction."""
    done = applied_versions(conn)
    applied = []
    for version, path in find_migrations(directory):
        if version in done:
            continue
        cursor = conn.cursor()
        try:
            for batch in GO_LINE.split(path.read_text()):
                if batch.strip():
                    cursor.execute(batch)
            cursor.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                (version, path.name),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        log.info("Applied migration %s", path.name)
        applied.append(version)
    return applied


def migrate_on_startup(attempts=20, delay_seconds=3):
    """The database container may still be starting, so retry the connection."""
    for attempt in range(1, attempts + 1):
        try:
            with closing(connect()) as conn:
                return apply_migrations(conn)
        except pymssql.OperationalError as error:
            if attempt == attempts:
                raise
            log.warning("Database not ready (attempt %s/%s): %s", attempt, attempts, error)
            time.sleep(delay_seconds)
