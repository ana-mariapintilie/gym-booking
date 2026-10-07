# Architecture Decision Records

## 1. Backend language and framework: Python with Flask
Date: 2026-10-01
Status: Decided
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
Status: Decided
Context: A booking must belong to a class, and members can be confirmed, waitlisted or cancelled. I needed to decide how to store this in SQLite.
Decision: bookings.class_id references classes.id with a foreign key, and a single status column (confirmed / waitlisted / cancelled) holds the booking state. Waitlist order comes from created_at.
Alternatives considered: A separate waitlist table. Rejected because moving someone up would mean deleting from one table and inserting into another; with one status column it is a single UPDATE. A position number column was rejected because every cancellation would require renumbering.
Consequences: The foreign key keeps data consistent now, but it ties the two tables to one database; when the domains become separate services in Assignment 2, this constraint will have to be replaced by checking the class through the schedule service.

## 4. Unit testing the service layer with pytest on a temporary database
Date: 2026-10-07
Status: Decided
Context: The assignment requires at least 70% coverage of core business logic. In my app the logic lives in schedule/service.py and bookings/service.py; the routes only read forms and show templates.
Decision: Test the service functions directly with pytest, giving every test its own empty SQLite file in a temporary folder (fixture in tests/conftest.py). Measure coverage with pytest-cov on schedule, bookings and db, and exclude routes.py through .coveragerc.
Alternatives considered: Testing through the web pages with Flask's test client, rejected because most of what it checks is HTML and redirects (framework glue), not my rules. Mocking the database, rejected because the waitlist order is decided inside the SQL query (ORDER BY created_at), so a mock would skip the part most likely to be wrong.
Consequences: The capacity, duplicate and waitlist rules are covered well, but the routes and templates are only tested by hand, so a typo in a form field name would not be caught by the tests.