"""
安全事件分类数据模型
"""
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from ..core.database import Base


class Category(Base):
    """安全事件分类表"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(30), unique=True, index=True, nullable=False, comment="分类代码")
    name = Column(String(50), nullable=False, comment="分类名称")
    description = Column(String(200), comment="描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Category(id={self.id}, code={self.code})>"
