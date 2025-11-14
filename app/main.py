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
import time
from fastapi import Body
from sqlalchemy.exc import IntegrityError
from .schemas import (
    HealthOut, OkOut,
    TenantCreate, TenantCreated,
    LoginIn, TokenOut,
    NoteIn, NoteOut,
    UserOut, UserCreate,
    StripeEventIn,
)
from .db import SessionLocal, engine, Base, redis_client, set_current_tenant
from .models import Note, User, Tenant

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
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FROM_EMAIL = os.getenv("SENDGRID_FROM", "noreply@example.com")

print("SENDGRID_API_KEY:", bool(os.getenv("SENDGRID_API_KEY")))
print("SENDGRID_FROM:", os.getenv("SENDGRID_FROM"))
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
                from_email=FROM_EMAIL,
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
        access = create_access_token(str(row.id), x_tenant_id, 3600)
        jti = mint_refresh_token(str(row.id), x_tenant_id)  # see "refresh token" below
        return TokenOut(access_token=access, token_type="bearer", expires_in=3600, refresh_token=jti)



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

    payload = (await request.body()).decode("utf-8")
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    etype = event["type"]
    data = event["data"]["object"]

    if etype == "payment_intent.succeeded":
        tid = (data.get("metadata") or {}).get("tenant_id")
        amt = data.get("amount_received")
        currency = data.get("currency")
        logger.info(f"✅ One-time payment succeeded for tenant={tid} amount={amt} {currency}")
    # (optional) update your DB if you add a 'last_payment_at' column later

    # You can parse and react to event types here if you want.
    return OkOut(ok=True)

@app.post("/billing/checkout", tags=["billing"])
def create_one_time_checkout_session(
    user=Depends(get_current_user),           # reads JWT with tenant_id
    db: Session = Depends(get_db_jwt),        # 🔑 sets app.current_tenant for THIS DB session
):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured (STRIPE_API_KEY)")
    if not PRICE_ID:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_ID not set")

    tenant_id = user["tenant_id"]

    # RLS is active on this db session; this SELECT can see only current tenant rows
    row = db.execute(
        text("SELECT stripe_customer_id, name FROM tenants WHERE id=:id"),
        {"id": tenant_id},
    ).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")

    customer_id = row["stripe_customer_id"]
    tenant_name = row["name"]

    if not customer_id:
        cust = stripe.Customer.create(name=tenant_name, metadata={"tenant_id": tenant_id})
        db.execute(text("UPDATE tenants SET stripe_customer_id=:cid WHERE id=:id"),
                   {"cid": cust.id, "id": tenant_id})
        db.commit()
        customer_id = cust.id

    try:
        session = stripe.checkout.Session.create(
            mode="payment",                         # one-time price
            customer=customer_id,
            line_items=[{"price": PRICE_ID, "quantity": 1}],
            success_url=f"{BACKEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BACKEND_URL}/billing/cancel",
            metadata={"tenant_id": tenant_id, "tenant_name": tenant_name},
            payment_intent_data={
                "metadata": {"tenant_id": tenant_id, "tenant_name": tenant_name}
            },
        )
        return {"url": session.url}
    except Exception as e:
        logger.exception("Stripe Checkout create failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

@app.get("/billing/success", tags=["billing"])
def billing_success(session_id: str):
    # Minimal success handler so the redirect lands somewhere;
    # also confirms payment status without webhooks.
    try:
        sess = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
        return {
            "ok": True,
            "session_id": session_id,
            "payment_status": sess.payment_status,          # "paid" when done
            "payment_intent": getattr(sess.payment_intent, "id", None),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot retrieve session: {e}")

@app.get("/billing/cancel", tags=["billing"])
def billing_cancel():
    return {"ok": False, "reason": "checkout canceled"}

@app.post("/users", response_model=UserOut, tags=["users"], dependencies=[Depends(require_role("admin"))])
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