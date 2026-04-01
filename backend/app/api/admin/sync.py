"""
数据同步API路由（管理员）
手动触发历史数据源的一次性同步
"""
from typing import Dict
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db, SessionLocal
from app.models.user import User
from app.models.historical_event import HistoricalEvent
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin
from app.services.nvd_collector import nvd_collector
from app.services.aiid_collector import aiid_collector
from app.services.aivd_collector import aivd_collector

router = APIRouter()


class SyncResult(BaseModel):
    """同步结果模型"""
    source: str
    new_count: int
    total_count: int
    message: str


def sync_nvd_task(days: int = 30, llm_only: bool = False) -> Dict:
    """
    NVD同步任务（后台执行）
    默认同步最近30天的数据，用于初次建库

    Args:
        days: 同步最近N天的数据
        llm_only: 是否只同步LLM相关的CVE
    """
    db = SessionLocal()
    try:
        cves = nvd_collector.collect_and_parse(days=days, llm_only=llm_only)

        new_count = 0
        for cve in cves:
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.cve_id == cve.get("cve_id")
            ).first()

            if not existing:
                event = HistoricalEvent(**cve)
                db.add(event)
                new_count += 1

        db.commit()
        total_count = db.query(HistoricalEvent).filter(
            HistoricalEvent.source_type == "nvd"
        ).count()

        return {
            "source": "NVD",
            "new_count": new_count,
            "total_count": total_count,
            "message": f"成功同步 {new_count} 条新数据，数据库中共有 {total_count} 条NVD记录"
        }

    except Exception as e:
        db.rollback()
        return {
            "source": "NVD",
            "new_count": 0,
            "total_count": 0,
            "message": f"同步失败: {str(e)}"
        }
    finally:
        db.close()


def sync_aiid_task() -> Dict:
    """AIID同步任务（后台执行）"""
    db = SessionLocal()
    try:
        items = aiid_collector.collect()

        new_count = 0
        for item in items:
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.original_url == item.get("original_url")
            ).first()

            if not existing:
                event = HistoricalEvent(**item)
                db.add(event)
                new_count += 1

        db.commit()
        total_count = db.query(HistoricalEvent).filter(
            HistoricalEvent.source_type == "aiid"
        ).count()

        return {
            "source": "AIID",
            "new_count": new_count,
            "total_count": total_count,
            "message": f"成功同步 {new_count} 条新数据，数据库中共有 {total_count} 条AIID记录"
        }

    except Exception as e:
        db.rollback()
        return {
            "source": "AIID",
            "new_count": 0,
            "total_count": 0,
            "message": f"同步失败: {str(e)}"
        }
    finally:
        db.close()


def sync_aivd_task() -> Dict:
    """AIVD同步任务（后台执行）"""
    db = SessionLocal()
    try:
        items = aivd_collector.collect()

        new_count = 0
        for item in items:
            existing = db.query(HistoricalEvent).filter(
                HistoricalEvent.original_url == item.get("original_url")
            ).first()

            if not existing:
                event = HistoricalEvent(**item)
                db.add(event)
                new_count += 1

        db.commit()
        total_count = db.query(HistoricalEvent).filter(
            HistoricalEvent.source_type == "aivd"
        ).count()

        return {
            "source": "AIVD",
            "new_count": new_count,
            "total_count": total_count,
            "message": f"成功同步 {new_count} 条新数据，数据库中共有 {total_count} 条AIVD记录"
        }

    except Exception as e:
        db.rollback()
        return {
            "source": "AIVD",
            "new_count": 0,
            "total_count": 0,
            "message": f"同步失败: {str(e)}"
        }
    finally:
        db.close()


@router.post("/nvd", response_model=ResponseModel[SyncResult])
def sync_nvd(
    background_tasks: BackgroundTasks,
    days: int = 30,
    llm_only: bool = True,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    触发NVD数据同步

    Args:
        days: 同步最近N天的数据，默认30天
        llm_only: 是否只同步LLM相关的CVE，默认True
    """
    result = sync_nvd_task(days=days, llm_only=llm_only)
    return ResponseModel(
        code=0,
        message="同步完成",
        data=SyncResult(**result)
    )


@router.post("/aiid", response_model=ResponseModel[SyncResult])
def sync_aiid(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """触发AIID数据同步"""
    result = sync_aiid_task()
    return ResponseModel(
        code=0,
        message="同步完成",
        data=SyncResult(**result)
    )


@router.post("/aivd", response_model=ResponseModel[SyncResult])
def sync_aivd(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """触发AIVD数据同步"""
    result = sync_aivd_task()
    return ResponseModel(
        code=0,
        message="同步完成",
        data=SyncResult(**result)
    )
