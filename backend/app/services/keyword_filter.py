"""
关键词筛选服务
用于 RSS 数据的初步筛选，供爬虫和管理员 API 复用
"""
import json
import logging
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.models.rss_event import RSSEvent

logger = logging.getLogger(__name__)


def get_filter_keywords(db: Session) -> List[str]:
    """从数据库获取关键词列表

    Args:
        db: 数据库会话

    Returns:
        关键词列表
    """
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "filter_keywords"
    ).first()
    if config and config.config_value:
        try:
            keywords = json.loads(config.config_value)
            if isinstance(keywords, list):
                return keywords
        except json.JSONDecodeError:
            logger.error("关键词配置JSON解析失败")
    return []


def is_keyword_filter_enabled(db: Session) -> bool:
    """检查关键词筛选是否启用

    Args:
        db: 数据库会话

    Returns:
        是否启用关键词筛选
    """
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "keyword_filter_enabled"
    ).first()
    return config and config.config_value.lower() == "true"


def matches_keywords(content: str, keywords: List[str]) -> bool:
    """检查内容是否匹配关键词（不区分大小写）

    Args:
        content: 要检查的内容
        keywords: 关键词列表

    Returns:
        是否匹配任意关键词
    """
    if not content or not keywords:
        return False

    content_lower = content.lower()
    for keyword in keywords:
        if keyword and keyword.lower() in content_lower:
            return True
    return False


def filter_rss_event(event: RSSEvent, db: Session) -> Tuple[bool, bool]:
    """对单个 RSS 事件进行关键词筛选

    Args:
        event: RSS 事件对象
        db: 数据库会话

    Returns:
        (is_filtered, passed): 是否执行了筛选, 是否通过筛选
    """
    # 检查是否启用筛选
    filter_enabled = is_keyword_filter_enabled(db)

    if not filter_enabled:
        # 未启用筛选，标记为通过
        event.is_keyword_filtered = True
        event.keyword_filter_passed = True
        return True, True

    # 获取关键词列表
    keywords = get_filter_keywords(db)
    if not keywords:
        # 无关键词配置，标记为通过
        event.is_keyword_filtered = True
        event.keyword_filter_passed = True
        return True, True

    # 执行筛选
    content = f"{event.title} {event.description or ''} {event.raw_content or ''}"
    passed = matches_keywords(content, keywords)

    event.is_keyword_filtered = True
    event.keyword_filter_passed = passed

    if passed:
        logger.debug(f"RSS事件 {event.id} 通过关键词筛选: {event.title[:50]}")
    else:
        logger.debug(f"RSS事件 {event.id} 未通过关键词筛选: {event.title[:50]}")

    return True, passed


def filter_rss_events_batch(
    events: List[RSSEvent],
    db: Session,
    preloaded_keywords: Optional[List[str]] = None,
    filter_enabled: Optional[bool] = None
) -> dict:
    """批量筛选 RSS 事件

    预加载配置以提高性能，避免每次循环都查询数据库

    Args:
        events: RSS 事件列表
        db: 数据库会话
        preloaded_keywords: 预加载的关键词列表（可选）
        filter_enabled: 预加载的筛选开关状态（可选）

    Returns:
        统计信息: {"total": N, "passed": N, "filtered": N}
    """
    if not events:
        return {"total": 0, "passed": 0, "filtered": 0}

    # 如果未预加载配置，则查询数据库
    if filter_enabled is None:
        filter_enabled = is_keyword_filter_enabled(db)

    if preloaded_keywords is None and filter_enabled:
        preloaded_keywords = get_filter_keywords(db)

    keywords = preloaded_keywords or []

    total = len(events)
    passed_count = 0

    for event in events:
        if filter_enabled and keywords:
            content = f"{event.title} {event.description or ''} {event.raw_content or ''}"
            passed = matches_keywords(content, keywords)
            event.is_keyword_filtered = True
            event.keyword_filter_passed = passed
        else:
            event.is_keyword_filtered = True
            event.keyword_filter_passed = True

        if event.keyword_filter_passed:
            passed_count += 1

    result = {
        "total": total,
        "passed": passed_count,
        "filtered": total - passed_count
    }

    logger.info(f"批量关键词筛选完成: 总计 {total} 条，通过 {passed_count} 条，过滤 {total - passed_count} 条")

    return result


def get_filter_config(db: Session) -> dict:
    """获取关键词筛选配置信息

    Args:
        db: 数据库会话

    Returns:
        配置信息字典
    """
    enabled = is_keyword_filter_enabled(db)
    keywords = get_filter_keywords(db) if enabled else []

    return {
        "enabled": enabled,
        "keywords": keywords,
        "keyword_count": len(keywords)
    }
