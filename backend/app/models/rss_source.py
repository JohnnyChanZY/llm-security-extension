"""
RSS数据源数据模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from ..core.database import Base


class RSSSource(Base):
    """RSS数据源表"""
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="源名称")
    rss_url = Column(String(500), nullable=False, comment="RSS链接")
    source_type = Column(String(20), default="other", comment="源类型：wechat/blog/other")
    is_active = Column(Boolean, default=True, comment="是否启用")
    crawl_interval = Column(Integer, default=60, comment="爬取间隔（分钟）")
    last_crawled_at = Column(DateTime, comment="最后爬取时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<RSSSource(id={self.id}, name={self.name})>"
