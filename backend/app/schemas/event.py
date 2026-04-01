"""
事件相关Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class SeverityLevel(str, Enum):
    """安全等级枚举"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    """事件类型枚举"""
    HISTORICAL = "historical"
    RSS = "rss"


class EventBase(BaseModel):
    """事件基础模型"""
    title: str
    description: Optional[str] = None
    original_url: Optional[str] = None
    published_at: Optional[datetime] = None
    cve_id: Optional[str] = None
    severity: Optional[SeverityLevel] = None


class EventFilter(BaseModel):
    """事件筛选参数"""
    page: int = 1
    page_size: int = 20
    category: Optional[str] = None
    model_id: Optional[int] = None
    severity: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    keyword: Optional[str] = None


class RelatedModel(BaseModel):
    """关联模型"""
    id: int
    name: str
    vendor: Optional[str] = None


class CategoryInfo(BaseModel):
    """分类信息"""
    id: int
    code: str
    name: str


class EventResponse(BaseModel):
    """事件响应模型"""
    id: int
    title: str
    description: Optional[str] = None
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    original_url: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[CategoryInfo] = None
    cve_id: Optional[str] = None
    severity: Optional[SeverityLevel] = None
    severity_source: Optional[str] = None
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    affected_models: List[RelatedModel] = []
    created_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """事件列表响应"""
    items: List[EventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UnreadCountResponse(BaseModel):
    """未读数量响应"""
    count: int
