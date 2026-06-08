import httpx
import logging
from core.config import get_settings

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"

async def send_otp_email(to_email: str, code: str)-> None:

    if not to_email:
        raise ValueError("send_otp_email called without recipient")
    
    settings = get_settings()
    payload = {
        "from":settings.email_from,
        "to":[to_email],
        "subject":"Your truenorth-AI verification code",
        "text":(
            f"Your verification code is {code}."
            f"it expires in {settings.otp_expiry_minutes} minutes."
        ),

    }

    headers = {"Authorization":f"Bearer {settings.resend_api_key}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_RESEND_URL, json=payload, headers=headers)
        resp.raise_for_status()
    
    logger.info("OTP email sent to %s (status %s)", to_email, resp.status_code)