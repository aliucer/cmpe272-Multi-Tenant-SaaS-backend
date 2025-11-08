from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr

# --- Notes ---

class NoteIn(BaseModel):
    text: str

class NoteOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Users ---

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

