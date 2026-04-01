"""
系统配置数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..core.database import Base


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(50), unique=True, index=True, nullable=False, comment="配置键")
    config_value = Column(Text, comment="配置值")
    description = Column(String(200), comment="配置说明")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<SystemConfig(key={self.config_key}, value={self.config_value})>"
