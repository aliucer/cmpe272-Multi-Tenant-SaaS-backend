# cmpe272 Multi-Tenant SaaS Backend

Multi-tenant SaaS backend for a CMPE 272 project.

Shows:

- Tenant onboarding
- Tenant-scoped users and JWT auth
- Postgres Row-Level Security (RLS) for multi-tenancy
- Tenant-scoped notes API
- Redis-backed refresh tokens + rate limiting
- Stripe checkout + webhooks
- SendGrid emails
- Deployment on Render

---

## Live Deployment

- Base URL: `https://cmpe272-multi-tenant-saas-backend.onrender.com/`
- Swagger UI: `https://cmpe272-multi-tenant-saas-backend.onrender.com/docs`
- ReDoc: `https://cmpe272-multi-tenant-saas-backend.onrender.com/redoc`

Cold start on Render: first request after idling can take ~50s.

---

## Tech Stack

- FastAPI (Python)
- PostgreSQL + RLS (schema + policies in [`app/schema.sql`](app/schema.sql))
- SQLAlchemy
- Redis (refresh tokens + rate limiting)
- Stripe (checkout + webhooks)
- SendGrid (emails)
- Render (deployment)

High-level flow:

Client → FastAPI (JWT) → `set_current_tenant` → SQLAlchemy → Postgres (RLS)  
            ↘ Redis (refresh / rate limit)  
            ↘ Stripe (checkout) → `/webhooks/stripe`  
            ↘ SendGrid (emails)

---

## Project Structure

- `app/main.py` — FastAPI app, endpoints, auth, Stripe, SendGrid
- `app/models.py` — `Tenant`, `User`, `Note`
- `app/db.py` — DB engine, session, Redis client, `set_current_tenant`
- `app/schemas.py` — Pydantic models
- `app/schema.sql` — tables + RLS policies
- `requirements.txt` — dependencies

---

## Running Locally

```bash
git clone https://github.com/aliucer/cmpe272-Multi-Tenant-SaaS-backend.git
cd cmpe272-Multi-Tenant-SaaS-backend

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Set up Postgres + Redis and export:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/saas_db"
export REDIS_URL="redis://localhost:6379/0"

export SECRET_KEY="dev-secret"
export BACKEND_URL="http://localhost:8000"

# Optional integrations
export STRIPE_API_KEY="sk_test_..."
export STRIPE_WEBHOOK_SECRET="whsec_..."
export STRIPE_PRICE_ID="price_..."
export SENDGRID_API_KEY="SG.xxx"
export SENDGRID_FROM="noreply@example.com"
```

Apply the schema:

```bash
psql "$DATABASE_URL" -f app/schema.sql
```

Run the API:

```bash
uvicorn app.main:app --reload
```

---

## Multi-Tenancy & RLS

- `app/schema.sql` defines `tenants`, `users`, `notes` and enables RLS on all.
- RLS uses `current_setting('app.current_tenant', true)::uuid`.
- Backend calls `set_current_tenant(db, tenant_id)` per request.
- `notes.tenant_id` defaults from `app.current_tenant`, so queries stay tenant-scoped.

---

## API Overview

### Health

- `GET /health`  
  Checks Postgres + Redis.

### Tenants

- `POST /tenants`  
  Body:

  ```json
  {
    "name": "Acme Inc",
    "admin_email": "admin@acme.com",
    "admin_password": "super-secret"
  }
  ```

  Creates tenant + admin user, optional Stripe customer + SendGrid welcome email.  
  Response:

  ```json
  { "tenant_id": "uuid" }
  ```

### Auth

Headers: `X-Tenant-Id: <tenant-uuid>` where required.

- `POST /auth/login`  
  Body:

  ```json
  { "email": "admin@acme.com", "password": "super-secret" }
  ```

  Rate-limited via Redis. Returns:

  ```json
  {
    "access_token": "jwt",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "refresh-jti"
  }
  ```

- `POST /auth/refresh`  
  Body:

  ```json
  { "jti": "refresh-jti" }
  ```

  Returns a new `TokenOut`.

- `POST /auth/logout`  
  Body:

  ```json
  { "jti": "refresh-jti" }
  ```

  Revokes the refresh token.

### Notes (tenant-scoped, JWT required)

- `GET /notes`  
  Query: `limit` (default 50, max 100), `offset` (default 0).  
  Returns list of notes for the current tenant.

- `POST /notes`  
  Body:

  ```json
  { "title": "My note", "body": "Content" }
  ```

  Creates a note under the current tenant.

### Users (admin only)

- `GET /users`  
  Requires `require_role("admin")`.  
  Returns users for the current tenant.

### Billing (Stripe)

- `POST /billing/checkout`  
  Creates a Checkout Session for the current tenant using `STRIPE_PRICE_ID`.

- `POST /webhooks/stripe`  
  Stripe webhook endpoint (e.g. handles `payment_intent.succeeded`).

---

## Benchmarks (dev)

Approx local results:

- `POST /auth/login`: avg ~441 ms
- `POST /notes`: avg ~457 ms
- `GET /notes?limit=10`: avg ~334 ms
- `GET /users`: avg ~634 ms
- `GET /health`: ~426 ms
- `POST /tenants`: ~1,639 ms
