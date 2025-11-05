# app/admin.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from .db import engine

router = APIRouter(prefix="/admin/db", tags=["Admin"])

@router.get("/overview")
def db_overview():
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
