# Gym Class Booking

A booking app for a small gym (around 300 members). Staff publish group classes (yoga, spinning, boxing) with a limited number of spots, and members book a spot online instead of signing up on paper at the front desk. When a class is full, members join a waitlist and are moved up automatically when someone cancels.

Built with Python 3.13 and Flask, split into two services that each own a SQL Server database, with a static UI.

**Live:** https://apintilieieu2024ui.z1.web.core.windows.net (Azure, scales to zero: the first request after a quiet period can take up to a minute while the services and databases wake up).

The whole system is described in [`system.yaml`](system.yaml) (validated against [`system.schema.json`](system.schema.json)), and each service's API in `services/<name>/openapi.yaml`.

## Services and the seam

| Service | Folder | Owns | Database | Host port |
|---|---|---|---|---|
| Schedule | `services/schedule/` | Create and list classes (name, instructor, room, start time, duration, capacity) | `schedule` → table `classes` | 8001 |
| Bookings | `services/bookings/` | Book a spot, waitlist when full, cancel, promote the next waitlisted member | `bookings` → table `bookings` | 8002 |

The split into two services, each with its own Dockerfile, requirements and migrations, was made in commit [b23ac50](https://github.com/ana-mariapintilie/gym-booking/commit/b23ac506db2e00fbcc02724819165dd4765a3bc2).

**The seam:** bookings never reads the `classes` table. Server-side, it calls `GET {SCHEDULE_URL}/api/classes/<id>` (in `services/bookings/app/schedule_client.py`) to get a class's capacity before booking, and its name and time for the bookings page.

**When schedule is down or slow** (2 s timeout, `SCHEDULE_TIMEOUT_SECONDS`):
- Booking returns **503** with "Booking is paused…", and nothing is saved.
- The bookings list still loads (200): the UI shows the existing bookings with a notice that class details are unavailable.
- Cancelling and waitlist promotion keep working, because they only need the bookings database.

## Run it with Docker Compose

Requires Docker Desktop. On Apple Silicon, SQL Server runs under amd64 emulation (Rosetta), which Docker Desktop handles automatically.

```
git clone https://github.com/ana-mariapintilie/gym-booking.git
cd gym-booking
docker compose up --build
```

- UI: http://localhost:8080 (static files in `ui/`, served by a stock `nginx` image; "View" on a class opens its bookings)
- APIs: http://localhost:8001/api/classes (schedule) and http://localhost:8002/api/classes/1/bookings (bookings)
- Health: http://localhost:8001/health and http://localhost:8002/health (200 `{"status":"ok","db":"ok","version":"dev"}`, or 503 when the service can't read and write its own database)

The UI finds the services through `ui/config.js` (`scheduleUrl`, `bookingsUrl`); the deploy pipeline replaces that file with the Azure URLs. Each service only answers cross-origin requests from `CORS_ORIGINS`.

Startup order: `mssql` becomes healthy → `db-init` creates the `schedule` and `bookings` databases and one login for each (`db/init.sql`) and exits → both services apply their pending migrations and start. Bookings deliberately does not wait for schedule.

Each service logs one line per request, e.g. `INFO bookings POST /api/classes/1/bookings 201 38ms` (`docker compose logs -f bookings`).

To start over with empty databases: `docker compose down -v`.

### Run a single service

Each service only needs a SQL Server database. Start just the database and run one service on its own:

```
docker compose up -d mssql db-init
docker compose up --build schedule        # or: bookings
```

Or without Docker for the service itself (from `services/<name>/`, with the venv below):

```
export DATABASE_URL=mssql://schedule_user:ScheduleDev2026@localhost:1433/schedule
export PORT=8001 CORS_ORIGINS=http://localhost:8080
python -m app.main
```

Bookings started alone still works for listing and cancelling; booking answers 503 until it can reach `SCHEDULE_URL`.

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
| `CORS_ORIGINS` | each service | `http://localhost:8080` | The UI origin(s) allowed to call the service from a browser (comma-separated) |
| `GIT_SHA` | each service | `dev` | Version reported by `/health` (the pipeline sets the commit SHA) |

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
| bookings | `0003_add_status_changed_at.sql` | Adds `status_changed_at` in four steps (add as NULL, backfill from `created_at`, make NOT NULL, default `GETDATE()`); existing bookings are kept (tested in `test_status_changed_at_is_backfilled_for_existing_bookings`, and run on Azure on 21 Nov with Ana's and Luis's bookings in the table) |

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
services/bookings   43 passed   app/ coverage 98%   (__main__ block and the concurrent-duplicate backstop)
```

Bookings unit tests replace `schedule_client.get_class` with a fake, so they can also simulate an outage. `test_schedule_client.py` runs the real client against a local HTTP server that answers 200, 404, 500, invalid JSON, or too slowly (it checks that the timeout fires), and against a port with nothing listening.

### Cross-seam integration tests

`tests/integration/test_cross_seam.py` drives the real stack over HTTP. It creates a class in schedule, books it through bookings (confirmed, then waitlisted), and checks that unknown classes are rejected. It also runs `docker compose stop schedule` and checks that booking fails with a 503 in under 5 s, saves nothing, and works again after `docker compose start schedule`.

```
docker compose up -d --build
python -m pytest tests/integration -v      # 5 passed
```

## CI and images

`.github/workflows/ci.yml` runs on every push and pull request:

| Job | What it does |
|---|---|
| `contracts` | `system.yaml` against `system.schema.json` (check-jsonschema), both OpenAPI documents (openapi-spec-validator), and `scripts/check_system.py` (folders exist, the bookings → schedule call is in schedule's OpenAPI) |
| `test` (per service) | ruff, then the unit tests against a SQL Server service container; fails under 70% coverage |
| `integration` | `docker compose up --build --wait`, then `tests/integration` against the running stack |
| `images` (per service) | Builds `services/<name>/Dockerfile` every time; only on `main` it logs in to GHCR and pushes `ghcr.io/ana-mariapintilie/gym-booking-<name>:<commit SHA>` |

`images` waits for `contracts`, `test` and `integration`, so a broken commit never gets an image. Pull requests and other branches only build, so nothing is published from them. On `main`, CI is not triggered directly: `cd.yml` calls it.

## Deployment (Azure)

`.github/workflows/cd.yml` runs on every push to `main` (only reachable through a pull request):

1. Runs the whole of `ci.yml` (above), which pushes both images tagged with the commit SHA.
2. Logs in to Azure with OpenID Connect through a user-assigned managed identity: no Azure password is stored anywhere.
3. For each service: sets the Container App secret `database-url` (from the GitHub secrets `SCHEDULE_DB_PASSWORD` / `BOOKINGS_DB_PASSWORD`), then updates the app to the new image, min 0 / max 1 replicas, and its env vars (`DATABASE_URL=secretref:database-url`, `PORT`, `CORS_ORIGINS` = the UI origin, `GIT_SHA`, and for bookings `SCHEDULE_URL` + `SCHEDULE_TIMEOUT_SECONDS`).
4. Writes `ui/config.js` with the two HTTPS service URLs and uploads `ui/` to the storage account's `$web` container.
5. Calls `/health` on both services (up to 6 minutes, to allow for cold starts) and fails unless both answer `ok` with the new commit SHA.

| Resource | Name |
|---|---|
| Resource group (Germany West Central) | `rg-apintilie-ieu2024` |
| Container Apps environment (Consumption) | `apintilie-ieu2024-env` |
| Container Apps | `apintilie-ieu2024-schedule`, `apintilie-ieu2024-bookings` |
| Azure SQL server / databases (serverless, free offer) | `apintilie-ieu2024-sql` / `apintilie-ieu2024-schedule-db`, `apintilie-ieu2024-bookings-db` |
| Static website | storage account `apintilieieu2024ui` |
| Images | `ghcr.io/ana-mariapintilie/gym-booking-<service>:<sha>` (public packages) |

### Initial Azure setup (once, in Azure Cloud Shell)

Passwords are typed in when prompted and never written to the repo. Replace `<...>` with your own values.

```
az account set --subscription <subscription-id>
PREFIX=apintilie-ieu2024; RG=rg-$PREFIX; LOC=germanywestcentral

# Resource group, logs, Container Apps environment
az group create -n $RG -l $LOC
az monitor log-analytics workspace create -g $RG -n $PREFIX-logs -l $LOC
az containerapp env create -g $RG -n $PREFIX-env -l $LOC \
  --logs-workspace-id <workspace customerId> --logs-workspace-key <workspace key>

# SQL server and one serverless (free offer) database per service
az sql server create -g $RG -n $PREFIX-sql -l $LOC -u <admin-user> -p <admin-password>
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n AllowAzure \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for svc in schedule bookings; do
  az sql db create -g $RG -s $PREFIX-sql -n $PREFIX-$svc-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 2 \
    --use-free-limit --free-limit-exhaustion-behavior AutoPause
done
# In each database (sqlcmd as admin): a contained user that only has rights there, e.g.
#   CREATE USER schedule_user WITH PASSWORD = '<password>';
#   ALTER ROLE db_ddladmin ADD MEMBER schedule_user;
#   ALTER ROLE db_datareader ADD MEMBER schedule_user;
#   ALTER ROLE db_datawriter ADD MEMBER schedule_user;

# One Container App per service (CD replaces the image on the first deploy)
for svc in schedule bookings; do
  az containerapp create -g $RG -n $PREFIX-$svc --environment $PREFIX-env \
    --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1
done

# Static website for the UI
az storage account create -g $RG -n apintilieieu2024ui -l $LOC --sku Standard_LRS --kind StorageV2
az storage blob service-properties update --account-name apintilieieu2024ui \
  --static-website --index-document index.html

# Identity GitHub Actions logs in as (OIDC, no secret)
az identity create -g $RG -n $PREFIX-deployer
az role assignment create --assignee <identity principalId> --role Contributor \
  --scope $(az group show -n $RG --query id -o tsv)
az identity federated-credential create -g $RG --identity-name $PREFIX-deployer -n github-main \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:ana-mariapintilie/gym-booking:ref:refs/heads/main \
  --audiences api://AzureADTokenExchange
```

Then in GitHub (Settings → Secrets and variables → Actions):
- Secrets: `AZURE_CLIENT_ID` (the identity's clientId), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `SCHEDULE_DB_PASSWORD`, `BOOKINGS_DB_PASSWORD`.
- Variables: `PREFIX=apintilie-ieu2024`, `RESOURCE_GROUP=rg-apintilie-ieu2024`, `UI_STORAGE=apintilieieu2024ui`.

After the first CD run, make both GHCR packages public (or give the Container Apps registry credentials) so Azure can pull them.

### Operating it

- Health: `https://<container app FQDN>/health` → `{"status":"ok","db":"ok","version":"<commit SHA>"}`.
- Logs (one line per request, plus migration lines at startup): `az containerapp logs show -n apintilie-ieu2024-bookings -g rg-apintilie-ieu2024 --tail 100`, or in Log Analytics: `ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'apintilie-ieu2024-bookings'`.
- A failed deploy leaves the CD run red at the health-check step; fix it with a new commit through a pull request.

## Project structure

```
docker-compose.yml          mssql + db-init + schedule + bookings + ui (nginx)
system.yaml                 the whole system: services, env vars, calls, Azure names
system.schema.json          schema system.yaml must follow (given by the course)
scripts/check_system.py     checks system.yaml against the repo (run in CI)
.github/workflows/          ci.yml (every push and PR), cd.yml (main only: deploy to Azure)
ui/                         static UI (index.html, class.html, app.js, config.js)
db/init.sql                 one database and one login per service
services/schedule/          Dockerfile, openapi.yaml, requirements*.txt, migrations/, app/, tests/
services/bookings/          Dockerfile, openapi.yaml, requirements*.txt, migrations/, app/, tests/
  app/main.py               routes, /health, startup migrations
  app/service.py            business rules
  app/migrate.py            migration runner
  app/request_log.py        one log line per request
  app/cors.py               allows only CORS_ORIGINS to call the API from a browser
  app/schedule_client.py    (bookings only) the call across the seam
tests/integration/          cross-seam tests against the running stack
ADR.md                      architecture decision records
AI_USAGE.md                 AI usage log
```
