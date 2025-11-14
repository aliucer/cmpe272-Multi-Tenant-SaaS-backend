from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from ..schemas import NoteIn, NoteOut
from ..models import Note
from ..core.dependencies import get_current_user, get_db_jwt

router = APIRouter(tags=["notes"])


@router.get("/notes", response_model=List[NoteOut])
def list_notes(limit: int = 50, offset: int = 0, user=Depends(get_current_user), db: Session = Depends(get_db_jwt)):
    limit = min(max(limit, 1), 100)
    rows = db.query(Note).order_by(Note.created_at.desc()).limit(limit).offset(offset).all()
    return [NoteOut.model_validate(r) for r in rows]


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(payload: NoteIn, user=Depends(get_current_user), db: Session = Depends(get_db_jwt)):
    note = Note(title=payload.title, body=payload.body)  # tenant_id via server_default/GUC
    db.add(note)
    db.flush()          # forces INSERT; server_default fills tenant_id/created_at
    db.refresh(note)    # still same txn; RLS ok because SET LOCAL is active
    out = NoteOut.model_validate(note)
    db.commit()         # commit after we have the data
    return out
