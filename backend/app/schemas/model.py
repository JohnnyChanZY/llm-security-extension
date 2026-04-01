"""
模型相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ModelBase(BaseModel):
    """模型基础模型"""
    name: str
    vendor: Optional[str] = None
    description: Optional[str] = None


class ModelCreate(ModelBase):
    """模型创建模型"""
    is_active: bool = True
    sort_order: int = 0


class ModelUpdate(BaseModel):
    """模型更新模型"""
    name: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ModelResponse(ModelBase):
    """模型响应模型"""
    id: int
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
