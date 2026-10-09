# Gym Class Booking

A booking app for a small gym (around 300 members). Staff publish group classes (yoga, spinning, boxing) with a limited number of spots, and members book a spot online instead of signing up on paper at the front desk. When a class is full, members join a waitlist and are moved up automatically when someone cancels.

Built with Python 3.13, Flask and SQLite, as a single process.

## Feature domains

| Domain | Folder | Responsibility | Table |
|---|---|---|---|
| Schedule | `schedule/` | Create and list classes (name, instructor, start time, duration, capacity) | `classes` |
| Bookings | `bookings/` | Book a spot, waitlist when full, cancel, promote the next waitlisted member | `bookings` |

**The seam:** the bookings domain only uses one function from the schedule domain, `get_class_capacity(class_id)`. It never reads or changes the `classes` table directly. In a later split into services, this becomes the single request between them.

## Run it directly 

Requires Python 3.13.

```
git clone https://github.com/ana-mariapintilie/gym-booking.git
cd gym-booking
python3.13 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000/classes

## Run it with Docker

Requires Docker Desktop running.

```
docker build -t gym-booking .
docker run --rm -p 8000:8000 -v gym-booking-data:/data gym-booking
```

Open http://localhost:8000/classes

The database is stored in the `gym-booking-data` volume, so it survives the container being removed. To use another port:

```
docker run --rm -e PORT=9000 -p 9000:9000 -v gym-booking-data:/data gym-booking
```

## Configuration

All settings come from environment variables. No `.env` file is needed.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the app listens on (always bound to `0.0.0.0`) |
| `DATA_DIR` | `data` (locally), `/data` (in the container, set by the Dockerfile) | Folder that holds the SQLite file |

## Database

- **Path:** `$DATA_DIR/gym.db`, so `data/gym.db` locally and `/data/gym.db` in the container.
- **Schema:** created automatically on first start with `CREATE TABLE IF NOT EXISTS`. Nothing is dropped or recreated on later starts.
- **Seed data:** four demo classes in `schedule/seed.sql`, loaded only when the `classes` table is empty, so restarting never duplicates them.

## Project structure

```
app.py               starts Flask, creates the tables, seeds, registers both domains
db.py                SQLite connection (DATA_DIR) and table creation
schedule/            domain 1: schema.py, service.py, routes.py, seed.sql
bookings/            domain 2: schema.py, service.py, routes.py
templates/           classes.html, bookings.html
tests/               pytest tests for both service layers
Dockerfile           provided course template with its four TODOs filled in
ADR.md               architecture decision records
AI_USAGE.md          AI usage log
```

## Tests and coverage

Tests cover the business logic in `schedule/service.py`, `bookings/service.py` and `db.py`. Route files are excluded in `.coveragerc` because they only connect forms to the services. Each test runs on its own empty temporary database.

```
python -m pytest --cov=schedule --cov=bookings --cov=db --cov-report=term-missing
```

Result:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.16, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/ana-mariapintilie/DEVOPS/gym-booking
configfile: pytest.ini
testpaths: tests
plugins: cov-7.1.0
collected 27 items

tests/test_bookings.py ..............                                    [ 51%]
tests/test_schedule.py .............                                     [100%]

================================ tests coverage ================================
_______________ coverage: platform darwin, python 3.13.16-final-0 ______________

Name                   Stmts   Miss  Cover   Missing
----------------------------------------------------
bookings/__init__.py       0      0   100%
bookings/schema.py         1      0   100%
bookings/service.py       48      0   100%
db.py                     16      0   100%
schedule/__init__.py       0      0   100%
schedule/schema.py         1      0   100%
schedule/service.py       46      0   100%
----------------------------------------------------
TOTAL                    112      0   100%
============================== 27 passed in 0.10s ==============================
```

## Container contract evidence 

Output of the provided checker, `bash ../sdd-assignment-1/container/run.sh .`:

```
=== SDD Assignment 1 contract check ===
Repository: /Users/ana-mariapintilie/DEVOPS/gym-booking

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 244 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: gym.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: bookings=0 classes=4

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```