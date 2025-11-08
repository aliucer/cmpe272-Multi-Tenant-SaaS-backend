import uuid
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
from typing import List
import os, json, datetime, logging, jwt

from .db import SessionLocal, engine, Base, redis_client, set_current_tenant
from .models import Note, User, Tenant
from .schemas import (
    HealthOut, OkOut,
    TenantCreate, TenantCreated,
    LoginIn, TokenOut,
    NoteIn, NoteOut,
    UserOut,
    StripeEventIn,
)

# Optional external services (Stripe/SendGrid) — install via requirements.txt
import stripe
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
stripe.api_key = os.getenv("STRIPE_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET = os.getenv("SECRET_KEY", "dev-secret")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# ---------------------------
# App lifespan
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks
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

    # IMPORTANT: schema is created via migration/SQL on Supabase; do not auto-create here.
    # Base.metadata.create_all(bind=engine)

    yield
    logger.info("Shutting down...")

app = FastAPI(title="Multi-Tenant SaaS API", lifespan=lifespan)

# ---------------------------
# Auth helpers (JWT)
# ---------------------------
def create_access_token(user_id, tenant_id, ttl=3600):
    exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)
    return jwt.encode({"sub": user_id, "tenant_id": tenant_id, "exp": exp}, SECRET, algorithm="HS256")

def mint_refresh_token(user_id, tenant_id, ttl=60*60*24*7):
    jti = str(uuid.uuid4())
    key = f"rt:{jti}"
    redis_client.set(key, f"{user_id}:{tenant_id}", ex=ttl)
    return jti

def revoke_refresh_token(jti): redis_client.delete(f"rt:{jti}")

def is_refresh_valid(jti): return redis_client.exists(f"rt:{jti}") == 1

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])

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
# ---------------------------
# Health
# ---------------------------
@app.get("/health", response_model=HealthOut, tags=["misc"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        pg = "ok"
    except Exception as e:
        pg = f"error: {e}"

    try:
        redis_client.ping()
        rd = "ok"
    except Exception as e:
        rd = f"error: {e}"

    return HealthOut(postgres=pg, redis=rd)

# ---------------------------
# Tenant onboarding
# ---------------------------
@app.post("/tenants", response_model=TenantCreated, status_code=201, tags=["tenants"])
def create_tenant(body: TenantCreate):
    tenant_id = str(uuid4())
    # create tenant + admin user in one transaction under that tenant context
    with SessionLocal() as db:
        with db.begin():
            set_current_tenant(db, tenant_id)

            # insert tenant
            db.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name)"),
                {"id": tenant_id, "name": body.name}
            )

            # (optional) Stripe Customer
            if stripe.api_key:
                try:
                    customer = stripe.Customer.create(name=body.name, email=body.admin_email)
                    db.execute(
                        text("UPDATE tenants SET stripe_customer_id=:cid WHERE id=:id"),
                        {"cid": customer.id, "id": tenant_id}
                    )
                except Exception as e:
                    logger.info(f"Stripe create customer skipped/failed: {e}")

            # admin user
            db.execute(
                text("""
                    INSERT INTO users (tenant_id, email, password_hash, role)
                    VALUES (:tid, :email, :ph, 'admin')
                """),
                {"tid": tenant_id, "email": body.admin_email, "ph": pwd_ctx.hash(body.admin_password)},
            )

    # (optional) welcome email
    if SENDGRID_API_KEY:
        try:
            sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
            sg.send(Mail(
                from_email="noreply@example.com",
                to_emails=body.admin_email,
                subject=f"Welcome to {body.name}",
                plain_text_content="Your tenant is ready."
            ))
        except Exception as e:
            logger.info(f"SendGrid welcome email skipped/failed: {e}")

    return TenantCreated(tenant_id=UUID(tenant_id))

@app.post("/auth/refresh", response_model=TokenOut)
def refresh(jti: str):
    if not is_refresh_valid(jti): raise HTTPException(401, "Invalid refresh")
    # parse stored user_id:tenant_id and mint new access
    val = redis_client.get(f"rt:{jti}")
    user_id, tenant_id = val.split(":")
    return TokenOut(access_token=create_access_token(user_id, tenant_id, 3600), token_type="bearer", expires_in=3600)

@app.post("/auth/logout")
def logout(jti: str):
    revoke_refresh_token(jti)
    return OkOut(ok=True)

# ---------------------------
# Login
# ---------------------------

@app.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(body: LoginIn, x_tenant_id: str = Header(..., alias="X-Tenant-Id")):
    rate_limit(f"login:{x_tenant_id}:{body.email}", limit=10, window=300)   # validate tenant header
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
        token = create_access_token(user_id=str(row.id), tenant_id=x_tenant_id, expires_in=3600)
        return TokenOut(
            access_token=create_access_token(str(row.id), x_tenant_id, 3600),
            token_type="bearer",
            expires_in=3600,
        )


@app.get("/notes", response_model=List[NoteOut], tags=["notes"])
def list_notes(limit: int = 50, offset: int = 0, user=Depends(get_current_user), db: Session = Depends(get_db_jwt)):
    limit = min(max(limit, 1), 100)
    rows = db.query(Note).order_by(Note.created_at.desc()).limit(limit).offset(offset).all()
    return [NoteOut.model_validate(r) for r in rows]

@app.post("/notes", response_model=NoteOut, status_code=201, tags=["notes"])
def create_note(payload: NoteIn, user=Depends(get_current_user), db: Session = Depends(get_db_jwt)):
    note = Note(title=payload.title, body=payload.body)  # tenant_id via server_default/GUC
    db.add(note)
    db.flush()          # forces INSERT; server_default fills tenant_id/created_at
    db.refresh(note)    # still same txn; RLS ok because SET LOCAL is active
    out = NoteOut.model_validate(note)
    db.commit()         # commit after we have the data
    return out

def rate_limit(key: str, limit=300, window=60):
    bucket = f"rl:{key}:{int(time.time()//window)}"
    n = redis_client.incr(bucket)
    if n == 1: redis_client.expire(bucket, window)
    if n > limit: raise HTTPException(status_code=429, detail="Too many requests")

# ---------------------------
# Users (optional list)
# ---------------------------
@app.get("/users", response_model=List[UserOut], tags=["users"], dependencies=[Depends(require_role("admin"))])
def list_users(db: Session = Depends(get_db_jwt)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [UserOut.model_validate(r) for r in rows]

# ---------------------------
# Stripe webhook (minimal verification)
# ---------------------------
@app.post("/webhooks/stripe", response_model=OkOut, include_in_schema=False, tags=["webhooks"])
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        # Accept but indicate misconfig (for student projects this keeps demos simple)
        logger.warning("Stripe webhook received but STRIPE_WEBHOOK_SECRET is not set; skipping verify.")
        return OkOut(ok=True)

    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # You can parse and react to event types here if you want.
    return OkOut(ok=True)
