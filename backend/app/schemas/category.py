"""
分类相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class CategoryBase(BaseModel):
    """分类基础模型"""
    code: str
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    """分类创建模型"""
    pass


class CategoryUpdate(BaseModel):
    """分类更新模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """分类响应模型"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
