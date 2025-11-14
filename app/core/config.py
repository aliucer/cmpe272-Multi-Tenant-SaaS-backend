import os

SECRET = os.getenv("SECRET_KEY", "dev-secret")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FROM_EMAIL = os.getenv("SENDGRID_FROM", "noreply@example.com")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

print("SENDGRID_API_KEY:", bool(os.getenv("SENDGRID_API_KEY")))
print("SENDGRID_FROM:", os.getenv("SENDGRID_FROM"))
