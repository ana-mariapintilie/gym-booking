# Architecture Decision Records

## 1. Backend language and framework: Python with Flask
Date: 2026-10-01
Status: Decided
Context: The gym booking app needs a small web backend that serves HTML pages and stores data in SQLite, runs as one process, and that I can explain myself. Python is the language I am most comfortable in.
Decision: Use Python 3.13 with Flask, rendering pages with Flask's built-in Jinja templates and talking to SQLite through Python's standard `sqlite3` module.
Alternatives considered: Django was rejected because its ORM, admin panel and project structure are much more than an app with two small domains needs, and would add a lot of code I would have to explain. FastAPI was rejected because it is mainly designed for JSON APIs; I want server-rendered pages, and Flask's templates make that simpler.
Consequences: Flask gives no built-in ORM or migrations, so I create the tables myself with SQL at startup. In exchange the app stays small, has few dependencies, and its code is easy to test with Flask's test client.
