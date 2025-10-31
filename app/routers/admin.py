# app/admin.py
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy import text, inspect
from .db import engine
import os
import json

router = APIRouter(prefix="/admin/db", tags=["Admin"])

# --- Basic token-based guard ---
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "supersecret")

# DO NOT expose this publicly in production (protect w/ auth/role checks!)
def verify_admin(x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

@router.get("/overview", dependencies=[Depends(verify_admin)])
def db_overview():
    db_type = engine.url.get_backend_name()

    with engine.connect() as conn:
        # DB version / name (SQLite safe)
        try:
            version = conn.execute(text("SELECT version();")).scalar_one()
        except Exception:
            version = "SQLite (no version query available)"

        try:
            current_db = conn.execute(text("SELECT current_database();")).scalar_one()
        except Exception:
            current_db = "sqlite_local"

        # List tables
        insp = inspect(engine)
        tables = insp.get_table_names()

        # Approx stats (Postgres only)
        stats = []
        if db_type == "postgresql":
            stats = conn.execute(text("""
                SELECT
                    n.nspname AS schema,
                    c.relname AS table,
                    c.reltuples::BIGINT AS approx_rows,
                    pg_total_relation_size(c.oid) AS total_bytes,
                    pg_relation_size(c.oid) AS table_bytes,
                    pg_indexes_size(c.oid) AS index_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'
                ORDER BY total_bytes DESC;
            """)).mappings().all()

    return {
        "db_type": db_type,
        "db": current_db,
        "version": version,
        "tables": tables,
        "stats": [
            {
                "table": s["table"],
                "approx_rows": int(s["approx_rows"]),
                "total_bytes": int(s["total_bytes"]),
                "table_bytes": int(s["table_bytes"]),
                "index_bytes": int(s["index_bytes"]),
            } for s in stats
        ] if stats else "No stats (SQLite)"
    }

'''
@router.get("/overview", dependencies=[Depends(verify_admin)])
def db_overview():
    db_type = engine.url.get_backend_name()
    # DO NOT expose this publicly in production (protect w/ auth/role checks!)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar_one()
        current_db = conn.execute(text("SELECT current_database();")).scalar_one()

        # List user tables in public schema
        tables = conn.execute(text("""
          SELECT table_name
          FROM information_schema.tables
          WHERE table_schema='public' AND table_type='BASE TABLE'
          ORDER BY table_name
        """)).fetchall()
        table_names = [t[0] for t in tables]

        # Per-table approx row count + sizes (fast, uses stats)
        stats = conn.execute(text("""
          SELECT
            n.nspname AS schema,
            c.relname AS table,
            c.reltuples::BIGINT AS approx_rows,
            pg_total_relation_size(c.oid) AS total_bytes,
            pg_relation_size(c.oid) AS table_bytes,
            pg_indexes_size(c.oid) AS index_bytes
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
          ORDER BY total_bytes DESC;
        """)).mappings().all()

    return {
        "db": current_db,
        "version": version,
        "tables": table_names,
        "stats": [
            {
              "table": s["table"],
              "approx_rows": int(s["approx_rows"]),
              "total_bytes": int(s["total_bytes"]),
              "table_bytes": int(s["table_bytes"]),
              "index_bytes": int(s["index_bytes"]),
            } for s in stats
        ]
    }
'''

# --- List all tables ---
@router.get("/tables", dependencies=[Depends(verify_admin)])
def list_tables():
    insp = inspect(engine)
    return insp.get_table_names()


# --- Preview rows from a table ---
@router.get("/tables/{table_name}/preview", dependencies=[Depends(verify_admin)])
def preview_rows(table_name: str, limit: int = 10):
    with engine.connect() as conn:
        try:
            rows = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}")).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


# --- Table row counts ---
@router.get("/stats", dependencies=[Depends(verify_admin)])
def table_stats():
    insp = inspect(engine)
    result = {}
    with engine.connect() as conn:
        for t in insp.get_table_names():
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                result[t] = count
            except Exception:
                result[t] = "Error or unsupported"
    return result


# --- Backup database to JSON ---
@router.get("/backup", dependencies=[Depends(verify_admin)])
def backup_db():
    insp = inspect(engine)
    data = {}
    with engine.connect() as conn:
        for t in insp.get_table_names():
            rows = conn.execute(text(f"SELECT * FROM {t}")).mappings().all()
            data[t] = [dict(r) for r in rows]
    with open("backup.json", "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "ok", "tables": len(data), "file": "backup.json"}