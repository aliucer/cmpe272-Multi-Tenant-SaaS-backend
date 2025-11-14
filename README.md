# cmpe272-Multi-Tenant-SaaS-backend

A minimal FastAPI backend demo for note-taking, using PostgreSQL and SQLAlchemy ORM. This project is a starting point for building multi-tenant SaaS applications, but currently implements a single-tenant Notes API for learning and prototyping.

## Features
- FastAPI service exposing REST endpoints for notes
- PostgreSQL database (connection via `DATABASE_URL`)
- SQLAlchemy ORM models and session management
- Pydantic v2 schemas for request/response validation
- Auto-creates tables on startup for development

## Quickstart
1. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```
2. **Set up your database connection:**
	```bash
	export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
	```
3. **Run the development server:**
	```bash
	python -m uvicorn app.main:app --reload
	```

## API Endpoints
- `GET /health` — Health check (verifies DB and Redis connection)
- `POST /tenants` — Create a new tenant with admin user
- `POST /auth/login` — Login and get JWT access token
- `POST /auth/refresh` — Refresh access token
- `POST /auth/logout` — Logout and revoke refresh token
- `GET /notes` — List all notes (authenticated)
- `POST /notes` — Create a new note (authenticated)
- `GET /users` — List users (admin only)
- `POST /users` — Create a new user (admin only)
- `POST /billing/checkout` — Create Stripe checkout session
- `GET /billing/success` — Billing success callback
- `GET /billing/cancel` — Billing cancel callback
- `POST /webhooks/stripe` — Stripe webhook handler

## Project Structure
```
app/
├── main.py              # Application entry point, FastAPI app setup
├── db.py                # Database engine, session, and Redis client
├── models.py            # SQLAlchemy ORM models (Tenant, User, Note)
├── schemas.py           # Pydantic models for request/response validation
├── schema.sql           # Database schema and RLS policies
├── api/                 # API route handlers (organized by domain)
│   ├── health.py        # Health check endpoint
│   ├── auth.py          # Authentication endpoints
│   ├── tenants.py       # Tenant management
│   ├── notes.py         # Note CRUD operations
│   ├── users.py         # User management
│   ├── billing.py       # Stripe billing integration
│   └── webhooks.py      # Webhook handlers
├── core/                # Core application functionality
│   ├── config.py        # Configuration and environment variables
│   ├── security.py      # JWT tokens, password hashing
│   ├── dependencies.py  # FastAPI dependencies (auth, DB session)
│   └── rate_limit.py    # Rate limiting implementation
└── services/            # External service integrations
    ├── stripe_service.py   # Stripe API integration
    └── email_service.py    # SendGrid email service
```

## Notes
- Multi-tenancy is implemented using PostgreSQL Row-Level Security (RLS)
- Authentication uses JWT tokens with refresh token support
- Rate limiting is implemented using Redis
- Stripe integration for billing (requires STRIPE_API_KEY and STRIPE_PRICE_ID)
- SendGrid integration for email notifications (optional)
- For production, use proper secrets management and set up database migrations

## License
MIT