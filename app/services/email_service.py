import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from ..core.config import SENDGRID_API_KEY, FROM_EMAIL

logger = logging.getLogger(__name__)


def send_welcome_email(to_email: str, tenant_name: str):
    if not SENDGRID_API_KEY:
        logger.info("SendGrid not configured, skipping welcome email")
        return
    
    try:
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        sg.send(Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject=f"Welcome to {tenant_name}",
            plain_text_content="Your tenant is ready."
        ))
    except Exception as e:
        logger.info(f"SendGrid welcome email skipped/failed: {e}")
