"""
历史安全事件数据模型
存储来自NVD、AIID、AIVD的历史数据
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float
from sqlalchemy.sql import func
from ..core.database import Base
import enum


class SeverityLevel(str, enum.Enum):
    """安全等级枚举"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SeveritySource(str, enum.Enum):
    """等级来源枚举"""
    NVD = "nvd"
    LLM = "llm"
    MANUAL = "manual"


class HistoricalEvent(Base):
    """历史安全事件表"""
    __tablename__ = "historical_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="事件标题")
    description = Column(Text, comment="事件描述/摘要")
    source_type = Column(String(20), index=True, nullable=False, comment="来源类型：nvd/aiid/aivd")
    source_name = Column(String(100), comment="来源平台名称")
    original_url = Column(String(500), index=True, comment="原文链接（去重依据）")
    published_at = Column(DateTime, index=True, comment="发布时间")
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    cve_id = Column(String(20), index=True, comment="CVE编号（去重依据）")
    severity = Column(Enum(SeverityLevel, values_callable=lambda obj: [e.value for e in obj]), comment="安全等级")
    severity_source = Column(Enum(SeveritySource, values_callable=lambda obj: [e.value for e in obj]), comment="等级来源")
    cvss_score = Column(Float, comment="CVSS 4.0基础分数")
    cvss_vector = Column(String(200), comment="CVSS 4.0向量字符串")
    affected_versions = Column(Text, comment="影响版本")
    raw_content = Column(Text, comment="原始内容")
    is_processed = Column(Boolean, default=False, comment="是否已处理")
    is_security_event = Column(Boolean, default=None, comment="是否为安全事件(None=未判断)")
    created_at = Column(DateTime, server_default=func.now(), comment="入库时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<HistoricalEvent(id={self.id}, title={self.title[:30]})>"
