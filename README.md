# cmpe272-Multi-Tenant-SaaS-backend

A minimal FastAPI backend demo for note-taking, using PostgreSQL and SQLAlchemy ORM. This project is a starting point for building multi-tenant SaaS applications, but currently implements a single-tenant Notes API for learning and prototyping.

## Features
- FastAPI service exposing REST endpoints for notes
- PostgreSQL database (connection via `DATABASE_URL`)
- SQLAlchemy ORM models and session management
- Pydantic v2 schemas for request/response validation
- Auto-creates tables on startup for development

## Quickstart
1. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```
2. **Set up your database connection:**
	```bash
	export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
	```
3. **Run the development server:**
	```bash
	python -m uvicorn app.main:app --reload
	```

## API Endpoints
- `GET /health` — Health check (verifies DB connection)
- `GET /notes` — List all notes
- `POST /notes` — Create a new note (body: `{ "text": "..." }`)

## Project Structure
- `app/main.py` — FastAPI app, routes, DB session dependency
- `app/models.py` — SQLAlchemy ORM models
- `app/db.py` — DB engine/session setup
- `app/schemas.py` — Pydantic schemas
- `requirements.txt` — Python dependencies

## Notes
- Tables are auto-created on startup for dev; no migrations are configured.
- Multi-tenancy and authentication are **not** implemented yet.
- For production, add migrations (e.g., Alembic) and proper secrets management.
- 
## Benchmark Result (Updated)
- POST /auth/login: 8 requests avg 441 ms; p50 441 ms; p95 455 ms; max 459 ms
- POST /notes: 20 requests avg 457 ms; p50 455 ms; p95 478 ms; max 548 ms 
- GET /notes?limit=10: 20 requests avg 334 ms; p50 329 ms; p95 364 ms; max 396 ms 
- GET /users: 10 requests avg 634 ms; p50 631 ms; p95 662 ms; max 673 ms
- GET /health: 426 ms
- POST/tenants: 1,639 ms
