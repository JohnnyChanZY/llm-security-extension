"""
统一响应格式Schema
"""
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一响应格式"""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据格式"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    code: int = 0
    message: str = "success"
    data: Optional[PaginatedData[T]] = None
