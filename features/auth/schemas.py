from pydantic import BaseModel, EmailStr


class RequestOTP(BaseModel):
    phone: str
    email: EmailStr


class VerifyOTP(BaseModel):
    phone: str
    code: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str