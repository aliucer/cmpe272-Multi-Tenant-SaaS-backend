from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from ..schemas import UserOut, UserCreate
from ..models import User
from ..core.dependencies import require_role, get_db_jwt
from ..core.security import pwd_ctx

router = APIRouter(tags=["users"])


@router.get("/users", response_model=List[UserOut], dependencies=[Depends(require_role("admin"))])
def list_users(db: Session = Depends(get_db_jwt)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [UserOut.model_validate(r) for r in rows]


@router.post("/users", response_model=UserOut, dependencies=[Depends(require_role("admin"))])
def create_user(body: UserCreate, db: Session = Depends(get_db_jwt)):
    """
    Create a user inside the *current tenant*.
    RLS is active thanks to get_db_jwt -> SET LOCAL app.current_tenant.
    We explicitly set tenant_id from current_setting(...) to satisfy RLS WITH CHECK.
    """
    try:
        row = db.execute(
            text("""
                INSERT INTO users (tenant_id, email, password_hash, role)
                VALUES (current_setting('app.current_tenant', true)::uuid, :email, :ph, :role)
                RETURNING id, tenant_id, email, role, created_at
            """),
            {
                "email": body.email,
                "ph": pwd_ctx.hash(body.password),
                "role": body.role,
            },
        ).mappings().one()
        db.commit()
        return UserOut.model_validate(row)
    except IntegrityError:
        db.rollback()
        # UNIQUE (tenant_id, email) → duplicate within this tenant
        raise HTTPException(status_code=409, detail="User with this email already exists in this tenant")
