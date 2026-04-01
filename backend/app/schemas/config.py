"""
系统配置相关Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ConfigBase(BaseModel):
    """系统配置基础模型"""
    config_key: str
    config_value: Optional[str] = None
    description: Optional[str] = None


class ConfigUpdate(BaseModel):
    """系统配置更新模型"""
    config_value: str


class ConfigResponse(ConfigBase):
    """系统配置响应模型"""
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LLMConfigResponse(BaseModel):
    """LLM配置响应"""
    llm_classify_enabled: bool
    llm_rating_enabled: bool
    llm_batch_size: int
    llm_max_concurrent_batches: int = 3  # 并行处理最大批次数
    llm_request_interval: float = 2.0  # 请求间隔时间（秒）
    max_batch_size: int = 100  # 批量处理最大上限
    max_concurrent_batches: int = 10  # 并行批次最大上限
    max_request_interval: float = 60.0  # 请求间隔最大上限
