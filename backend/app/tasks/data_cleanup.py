"""
数据清理任务
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.push_log import PushLog
from app.models.operation_log import OperationLog

logger = logging.getLogger(__name__)


def cleanup_old_data():
    """清理过期数据"""
    logger.info("开始清理过期数据...")

    cleanup_push_logs(days=90)
    cleanup_operation_logs(days=180)

    logger.info("数据清理完成")


def cleanup_push_logs(days: int = 90):
    """清理过期的推送日志"""
    db = SessionLocal()
    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        deleted = db.query(PushLog).filter(
            PushLog.created_at < cutoff_date
        ).delete()

        db.commit()
        logger.info(f"清理推送日志 {deleted} 条（保留 {days} 天）")

    except Exception as e:
        logger.error(f"清理推送日志失败: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_operation_logs(days: int = 180):
    """清理过期的操作日志"""
    db = SessionLocal()
    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        deleted = db.query(OperationLog).filter(
            OperationLog.created_at < cutoff_date
        ).delete()

        db.commit()
        logger.info(f"清理操作日志 {deleted} 条（保留 {days} 天）")

    except Exception as e:
        logger.error(f"清理操作日志失败: {e}")
        db.rollback()
    finally:
        db.close()
