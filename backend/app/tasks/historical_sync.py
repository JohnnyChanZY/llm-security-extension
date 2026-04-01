"""
历史数据同步任务
"""
import logging
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.historical_event import HistoricalEvent
from app.services.nvd_collector import nvd_collector
from app.services.aiid_collector import aiid_collector
from app.services.aivd_collector import aivd_collector

logger = logging.getLogger(__name__)


def sync_all_sources():
    """同步所有历史数据源"""
    logger.info("开始同步历史数据...")

    sync_nvd()
    sync_aiid()
    sync_aivd()

    logger.info("历史数据同步完成")


def sync_nvd():
    """同步NVD数据（仅LLM相关CVE）"""
    logger.info("开始同步NVD数据（LLM相关）...")
    db = SessionLocal()
    try:
        # 只采集LLM相关的CVE
        cves = nvd_collector.collect_and_parse(days=7, llm_only=True)

        new_count = 0
        for cve in cves:
            # 检查是否已存在
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.cve_id == cve.get("cve_id")
            ).first()

            if not existing:
                event = HistoricalEvent(**cve)
                db.add(event)
                new_count += 1

        db.commit()
        logger.info(f"NVD数据同步完成，新增 {new_count} 条")

    except Exception as e:
        logger.error(f"NVD数据同步失败: {e}")
        db.rollback()
    finally:
        db.close()


def sync_aiid():
    """同步AIID数据"""
    logger.info("开始同步AIID数据...")
    db = SessionLocal()
    try:
        items = aiid_collector.collect()

        new_count = 0
        for item in items:
            # 检查是否已存在
            external_id = f"AIID-{item.get('report_number', '')}"
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.original_url == item.get("original_url")
            ).first()

            if not existing:
                event = HistoricalEvent(**item)
                db.add(event)
                new_count += 1

        db.commit()
        logger.info(f"AIID数据同步完成，新增 {new_count} 条")

    except Exception as e:
        logger.error(f"AIID数据同步失败: {e}")
        db.rollback()
    finally:
        db.close()


def sync_aivd():
    """同步AIVD数据"""
    logger.info("开始同步AIVD数据...")
    db = SessionLocal()
    try:
        items = aivd_collector.collect()

        new_count = 0
        for item in items:
            # 检查是否已存在
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.original_url == item.get("original_url")
            ).first()

            if not existing:
                event = HistoricalEvent(**item)
                db.add(event)
                new_count += 1

        db.commit()
        logger.info(f"AIVD数据同步完成，新增 {new_count} 条")

    except Exception as e:
        logger.error(f"AIVD数据同步失败: {e}")
        db.rollback()
    finally:
        db.close()
