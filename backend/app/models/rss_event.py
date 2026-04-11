"""
RSS实时安全事件数据模型
存储RSS获取的实时数据，用于推送
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.sql import func
from ..core.database import Base
from .historical_event import SeverityLevel, SeveritySource


class RSSEvent(Base):
    """RSS实时安全事件表"""
    __tablename__ = "rss_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="事件标题")
    description = Column(Text, comment="事件描述/摘要")
    rss_source_id = Column(Integer, ForeignKey("rss_sources.id"), comment="RSS源ID")
    source_name = Column(String(100), comment="来源平台名称")
    original_url = Column(String(500), index=True, comment="原文链接（去重依据）")
    published_at = Column(DateTime, index=True, comment="发布时间")
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    cve_id = Column(String(20), index=True, comment="CVE编号（去重依据，如有）")
    severity = Column(Enum(SeverityLevel, values_callable=lambda obj: [e.value for e in obj]), comment="安全等级")
    severity_source = Column(Enum(SeveritySource, values_callable=lambda obj: [e.value for e in obj]), comment="等级来源")
    cvss_score = Column(Float, comment="CVSS 4.0基础分数")
    cvss_vector = Column(String(200), comment="CVSS 4.0向量字符串")
    affected_versions = Column(String(500), comment="影响版本")
    raw_content = Column(LONGTEXT, comment="原始内容（用于LLM分析）")
    is_processed = Column(Boolean, default=False, comment="是否已处理（分类、评级）")
    is_pushed = Column(Boolean, default=False, comment="是否已推送")
    is_security_event = Column(Boolean, default=None, comment="是否为安全事件(None=未判断)")
    is_keyword_filtered = Column(Boolean, default=False, comment="是否已进行关键词筛选")
    keyword_filter_passed = Column(Boolean, default=None, comment="关键词筛选是否通过(None=未筛选)")
    created_at = Column(DateTime, server_default=func.now(), comment="入库时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<RSSEvent(id={self.id}, title={self.title[:30]})>"
