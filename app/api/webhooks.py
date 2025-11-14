import logging
from fastapi import APIRouter, HTTPException, Request
from ..schemas import OkOut
from ..core.config import STRIPE_WEBHOOK_SECRET
from ..services import stripe_service
import stripe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"], include_in_schema=False)


@router.post("/webhooks/stripe", response_model=OkOut)
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
