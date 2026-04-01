"""
RSS数据源相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator
import re


class RSSSourceBase(BaseModel):
    """RSS数据源基础模型"""
    name: str
    rss_url: str
    source_type: str = "other"
    crawl_interval: int = 60


class RSSSourceCreate(RSSSourceBase):
    """RSS数据源创建模型"""
    is_active: bool = True

    @field_validator('rss_url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('RSS链接必须是有效的URL')
        return v


class RSSSourceUpdate(BaseModel):
    """RSS数据源更新模型"""
    name: Optional[str] = None
    rss_url: Optional[str] = None
    source_type: Optional[str] = None
    crawl_interval: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator('rss_url')
    @classmethod
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('RSS链接必须是有效的URL')
        return v


class RSSSourceResponse(RSSSourceBase):
    """RSS数据源响应模型"""
    id: int
    is_active: bool
    last_crawled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RSSValidateResponse(BaseModel):
    """RSS验证响应模型"""
    valid: bool
    message: str
    title: Optional[str] = None
    item_count: Optional[int] = None
