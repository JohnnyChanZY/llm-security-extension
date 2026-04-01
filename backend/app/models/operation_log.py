"""
操作日志数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from ..core.database import Base


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, comment="操作用户ID")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), comment="目标类型")
    target_id = Column(Integer, comment="目标ID")
    details = Column(Text, comment="操作详情")
    ip_address = Column(String(50), comment="IP地址")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="操作时间")

    def __repr__(self):
        return f"<OperationLog(id={self.id}, action={self.action})>"
