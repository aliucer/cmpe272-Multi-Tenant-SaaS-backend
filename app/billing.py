from fastapi import APIRouter, Depends, HTTPException, Request
from .auth import get_current_user
from . import models
import stripe
import os

router = APIRouter(prefix="/billing", tags=["billing"])

# Configure Stripe with your secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
def create_checkout_session(current_user: models.User = Depends(get_current_user)):
    """Create a Stripe checkout session for the logged-in user."""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 500,  # $5.00 in cents
                    "product_data": {
                        "name": "Premium Note Plan",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="http://localhost:8000/success",
            cancel_url="http://localhost:8000/cancel",
            metadata={"user_id": current_user.id}
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
