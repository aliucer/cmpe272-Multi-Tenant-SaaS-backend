from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text
from uuid import UUID
from ..schemas import LoginIn, TokenOut, OkOut
from ..db import SessionLocal, set_current_tenant, redis_client
from ..core.security import (
    create_access_token,
    mint_refresh_token,
    revoke_refresh_token,
    is_refresh_valid,
    pwd_ctx
)
from ..core.rate_limit import rate_limit

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, x_tenant_id: str = Header(..., alias="X-Tenant-Id")):
    rate_limit(f"login:{x_tenant_id}:{body.email}", limit=10, window=300)
    # validate tenant header
    try:
        UUID(x_tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id; must be a UUID")

    with SessionLocal() as db:
        set_current_tenant(db, x_tenant_id)

        row = db.execute(
            text("SELECT id, password_hash FROM users WHERE email=:email LIMIT 1"),
            {"email": body.email}
        ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not pwd_ctx.verify(body.password, row.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        access = create_access_token(str(row.id), x_tenant_id, 3600)
        jti = mint_refresh_token(str(row.id), x_tenant_id)
        return TokenOut(access_token=access, token_type="bearer", expires_in=3600, refresh_token=jti)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(jti: str):
    if not is_refresh_valid(jti):
        raise HTTPException(401, "Invalid refresh")
    # parse stored user_id:tenant_id and mint new access
    val = redis_client.get(f"rt:{jti}")
    user_id, tenant_id = val.split(":")
    return TokenOut(access_token=create_access_token(user_id, tenant_id, 3600), token_type="bearer", expires_in=3600)


@router.post("/auth/logout")
def logout(jti: str):
    revoke_refresh_token(jti)
    return OkOut(ok=True)
