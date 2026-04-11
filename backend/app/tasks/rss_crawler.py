"""
RSS爬虫任务
"""
import logging
from datetime import datetime
import feedparser
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.rss_source import RSSSource
from app.models.rss_event import RSSEvent
from app.services.keyword_filter import filter_rss_events_batch, is_keyword_filter_enabled, get_filter_keywords
from app.services.html_cleaner import clean_html

logger = logging.getLogger(__name__)


def crawl_all_sources(db: Session = None):
    """
    爬取所有活跃的RSS源

    Args:
        db: 数据库session，如果为None则自动创建

    Returns:
        dict: {
            "total": 新增事件总数,
            "passed_filter": 通过关键词筛选的数量,
            "filtered": 被过滤的数量,
            "sources_count": 处理的RSS源数量,
            "failed_count": 失败的RSS源数量
        }
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()

    try:
        sources = db.query(RSSSource).filter(RSSSource.is_active == True).all()

        total_stats = {
            "total": 0,
            "passed_filter": 0,
            "filtered": 0,
            "sources_count": len(sources),
            "failed_count": 0
        }

        for source in sources:
            try:
                result = crawl_source(source, db)
                total_stats["total"] += result["total"]
                total_stats["passed_filter"] += result["passed_filter"]
                total_stats["filtered"] += result["filtered"]
            except Exception as e:
                logger.error(f"爬取RSS源 {source.name} 失败: {e}")
                total_stats["failed_count"] += 1

        db.commit()
        logger.info(f"所有RSS源爬取完成: 新增 {total_stats['total']} 条，通过筛选 {total_stats['passed_filter']} 条，过滤 {total_stats['filtered']} 条")
        return total_stats
    finally:
        if own_db:
            db.close()


def crawl_source(source: RSSSource, db: Session) -> dict:
    """
    爬取单个RSS源

    Returns:
        dict: {
            "total": 新增事件总数,
            "passed_filter": 通过关键词筛选的数量,
            "filtered": 被过滤的数量
        }
    """
    logger.info(f"开始爬取RSS源: {source.name}")

    try:
        feed = feedparser.parse(source.rss_url)

        if feed.bozo and not feed.entries:
            logger.error(f"RSS解析失败: {source.rss_url}")
            return {"total": 0, "passed_filter": 0, "filtered": 0}

        new_events = []
        for entry in feed.entries:
            # 检查是否已存在
            url = entry.get('link', '')
            if url:
                existing = db.query(RSSEvent).filter(
                    RSSEvent.original_url == url
                ).first()
                if existing:
                    continue

            # 创建新事件
            event = RSSEvent(
                title=entry.get('title', ''),
                description=clean_html(entry.get('summary', '')),
                rss_source_id=source.id,
                source_name=source.name,
                original_url=url,
                published_at=datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') and entry.published_parsed else None,
                raw_content=str(entry),
                is_processed=False,
                is_pushed=False
            )
            db.add(event)
            new_events.append(event)

        # 对新事件进行关键词筛选
        filter_result = {"total": len(new_events), "passed": 0, "filtered": 0}
        if new_events:
            # 预加载配置以提高性能
            filter_enabled = is_keyword_filter_enabled(db)
            keywords = get_filter_keywords(db) if filter_enabled else []

            filter_result = filter_rss_events_batch(
                new_events,
                db,
                preloaded_keywords=keywords,
                filter_enabled=filter_enabled
            )
            logger.info(f"RSS源 {source.name} 关键词筛选: 通过 {filter_result['passed']} 条, 过滤 {filter_result['filtered']} 条")

        # 更新最后爬取时间
        source.last_crawled_at = datetime.now()

        logger.info(f"RSS源 {source.name} 爬取完成，新增 {len(new_events)} 条")

        return {
            "total": len(new_events),
            "passed_filter": filter_result["passed"],
            "filtered": filter_result["filtered"]
        }

    except Exception as e:
        logger.error(f"爬取RSS源 {source.name} 出错: {e}")
        raise
