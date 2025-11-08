from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from . import admin, auth
from .db import SessionLocal, engine, Base, redis_client
from .models import User, Note
from .schemas import NoteIn, NoteOut
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# auto-create tables for learning/dev

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Test DB and Redis connections on startup"""
    # Startup: Test connections
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
    
    # Auto-create tables for learning/dev
    Base.metadata.create_all(bind=engine)
    
    yield  # App runs here
    
    # Shutdown: cleanup (if needed)
    logger.info("Shutting down...")

app = FastAPI(title="Basic Postgres Demo", lifespan=lifespan)

# --- Routers ---
app.include_router(admin.router)
app.include_router(auth.router)   # authentication routes

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="API with JWT-based authentication",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
        # Only protect selected routes
    protected_routes = [
        "/admin/ping",
        "/auth/me",
        "/notes"
    ]  # add more as needed

    for path, path_item in openapi_schema["paths"].items():
        for method in path_item.values():
            if path in protected_routes:
                method["security"] = [{"BearerAuth": []}]
            else:
                method["security"] = []
                
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        # Test Postgres
        db.execute(text("SELECT 1"))
        postgres_status = "ok"
    except Exception as e:
        postgres_status = f"error: {str(e)}"
    
    try:
        # Test Redis
        redis_client.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    return {
        "postgres": postgres_status,
        "redis": redis_status
    }

@app.get("/notes", response_model=list[NoteOut])
def list_notes(
    db: Session = Depends(get_db),
    current_user = Depends(auth.get_current_user),
    ):
    return db.query(Note).filter(Note.user_id == current_user.id).order_by(Note.id).all()

@app.post("/notes", response_model=NoteOut, status_code=201)
def create_note(
    payload: NoteIn, 
    db: Session = Depends(get_db),
    current_user = Depends(auth.get_current_user),
    ):
    '''
    note = Note(text=payload.text, user_id = current_user.id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
    '''
    from fastapi import HTTPException

    if not current_user:
        raise HTTPException(status_code=401, detail="User not authenticated")

    logger.info(f"Creating note for user_id={current_user.id}, text={payload.text}")

    try:
        note = Note(text=payload.text, user_id=current_user.id)
        db.add(note)
        db.commit()
        db.refresh(note)
        return note
    except Exception as e:
        logger.error(f"❌ Failed to create note: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")
