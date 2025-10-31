from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from .db import SessionLocal, engine, Base
from .models import Note
from .schemas import NoteIn, NoteOut
from .admin import router as admin_router

# auto-create tables for learning/dev
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Basic Postgres Demo")
app.include_router(admin.router)
app.include_router(notes.router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
