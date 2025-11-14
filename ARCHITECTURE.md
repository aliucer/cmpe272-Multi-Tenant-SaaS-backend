# Architecture Overview

This document describes the structure and organization of the Multi-Tenant SaaS backend codebase.

## Directory Structure

```
app/
├── main.py              # Application entry point
├── db.py                # Database and Redis configuration
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response models
├── schema.sql           # PostgreSQL schema with RLS policies
├── api/                 # API endpoint handlers
│   ├── health.py        # Health check endpoint
│   ├── auth.py          # Authentication (login, refresh, logout)
│   ├── tenants.py       # Tenant management
│   ├── notes.py         # Note CRUD operations
│   ├── users.py         # User management
│   ├── billing.py       # Stripe billing integration
│   └── webhooks.py      # External webhook handlers
├── core/                # Core application functionality
│   ├── config.py        # Environment variables and configuration
│   ├── security.py      # JWT tokens and password hashing
│   ├── dependencies.py  # FastAPI dependencies (auth, DB sessions)
│   └── rate_limit.py    # Rate limiting using Redis
└── services/            # External service integrations
    ├── stripe_service.py   # Stripe API client
    └── email_service.py    # SendGrid email service
```

## Module Responsibilities

### `app/main.py`
- FastAPI application initialization
- Lifespan management (startup/shutdown)
- Router registration
- **Lines of code**: 51 (down from 390)

### `app/api/` - API Route Handlers
Each module in this directory handles HTTP endpoints for a specific domain:

- **`health.py`** (24 lines): Database and Redis health checks
- **`auth.py`** (57 lines): JWT-based authentication
  - POST `/auth/login` - Login with email/password
  - POST `/auth/refresh` - Refresh access token
  - POST `/auth/logout` - Revoke refresh token
- **`tenants.py`** (55 lines): Tenant onboarding
  - POST `/tenants` - Create tenant with admin user
- **`notes.py`** (26 lines): Note CRUD operations
  - GET `/notes` - List notes
  - POST `/notes` - Create note
- **`users.py`** (45 lines): User management
  - GET `/users` - List users (admin only)
  - POST `/users` - Create user (admin only)
- **`billing.py`** (81 lines): Stripe integration
  - POST `/billing/checkout` - Create checkout session
  - GET `/billing/success` - Success callback
  - GET `/billing/cancel` - Cancel callback
- **`webhooks.py`** (37 lines): External webhook handlers
  - POST `/webhooks/stripe` - Stripe events

### `app/core/` - Core Functionality
Shared business logic and utilities:

- **`config.py`** (12 lines): Environment variable loading
  - SECRET_KEY, STRIPE_API_KEY, SENDGRID_API_KEY, etc.
- **`security.py`** (32 lines): Authentication utilities
  - JWT token creation and validation
  - Password hashing with passlib
  - Refresh token management using Redis
- **`dependencies.py`** (39 lines): FastAPI dependencies
  - `get_current_user()` - Extract user from JWT
  - `get_db_jwt()` - Database session with tenant context
  - `require_role()` - Role-based access control
- **`rate_limit.py`** (12 lines): Rate limiting
  - Redis-based request throttling

### `app/services/` - External Services
Integration with third-party services:

- **`stripe_service.py`** (4 lines): Stripe API configuration
- **`email_service.py`** (23 lines): SendGrid email sending
  - Welcome emails for new tenants

## Key Design Patterns

### Multi-Tenancy with Row-Level Security (RLS)
- PostgreSQL RLS policies isolate tenant data
- `set_current_tenant()` sets `app.current_tenant` session variable
- All queries automatically filtered by tenant context

### Authentication Flow
1. Client sends credentials to `/auth/login` with `X-Tenant-Id` header
2. Server validates credentials and tenant ID
3. Returns JWT access token (1 hour) and refresh token (7 days)
4. Client includes access token in `Authorization: Bearer <token>` header
5. `get_current_user()` dependency validates token and extracts user info
6. `get_db_jwt()` sets tenant context for database queries

### Rate Limiting
- Redis-based sliding window rate limiter
- Configurable per-endpoint limits
- Example: Login limited to 10 requests per 5 minutes per tenant+email

## Benefits of This Structure

1. **Separation of Concerns**: Each module has a single, clear responsibility
2. **Easy Navigation**: Find code by domain (auth, billing, notes, etc.)
3. **Better Testing**: Isolated modules are easier to test
4. **Team Collaboration**: Multiple developers can work on different modules
5. **Maintainability**: Changes are localized to relevant modules
6. **Scalability**: Easy to add new domains without cluttering main.py

## Before vs After

**Before Restructuring:**
- Single `main.py`: 390 lines
- All logic mixed together
- Hard to find specific functionality
- Difficult to test individual components

**After Restructuring:**
- `main.py`: 51 lines (router registration only)
- 17 organized modules
- Clear separation by domain and responsibility
- Easy to locate and modify specific features

## Adding New Features

### To add a new API endpoint:
1. Create or modify a file in `app/api/`
2. Define your route handlers using FastAPI decorators
3. Import and register the router in `app/main.py`

### To add a new external service:
1. Create a new file in `app/services/`
2. Implement service client and helper functions
3. Import and use in relevant API handlers

### To add core functionality:
1. Add utility functions to `app/core/`
2. Keep them generic and reusable
3. Import where needed in API handlers

## Configuration

All configuration is centralized in `app/core/config.py`:
- Database: `DATABASE_URL`
- Redis: `REDIS_URL`
- JWT: `SECRET_KEY`
- Stripe: `STRIPE_API_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`
- SendGrid: `SENDGRID_API_KEY`, `SENDGRID_FROM`
- Application: `BACKEND_URL`

## Security

- JWT tokens for authentication
- Password hashing with PBKDF2-SHA256
- PostgreSQL RLS for data isolation
- Rate limiting to prevent abuse
- Stripe webhook signature verification
- Role-based access control (admin/user)

## Testing

To verify the application:
```bash
# Set required environment variables
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
export REDIS_URL="redis://localhost:6379/0"

# Run the application
python -m uvicorn app.main:app --reload

# Check all routes are registered
curl http://localhost:8000/docs
```
