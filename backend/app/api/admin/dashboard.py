"""
仪表盘统计数据API（管理员）
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.rss_source import RSSSource
from app.models.rss_event import RSSEvent
from app.models.historical_event import HistoricalEvent
from app.models.model import Model
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin

router = APIRouter()


@router.get("/stats", response_model=ResponseModel)
def get_dashboard_stats(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取仪表盘统计数据"""
    rss_count = db.query(RSSSource).filter(RSSSource.is_active == True).count()
    rss_event_count = db.query(RSSEvent).count()
    historical_count = db.query(HistoricalEvent).count()
    user_count = db.query(User).count()
    model_count = db.query(Model).filter(Model.is_active == True).count()

    return ResponseModel(data={
        "rssCount": rss_count,
        "rssEventCount": rss_event_count,
        "historicalCount": historical_count,
        "eventCount": rss_event_count + historical_count,
        "userCount": user_count,
        "modelCount": model_count
    })
