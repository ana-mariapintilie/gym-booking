# Gym Class Booking

A booking app for a small gym (around 300 members). Staff publish group classes (yoga, spinning, boxing) with a limited number of spots, and members book a spot online instead of signing up on paper at the front desk. When a class is full, members join a waitlist and are moved up automatically when someone cancels.

Built with Python 3.13 and Flask, split into two services that each own a SQL Server database.

## Services and the seam

| Service | Folder | Owns | Database | Host port |
|---|---|---|---|---|
| Schedule | `services/schedule/` | Create and list classes (name, instructor, room, start time, duration, capacity) | `schedule` → table `classes` | 8001 |
| Bookings | `services/bookings/` | Book a spot, waitlist when full, cancel, promote the next waitlisted member | `bookings` → table `bookings` | 8002 |

**The seam:** bookings never reads the `classes` table. Server-side, it calls `GET {SCHEDULE_URL}/api/classes/<id>` (in `services/bookings/app/schedule_client.py`) to get a class's capacity before booking, and its name and time for the bookings page.

**When schedule is down or slow** (2 s timeout, `SCHEDULE_TIMEOUT_SECONDS`):
- Booking returns **503** with "Booking is paused…", and nothing is saved.
- The bookings page still loads (200) and shows the existing bookings, with a notice that class details are unavailable.
- Cancelling and waitlist promotion keep working, because they only need the bookings database.

## Run it with Docker Compose

Requires Docker Desktop. On Apple Silicon, SQL Server runs under amd64 emulation (Rosetta), which Docker Desktop handles automatically.

```
git clone https://github.com/ana-mariapintilie/gym-booking.git
cd gym-booking
docker compose up --build
```

- Classes: http://localhost:8001/classes
- Bookings: follow "View" on a class, or http://localhost:8002/classes/1/bookings
- Health: http://localhost:8001/health and http://localhost:8002/health (200 `{"status":"ok"}`, or 503 when the service's database is unreachable)

Startup order: `mssql` becomes healthy → `db-init` creates the `schedule` and `bookings` databases and one login for each (`db/init.sql`) and exits → both services apply their pending migrations and start. Bookings deliberately does not wait for schedule.

Each service logs one line per request, e.g. `INFO bookings POST /classes/1/bookings 302 38ms` (`docker compose logs -f bookings`).

To start over with empty databases: `docker compose down -v`.

## Configuration

Compose has development defaults, so no `.env` is needed locally. Override them with environment variables anywhere else.

| Variable | Used by | Default (compose) | Purpose |
|---|---|---|---|
| `MSSQL_SA_PASSWORD` | mssql, db-init | `GymBooking_Dev_2026` | SQL Server admin password |
| `SCHEDULE_DB_PASSWORD` / `BOOKINGS_DB_PASSWORD` | db-init, services | `ScheduleDev2026` / `BookingsDev2026` | Per-service login passwords |
| `DATABASE_URL` | each service | `mssql://<svc>_user:…@mssql:1433/<svc>` | The service's own database |
| `PORT` | each service | `8000` | Port inside the container |
| `SCHEDULE_URL` | bookings | `http://schedule:8000` | Where bookings calls schedule (server-side) |
| `SCHEDULE_TIMEOUT_SECONDS` | bookings | `2` | Timeout for that call |
| `SCHEDULE_PUBLIC_URL` / `BOOKINGS_PUBLIC_URL` | bookings / schedule | `http://localhost:8001` / `:8002` | Browser links between the two UIs |

## Database migrations

Each service has versioned SQL files in `services/<name>/migrations/` (`0001_name.sql`, `0002_…`). On startup, `app/migrate.py`:

1. creates `schema_migrations (version, name, applied_at)` if it is missing,
2. applies **only** the files whose version is not recorded there, in order, each in its own transaction together with its `schema_migrations` row (a failing file is rolled back and not recorded),
3. retries the connection while SQL Server is still starting.

Nothing is dropped or recreated on boot.

| Service | Migration | What it does to existing data |
|---|---|---|
| schedule | `0001_create_classes.sql` | Creates the table |
| schedule | `0002_seed_demo_classes.sql` | Inserts 4 demo classes only if the table is empty |
| schedule | `0003_add_room_to_classes.sql` | Adds `room`; existing classes are kept and get `Main studio` (tested in `test_adding_room_keeps_existing_classes`) |
| bookings | `0001_create_bookings.sql` | Creates the table; no foreign key to `classes`, which lives in the other database |
| bookings | `0002_one_active_booking_per_member.sql` | Unique filtered index on active bookings; existing rows are kept (tested in `test_unique_index_keeps_existing_bookings`) |

To change a schema, add a new numbered file. Never edit a file that has already been applied.

## Tests and coverage

The unit tests run against the Compose SQL Server, using throwaway `*_test` databases created by the tests, so start it first:

```
docker compose up -d mssql
python3.13 -m venv venv && source venv/bin/activate
pip install -r services/schedule/requirements-dev.txt   # same pins for both services

cd services/schedule && python -m pytest --cov --cov-report=term-missing && cd ../..
cd services/bookings && python -m pytest --cov --cov-report=term-missing && cd ../..
```

Results:

```
services/schedule   29 passed   app/ coverage 99%   (only the __main__ block is missed)
services/bookings   41 passed   app/ coverage 98%   (__main__ block and the concurrent-duplicate backstop)
```

Bookings unit tests replace `schedule_client.get_class` with a fake, so they can also simulate an outage. `test_schedule_client.py` runs the real client against a local HTTP server that answers 200, 404, 500, invalid JSON, or too slowly (it checks that the timeout fires), and against a port with nothing listening.

### Cross-seam integration tests

`tests/integration/test_cross_seam.py` drives the real stack over HTTP. It creates a class in schedule, books it through bookings (confirmed, then waitlisted), and checks that unknown classes are rejected. It also runs `docker compose stop schedule` and checks that booking fails with a 503 in under 5 s, saves nothing, and works again after `docker compose start schedule`.

```
docker compose up -d --build
python -m pytest tests/integration -v      # 5 passed
```

## Project structure

```
docker-compose.yml          mssql + db-init + schedule + bookings
db/init.sql                 one database and one login per service
services/schedule/          Dockerfile, requirements*.txt, migrations/, app/, tests/
services/bookings/          Dockerfile, requirements*.txt, migrations/, app/, tests/
  app/main.py               routes, /health, startup migrations
  app/service.py            business rules
  app/migrate.py            migration runner
  app/request_log.py        one log line per request
  app/schedule_client.py    (bookings only) the call across the seam
tests/integration/          cross-seam tests against the running stack
ADR.md                      architecture decision records
AI_USAGE.md                 AI usage log
```
