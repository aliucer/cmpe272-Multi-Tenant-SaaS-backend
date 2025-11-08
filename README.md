# cmpe272-Multi-Tenant-SaaS-backend

A minimal FastAPI backend demo for note-taking, now with user authentication.
It uses JWT-based authentication, PostgreSQL, and SQLAlchemy ORM.
This project serves as a foundation for building multi-tenant SaaS applications.

## Features
- FastAPI service exposing REST endpoints for notes
- PostgreSQL database (connection via `DATABASE_URL`)
- SQLAlchemy ORM models and session management
- Pydantic v2 schemas for request/response validation
- Auto-creates tables on startup for development
- User authentication (JWT-based)
- Public routes and protected routes (require Bearer token)

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
- `app/db.py` — DB engine/session setup
- `app/models.py` — SQLAlchemy ORM models
- `app/schemas.py` — Pydantic schemas
- `requirements.txt` — Python dependencies

## Notes
- Tables are auto-created on startup for dev; no migrations are configured.
- Multi-tenancy and authentication are implemented.
- For production, add migrations (e.g., Alembic) and proper secrets management.

## Acces the API
- Swagger UI: http://localhost:8000/docs
- Redoc: http://localhost:8000/redoc

## License
MIT