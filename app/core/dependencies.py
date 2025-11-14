from fastapi import Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.orm import Session
from .security import decode_access_token
from ..db import SessionLocal, set_current_tenant


def get_current_user(auth: str = Header(..., alias="Authorization")) -> dict:
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user_id": payload["sub"], "tenant_id": payload["tenant_id"]}


def get_db_jwt(user=Depends(get_current_user)):
    db = SessionLocal()
    try:
        set_current_tenant(db, user["tenant_id"])
        yield db
    finally:
        db.close()


def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        with SessionLocal() as db:
            db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": user["tenant_id"]})
            row = db.execute(
                text("SELECT role FROM users WHERE id=:uid LIMIT 1"),
                {"uid": user["user_id"]}
            ).fetchone()
            if not row or row.role not in roles:
                raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dep
