from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class SendSmsCodeRequest(BaseModel):
    phone: str
    purpose: str = "REGISTER"


class SendSmsCodeResponse(BaseModel):
    request_id: str
    status: str


class PhoneRegisterRequest(BaseModel):
    phone: str
    password: str
    sms_code: str | None = None


class PhoneRegisterResponse(BaseModel):
    user_id: int
    phone: str
    username: str
    access_token: str
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
