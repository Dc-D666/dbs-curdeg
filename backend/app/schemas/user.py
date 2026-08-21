"""用户/认证相关 Pydantic 模型。"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------- 请求 ----------


class SendCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=64)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("密码需同时包含字母和数字")
        return v


class LoginRequest(BaseModel):
    account: str = Field(min_length=3, max_length=64)  # 用户名或邮箱
    password: str = Field(min_length=1, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=64)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("新密码需同时包含字母和数字")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=64)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("新密码需同时包含字母和数字")
        return v


class UpdateProfileRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=255)
    gender: int | None = Field(default=None, ge=0, le=2)
    province: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=32)
    avatar_url: str | None = Field(default=None, max_length=255)


# ---------- 响应 ----------


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    avatar_url: str
    bio: str
    gender: int
    province: str
    city: str
    email: str
    user_type: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicUserOut(BaseModel):
    """他人主页公开资料（不含 email/手机号等隐私字段）。"""
    id: int
    username: str
    nickname: str
    avatar_url: str
    bio: str
    gender: int
    province: str
    city: str
    user_type: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
