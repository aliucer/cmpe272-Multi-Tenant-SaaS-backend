from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NoteIn(BaseModel):
    text: str

class NoteOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
