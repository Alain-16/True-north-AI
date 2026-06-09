import asyncio
import logging

import resend

from core.config import get_settings

logger = logging.getLogger(__name__)


async def send_otp_email(to_email: str, code: str) -> None:
    if not to_email:
        raise ValueError("send_otp_email called without recipient")

    settings = get_settings()
    resend.api_key = settings.resend_api_key

    params: resend.Emails.SendParams = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": "Your TrueNorth-AI verification code",
        "text": (
            f"Your verification code is {code}. "
            f"It expires in {settings.otp_expiry_minutes} minutes."
        ),
    }

    try:
        # The Resend SDK is synchronous (requests under the hood) — offload to a
        # thread so it doesn't block the FastAPI event loop.
        email = await asyncio.to_thread(resend.Emails.send, params)
    except Exception as exc:
        # Surface Resend's ACTUAL reason (invalid from / unverified domain /
        # test-mode recipient restriction) instead of a bare HTTP status.
        logger.error(
            "Resend send failed (from=%r to=%r): %s",
            settings.email_from, to_email, exc,
        )
        raise

    logger.info("OTP email sent to %s (id=%s)", to_email, (email or {}).get("id"))
