import uuid
import logging
from fastapi import APIRouter
from sqlalchemy import text
from uuid import uuid4, UUID
from ..schemas import TenantCreate, TenantCreated
from ..db import SessionLocal, set_current_tenant
from ..core.security import pwd_ctx
from ..services.email_service import send_welcome_email
from ..services import stripe_service
import stripe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])


@router.post("/tenants", response_model=TenantCreated, status_code=201)
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
    send_welcome_email(body.admin_email, body.name)

    return TenantCreated(tenant_id=UUID(tenant_id))
