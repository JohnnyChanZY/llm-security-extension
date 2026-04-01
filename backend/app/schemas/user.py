"""
用户相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """用户基础模型"""
    email: EmailStr
    nickname: Optional[str] = None


class UserCreate(UserBase):
    """用户注册模型"""
    password: str = Field(..., min_length=6, max_length=50)


class UserLogin(BaseModel):
    """用户登录模型"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """用户更新模型"""
    nickname: Optional[str] = None


class PasswordUpdate(BaseModel):
    """密码更新模型"""
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=50)


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    is_admin: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    """登录响应模型"""
    user: UserResponse
    token: TokenResponse
