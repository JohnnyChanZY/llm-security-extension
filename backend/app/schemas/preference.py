"""
用户偏好相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class PreferenceBase(BaseModel):
    """用户偏好基础模型"""
    model_id: Optional[int] = None
    category_id: Optional[int] = None
    is_enabled: bool = True


class PreferenceCreate(PreferenceBase):
    """用户偏好创建模型"""
    pass


class PreferenceUpdate(BaseModel):
    """用户偏好更新模型"""
    is_enabled: Optional[bool] = None


class PreferenceResponse(PreferenceBase):
    """用户偏好响应模型"""
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PreferenceDetail(PreferenceResponse):
    """用户偏好详情（包含关联信息）"""
    model_name: Optional[str] = None
    category_name: Optional[str] = None
