from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

# ---- Generic ----
class HealthOut(BaseModel):
    postgres: str  # "ok" or "error: <msg>"
    redis: str     # "ok" or "error: <msg>"

class OkOut(BaseModel):
    ok: bool = True

# ---- Tenants ----
class TenantCreate(BaseModel):
    name: str
    admin_email: EmailStr
    admin_password: str
    
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: Literal["user", "admin"] = "user"  # default non-admin
    
class TenantCreated(BaseModel):
    tenant_id: UUID

# ---- Auth ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    refresh_token: str | None = None  # simple addition for refresh token support

# (reference only; not returned by an endpoint)
class JWTClaims(BaseModel):
    sub: UUID        # user_id
    tenant_id: UUID
    exp: int         # epoch seconds

# ---- Notes ----
class NoteIn(BaseModel):
    title: str
    body: str

class NoteOut(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    body: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ---- Users (optional list endpoint) ----
class UserOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: Literal["admin", "user"]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ---- Stripe webhook ----
class StripeEventIn(BaseModel):  # accept raw Stripe event
    id: str
    type: str
    data: dict
    model_config = ConfigDict(extra="allow")
# (specific event schemas can be defined as needed)