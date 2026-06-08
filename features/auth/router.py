from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from features.auth.schemas import RequestOTP
from features.auth.service import request_login_otp
import logging
import uuid
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from sqlalchemy import select
from core.config import get_settings
from core.phone import normalize_phone
from core.security import create_access_token,create_refresh_token
from models.db import Patient,RefreshToken
from features.auth.service import verify_otp
from features.auth.schemas import TokenPair

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth",tags=["auth"])

_GENERIC_OTP_RESPONSE = {"message":"if those details match an account, a code has been sent.check email or phone"}


@router.post("/request-otp")
async def request_otp(body:RequestOTP,session:AsyncSession=Depends(get_db)):

    try:
        await request_login_otp(session,body.phone,body.email)
    except Exception:
        logger.exception("request-otp failed for submitted details")
    
    return _GENERIC_OTP_RESPONSE

@router.post("/verify-otp",response_model=TokenPair)
async def verify_otp_endpoint(body:verify_otp,session:AsyncSession=Depends(get_db)):

    settings = get_settings()

    norm_phone = normalize_phone(body.phone,settings.default_country_code)

    bad = HTTPException(status_code=401, detail="Invalid or expired code")

    patient = (await session.execute(
        select(Patient).where(Patient.whatsapp_phone == norm_phone)
    )).scalar_one_or_none()

    if patient is None:
        raise bad
    
    if not await verify_otp(session,norm_phone,"web_login",body.code):
        raise bad
    
    jti = uuid.uuid4()
    refresh_exp = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    access = create_access_token(patient.id,patient.openmrs_patient_id)
    refresh = create_refresh_token(jti,patient.id)

    session.add(RefreshToken(id=jti,patient_id=patient.id,expires_at=refresh_exp))

    await session.commit()

    return TokenPair(access_token=access,refresh_token=refresh)