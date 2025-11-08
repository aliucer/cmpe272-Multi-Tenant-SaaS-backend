import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import redis

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Check your .env file.")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is not set. Check your .env file.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# === RLS tenant context helper ===
def set_current_tenant(db_session, tenant_id: str | None):
    """
    Set the tenant for the current DB session/transaction (affects RLS + server defaults).
    Call near the start of a request BEFORE any queries/inserts.
    """
    if tenant_id:
        db_session.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": tenant_id})
    else:
        db_session.execute(text("RESET app.current_tenant"))
