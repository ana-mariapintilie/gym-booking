import pytest

import db
from bookings.schema import SCHEMA as BOOKINGS_SCHEMA
from schedule.schema import SCHEMA as SCHEDULE_SCHEMA


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db([SCHEDULE_SCHEMA, BOOKINGS_SCHEMA])