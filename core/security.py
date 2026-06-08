import jwt
from datetime import datetime,timedelta,timezone
from core.config import get_settings

def create_access_token(patient_id:str,openmrs_patient_id:str)-> str:

    settings = get_settings()
    now = datetime.now(timezone.utc)

    claims ={
        "sub":str(patient_id),
        "openmrs_patient_id":openmrs_patient_id,
        "type":"access",
        "iat":now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),

    }
    return jwt.encode(claims,settings.jwt_secret_key,algorithm=settings.jwt_algorithm)


def create_refresh_token(jti:str,patient_id:str) -> str:

    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims ={
        "sub":str(patient_id),
        "type":"refresh",
        "jti":str(jti),
        "iat":now,
        "exp":now + timedelta(days=settings.refresh_token_expire_days),

    } 
    return jwt.encode(claims,settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token:str,expected_type:str)-> dict:

    settings = get_settings()

    payload = jwt.decode(token,settings.jwt_secret_key,algorithms=[settings.jwt_algorithm])

    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload