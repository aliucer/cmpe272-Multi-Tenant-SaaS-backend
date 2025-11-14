import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..core.dependencies import get_current_user, get_db_jwt
from ..core.config import PRICE_ID, BACKEND_URL
from ..services import stripe_service
import stripe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])


@router.post("/billing/checkout")
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


@router.get("/billing/success")
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


@router.get("/billing/cancel")
def billing_cancel():
    return {"ok": False, "reason": "checkout canceled"}
