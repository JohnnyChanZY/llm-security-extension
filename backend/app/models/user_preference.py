"""
用户关注设置数据模型
"""
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from ..core.database import Base


class UserPreference(Base):
    """用户关注设置表"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    model_id = Column(Integer, ForeignKey("models.id"), comment="模型ID")
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 联合唯一约束：同一用户对同一模型+分类组合只能有一条记录
    __table_args__ = (
        UniqueConstraint('user_id', 'model_id', 'category_id', name='uq_user_preference'),
    )

    def __repr__(self):
        return f"<UserPreference(id={self.id}, user_id={self.user_id})>"
