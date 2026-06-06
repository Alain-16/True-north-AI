import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from core.config import get_settings
from models.db import OTPToken


async def generate_otp(session, phone: str, purpose: str) -> str:
    """C
    this function create an OTP code to send to users for verification
    """
    settings = get_settings()

    # Kill any still-live codes for this (phone, purpose) before issuing a new one.
    # `.is_(False)` mirrors the index predicate `WHERE NOT used`.
    await session.execute(
        update(OTPToken)
        .where(
            OTPToken.phone == phone,
            OTPToken.purpose == purpose,
            OTPToken.used.is_(False),
        )
        .values(used=True)
    )

    # CSPRNG (not `random`); zero-padded so a code like 042315 keeps all 6 digits
    # and fits the fixed-width VARCHAR(6) column.
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes)

    # session.add is synchronous (no await) — it just stages the INSERT.
    session.add(OTPToken(phone=phone, token=code, purpose=purpose, expires_at=expires_at))

    return code