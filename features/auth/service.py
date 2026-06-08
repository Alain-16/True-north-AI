import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update, select, func

from core.config import get_settings
from models.db import OTPToken, Patient
from core.phone import normalize_phone
import logging
from features.auth.email import send_otp_email

logger = logging.getLogger(__name__)



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

async def verify_otp(session,phone:str,purpose:str,submitted_code:str | None)-> bool:

    row = (await session.execute(
        select(OTPToken).where(
            OTPToken.phone == phone,
            OTPToken.purpose == purpose,
            OTPToken.used.is_(False),
        )
        .order_by(OTPToken.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if row is None:
        return False
    
    if row.expires_at <= datetime.now(timezone.utc):
        return False
    
    if not submitted_code or not secrets.compare_digest(row.token,submitted_code):
        return False
    
    row.used = True
    return True


async def request_login_otp(session,phone:str,email:str)-> None:
    settings = get_settings()
    norm_phone = normalize_phone(phone,settings.default_country_code)
    
    patient =(await session.execute(
        select(Patient).where(
            Patient.whatsapp_phone == norm_phone,
            func.lower(Patient.web_email) == email.lower(),
        )
    )).scalar_one_or_none()

    if patient is None or not patient.web_email:
        logger.info("request_login_otp: no patient for given phone or email found in our records")
        return
    
    code = await generate_otp(session,patient.whatsapp_phone,"web_login")

    await send_otp_email(patient.web_email,code)
    await session.commit()