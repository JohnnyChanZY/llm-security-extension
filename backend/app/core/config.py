"""
配置管理模块
负责加载和管理应用程序配置

所有敏感配置从 .env 文件读取，请复制 .env.example 为 .env 并填写实际值
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用程序配置类"""

    # 应用配置
    app_name: str = "LLM Security Event Push System"
    app_version: str = "3.0.0"
    debug: bool = True

    # 数据库配置
    database_url: str = ""

    # NVD API配置
    nvd_api_key: Optional[str] = None

    # AIID API配置
    aiid_api_key: Optional[str] = None

    # LLM API配置 (通用配置，支持腾讯云等)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.lkeap.cloud.tencent.com/coding/v3"
    llm_model: str = "glm-5"

    # JWT配置
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # 管理员配置
    admin_email: str = "admin"
    admin_password: str = "password"

    # LLM 日志配置
    llm_log_enabled: bool = False
    llm_log_dir: str = "logs/llm"

    # LLM 批处理配置
    llm_batch_size: int = 30  # 单次 LLM 请求最多处理的事件数

    # CORS 允许的来源（逗号分隔）
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出配置实例
settings = get_settings()
