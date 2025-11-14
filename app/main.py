import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from .db import SessionLocal, redis_client
from .api import health, auth, tenants, notes, users, billing, webhooks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------
# App lifespan
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        logger.info("✅ Postgres connection successful")
    except Exception as e:
        logger.error(f"❌ Postgres connection failed: {e}")
        raise

    try:
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise

    # IMPORTANT: schema is created via migration/SQL on Supabase; do not auto-create here.
    # Base.metadata.create_all(bind=engine)

    yield
    logger.info("Shutting down...")


# ---------------------------
# Application
# ---------------------------
app = FastAPI(title="Multi-Tenant SaaS API", lifespan=lifespan)

# Include all routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(notes.router)
app.include_router(users.router)
app.include_router(billing.router)
app.include_router(webhooks.router)