"""
推送记录数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from ..core.database import Base
import enum


class PushChannel(str, enum.Enum):
    """推送渠道枚举"""
    EXTENSION = "extension"
    EMAIL = "email"


class PushStatus(str, enum.Enum):
    """推送状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PushLog(Base):
    """推送记录表"""
    __tablename__ = "push_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    event_type = Column(String(20), nullable=False, comment="事件类型：historical/rss")
    event_id = Column(Integer, nullable=False, index=True, comment="事件ID")
    push_channel = Column(Enum(PushChannel), default=PushChannel.EXTENSION, comment="推送渠道")
    push_status = Column(Enum(PushStatus), default=PushStatus.PENDING, comment="状态")
    pushed_at = Column(DateTime, comment="推送时间")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<PushLog(id={self.id}, user_id={self.user_id}, status={self.push_status})>"
