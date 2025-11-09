from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from .db import SessionLocal, engine, Base, redis_client
from .models import Note
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
def list_notes(db: Session = Depends(get_db)):
    return db.query(Note).order_by(Note.id).all()

@app.post("/notes", response_model=NoteOut, status_code=201)
def create_note(payload: NoteIn, db: Session = Depends(get_db)):
    note = Note(text=payload.text)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
