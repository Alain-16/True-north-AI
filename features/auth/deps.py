import jwt
from fastapi import Header, HTTPException

from core.security import decode_token


async def get_current_patient(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: derive the patient identity from a verified access token.

    Replaces trusting `patient_id` from the request body. Returns
    {patient_id, openmrs_patient_id} or raises 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "patient_id": payload["sub"],
        "openmrs_patient_id": payload.get("openmrs_patient_id"),
    }
