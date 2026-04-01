"""
事件-模型关联数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from ..core.database import Base


class EventModel(Base):
    """事件-模型关联表"""
    __tablename__ = "event_models"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String(20), nullable=False, comment="事件类型：historical/rss")
    event_id = Column(Integer, nullable=False, index=True, comment="事件ID")
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False, comment="模型ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 联合唯一约束
    __table_args__ = (
        UniqueConstraint('event_type', 'event_id', 'model_id', name='uq_event_model'),
    )

    def __repr__(self):
        return f"<EventModel(id={self.id}, event_type={self.event_type}, event_id={self.event_id})>"
