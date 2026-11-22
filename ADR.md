# Architecture Decision Records

## 1. Backend language and framework: Python with Flask
Date: 2026-10-01
Status: Superseded by 7
Context: The gym booking app needs a small web backend that serves HTML pages and stores data in SQLite, runs as one process, and that I can explain myself. Python is the language I am most comfortable in.
Decision: Use Python 3.13 with Flask, rendering pages with Flask's built-in Jinja templates and talking to SQLite through Python's standard `sqlite3` module.
Alternatives considered: Django was rejected because its ORM, admin panel and project structure are much more than an app with two small domains needs, and would add a lot of code I would have to explain. FastAPI was rejected because it is mainly designed for JSON APIs; I want server-rendered pages, and Flask's templates make that simpler.
Consequences: Flask gives no built-in ORM or migrations, so I create the tables myself with SQL at startup. In exchange the app stays small, has few dependencies, and its code is easy to test with Flask's test client.

## 2. Splitting the app into a schedule domain and a bookings domain
Date: 2026-10-04
Status: Decided
Context: Assignment 2 will split this app into separate services, so the two feature domains must already be logically separable inside one process.
Decision: Each domain lives in its own package (schedule/ and bookings/) and owns its own table. Bookings only needs one thing from schedule: a class's capacity, looked up by class_id.
Alternatives considered: One shared models file with all tables and logic together. Rejected because bookings code could then freely read and change classes, and splitting it later would mean untangling everything.
Consequences: The future service boundary is clear (one request: "what is the capacity of class X?"). The cost is a little duplication, e.g. each package has its own schema file.

## 3. Linking bookings to classes with a foreign key and a status column
Date: 2026-10-04
Status: Superseded by 6
Context: A booking must belong to a class, and members can be confirmed, waitlisted or cancelled. I needed to decide how to store this in SQLite.
Decision: bookings.class_id references classes.id with a foreign key, and a single status column (confirmed / waitlisted / cancelled) holds the booking state. Waitlist order comes from created_at.
Alternatives considered: A separate waitlist table. Rejected because moving someone up would mean deleting from one table and inserting into another; with one status column it is a single UPDATE. A position number column was rejected because every cancellation would require renumbering.
Consequences: The foreign key keeps data consistent now, but it ties the two tables to one database; when the domains become separate services in Assignment 2, this constraint will have to be replaced by checking the class through the schedule service.

## 4. Unit testing the service layer with pytest on a temporary database
Date: 2026-10-07
Status: Superseded by 9
Context: The assignment requires at least 70% coverage of core business logic. In my app the logic lives in schedule/service.py and bookings/service.py; the routes only read forms and show templates.
Decision: Test the service functions directly with pytest, giving every test its own empty SQLite file in a temporary folder (fixture in tests/conftest.py). Measure coverage with pytest-cov on schedule, bookings and db, and exclude routes.py through .coveragerc.
Alternatives considered: Testing through the web pages with Flask's test client, rejected because most of what it checks is HTML and redirects (framework glue), not my rules. Mocking the database, rejected because the waitlist order is decided inside the SQL query (ORDER BY created_at), so a mock would skip the part most likely to be wrong.
Consequences: The capacity, duplicate and waitlist rules are covered well, but the routes and templates are only tested by hand, so a typo in a form field name would not be caught by the tests.

## 5. Not building login or user accounts
Date: 2026-10-09
Status: Decided
Context: Right now anyone who opens the app can create classes, book a spot and cancel any booking. A real gym would want staff and members to log in.
Decision: I didn't build authentication on purpose. Members identify themselves with a name and email when booking, and the classes page is not protected.
Alternatives considered: Login with Flask-Login, a users table and hashed passwords. Rejected because it would be a third domain with its own data, add dependencies, and require handling passwords safely, which is more than the two domains this assignment is about and would take time away from tests and documentation.
Consequences: Anyone with access could cancel someone else's booking or add classes, so the app should only run on the gym's internal network for now. Authentication could become its own service in Assignment 2, and bookings already store the member's email, which a future user account could link to.

## 6. Splitting along the existing seam: bookings asks schedule over HTTP
Date: 2026-11-18
Status: Decided
Context: Assignment 2 requires one service per domain, each with its own database. In Assignment 1 the only contact between the domains was get_class_capacity(class_id) (ADR-2), plus a foreign key from bookings.class_id to classes.id (ADR-3).
Decision: The seam stays where ADR-2 put it. The schedule service owns classes and exposes GET /api/classes/<id>; the bookings service calls it server side from schedule_client.get_class() before every booking, with a 2-second timeout (SCHEDULE_TIMEOUT_SECONDS). If schedule is down, slow or answers with an error, booking returns 503 "Booking is paused" and saves nothing, while the bookings list and cancelling keep working because they only need the bookings database.
Alternatives considered: Letting the UI call both services and pass the capacity to bookings, rejected because a browser could then send any capacity and overbook a class; the capacity must come from schedule, server side. Retrying the call to schedule, rejected because a member waiting several seconds is worse than a clear "try again in a minute".
Consequences: ADR-2 held: only one call crosses the seam, so the split needed no redesign. The cost is that booking now depends on schedule being up, and that the bookings page shows the class name only when schedule answers.

## 7. One SQL Server database per service, with numbered migrations run at startup
Date: 2026-11-21
Status: Decided
Context: After the split each service must own its data, and the schema must be able to change after the tables already hold real bookings. SQLite (ADR-1) was a single file inside one container, which does not work once there are two services and the containers on Azure can be replaced or scaled to zero at any time.
Decision: Each service has its own database (schedule and bookings) and its own login, which only has rights on that one database, so bookings cannot read or change classes even by mistake. Locally both databases run in one SQL Server 2022 container; on Azure they are two databases on one Azure SQL server (serverless, free offer). Schema changes are numbered files (0001_..., 0002_...) in services/<name>/migrations. On every start, migrate.py runs the files whose number is not in the schema_migrations table yet, in order, each one in its own transaction. Changes to tables with data follow "expand, then contract": migration 0003 adds bookings.status_changed_at as NULL, fills it from created_at for the existing rows, and only then makes it NOT NULL with a default.
Alternatives considered: One shared database with a schema per service, rejected because one login could then still reach the other service's tables, and both services would have to stop if the database had to change. An ORM migration tool like Alembic, rejected because it brings SQLAlchemy and auto-generated files I would have to explain; plain SQL files are easier to read and review. Dropping and recreating tables, rejected because it deletes the existing bookings.
Consequences: The schema is the same everywhere because it comes from the same files, and 0003 proved on Azure that existing bookings are kept (before/after evidence in the report). Because the new column has a default, the old version of the code still works while a new revision starts. Recovery plan: a failing migration is rolled back and not recorded, the container does not become healthy, and the CD health check fails, so I fix it with a new commit. Migrations are never edited after they reached main; to undo one I write a new migration. If data is lost, Azure SQL's automatic backups allow a point-in-time restore. The cost is that two databases must be created and their logins managed, and nothing in the database stops a booking for a class that does not exist; bookings checks that through schedule (ADR-6).

## 8. Running on serverless Azure: Container Apps, Azure SQL serverless and a static website
Date: 2026-11-21
Status: Decided
Context: The system has to be live on Azure with as little cost as possible, on a student subscription that only allows a few regions (I use Germany West Central).
Decision: Each service runs as an Azure Container App on the Consumption plan with min 0 and max 1 replicas, pulling SHA-tagged images from GHCR. The databases are Azure SQL serverless (free offer), which pauses when nobody uses it. The UI is plain HTML and JS in an Azure Storage static website ($web), and config.js tells it the service URLs. Logs go to Log Analytics.
Alternatives considered: Azure App Service, rejected because a plan is paid while it is running even with no visitors and does not scale to zero. AKS (Kubernetes), rejected because it is much more to set up and pay for than two small services need. Serving the UI from one of the Flask services, rejected because then the UI would go down with that service and it would not be a static site.
Consequences: With no traffic it costs close to nothing. The price is cold starts: after some idle time the first request waits for the container to start and the database to resume, and Azure answers "App port is not ready" (503) in the meantime. The UI waits up to 30 seconds and shows a "waking up" message instead of an error. With 100x the users I would set min replicas to 1 (no cold starts, but it costs money all the time), raise max replicas so each service scales on its own (bookings gets more traffic than schedule), move the databases to a paid tier that does not pause, and add a short cache in bookings for class capacities to reduce calls to schedule.

## 9. CI on every push and pull request, CD only from main, tests against a real SQL Server
Date: 2026-11-22
Status: Decided
Context: With two services, a UI and Azure, a change can break things that one person testing by hand would miss: a migration, the call between the services, or the deployment itself. ADR-4 tested the logic against SQLite files, which no longer exist.
Decision: ci.yml runs on every push to a branch and on every pull request. It checks system.yaml against system.schema.json and both OpenAPI files, runs ruff and the unit tests of each service against a real SQL Server container with at least 70% coverage, starts the whole stack with Docker Compose for the cross-seam tests (including stopping schedule to check the 503), and builds both images. cd.yml runs only on pushes to main: it calls ci.yml first, then deploys the images tagged with the commit SHA, uploads the UI, and only passes when /health on both services answers ok with that SHA. GitHub logs in to Azure with OIDC and a managed identity, so no Azure password exists; the two database passwords are GitHub secrets. Work happens on branches and reaches main through pull requests.
Alternatives considered: Mocking the database in unit tests, rejected because the waitlist order and the one-active-booking rule live in SQL. Deploying from every branch, rejected because there is only one environment and it must always match main. Storing an Azure service principal secret in GitHub, rejected because OIDC needs no secret that could leak or expire.
Consequences: Nothing reaches Azure without passing every test, and a failed run is visible: PR #1 failed because the cache could not be saved and PR #5 fixed it. A full CD run takes about 4 minutes. docker-compose.yml and ci.yml still contain default passwords for the local SQL Server container; they only work on a developer's own machine or a throwaway CI runner, can be overridden with a .env file, and are never used on Azure. Tests need Docker running, which is slower than SQLite.

## 10. What I did not build
Date: 2026-11-22
Status: Decided
Context: The assignment is about splitting, shipping and operating two services with as little cost and complexity as possible, so I had to choose what to leave out.
Decision: I did not build: login (ADR-5 still holds), messaging or a queue between the services, retries or a circuit breaker on the call to schedule, a staging environment, infrastructure as code (Bicep or Terraform), Azure Key Vault, or a custom domain.
Alternatives considered: A queue so bookings could be accepted while schedule is down and checked later, rejected because members would not know if their spot is real, and a clear 503 is honest (ADR-6). Bicep for the Azure setup, rejected for time; the README lists the exact az commands instead. Key Vault, rejected because only two secrets exist and Container App secrets already keep them out of the code.
Consequences: Anyone with the UI link can book or cancel any booking, so the system is a demo, not a real gym system. If schedule is down, booking stops until it is back. Rebuilding the Azure setup means running the README commands by hand, and a bad deploy reaches users directly, without a staging step; the CD health check is the only safety net.
