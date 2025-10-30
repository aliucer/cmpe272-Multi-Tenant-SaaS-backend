## Purpose
Make it quick for an AI coding assistant to be productive in this repository: this file captures the minimal architecture, developer workflows, conventions, and specific examples to avoid guesswork.

## Big picture (what this repo is)
- A small FastAPI service exposing a simple Notes API (see `app/main.py`).
- SQLAlchemy ORM backed by Postgres; DB connection configured through the `DATABASE_URL` environment variable (`app/db.py`).
- Pydantic v2 models are used for request/response schemas (`app/schemas.py`) and are configured to read ORM attributes.
- The repo currently contains a single `Note` model (`app/models.py`) and uses `Base.metadata.create_all(...)` in `app/main.py` to auto-create tables during dev.

## Key files to consult
- `app/main.py` — API routes, `get_db()` dependency, and dev-oriented `Base.metadata.create_all(bind=engine)` call.
- `app/db.py` — `engine`, `SessionLocal`, `Base`. Uses `DATABASE_URL` and `pool_pre_ping=True`.
- `app/models.py` — SQLAlchemy ORM models (example: `Note`).
- `app/schemas.py` — Pydantic models (example: `NoteIn`, `NoteOut`). Note: `NoteOut` uses `ConfigDict(from_attributes=True)` so response models are populated from ORM instances.
- `requirements.txt` — runtime dependencies (FastAPI, uvicorn, SQLAlchemy 2.x, psycopg2-binary, pydantic v2).

## Run / dev workflow (explicit)
1. Install dependencies from `requirements.txt` (pip). The environment expects a Postgres connection string in `DATABASE_URL`.
2. Run the app for development with an explicit call. Example (from repo root):

   ```bash
   export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
   python -m uvicorn app.main:app --reload
   ```

3. The app will create tables automatically on startup (dev only) because `Base.metadata.create_all(bind=engine)` is executed in `app/main.py`. Do not assume this for production — migrations are not configured.

## Coding conventions & patterns to follow
- DB sessions: use the `get_db()` dependency in `app/main.py` which yields `SessionLocal()` and closes it in a finally block.
- Unit-of-work: handler functions create objects, `db.add(...)`, then `db.commit()` followed by `db.refresh(obj)` to return the persisted instance (see `create_note`).
- Response models: routes declare `response_model=...` and rely on Pydantic `from_attributes=True` to read SQLAlchemy model attributes.
- Engine/session config: `SessionLocal` uses `autoflush=False` and `autocommit=False` — preserve this behavior when refactoring.

## Integration and environment notes
- The service expects `DATABASE_URL` (Postgres). The repo includes `python-dotenv` in `requirements.txt` but there is no `.env` loader in `app/main.py` — if you add one, be explicit where `.env` is loaded.
- Uses `psycopg2-binary` driver (packaged in `requirements.txt`).

## Important gotchas & current limitations (do not assume)
- This repo's title references multi-tenant SaaS, but the current code is a simple single-tenant Note demo. There are no tenant isolation or auth patterns present — flag this before adding multi-tenant features.
- There are no DB migrations configured (no Alembic). Relying on `create_all()` is fine for demos but not for production.

## Small examples to copy/paste
- Get DB session: see `get_db()` in `app/main.py` — yield `SessionLocal()` and `finally: db.close()`.
- Create pattern (use commit+refresh):

  ```py
  note = Note(text=payload.text)
  db.add(note)
  db.commit()
  db.refresh(note)
  return note
  ```

## When to ask the repo owner
- If you need multi-tenant behavior, ask for the intended tenant identifier and storage strategy.
- If you need migrations or CI deployment, ask whether to add Alembic and about production DB setup (managed Postgres, credentials handling).

## Quick checklist for changes
- Preserve `get_db()` pattern and session config.
- Keep `from_attributes=True` on response schemas (Pydantic v2) when returning ORM objects.
- Do not remove `pool_pre_ping=True` on engine without discussing connection stability with the owner.

If anything here is unclear or you want a different focus (tests, CI, or multi-tenant design), tell me which area to expand.
