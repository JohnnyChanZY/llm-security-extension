"""
事件推送任务
"""
import logging
import json
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.rss_event import RSSEvent
from app.models.user_preference import UserPreference
from app.models.push_log import PushLog, PushStatus, PushChannel
from app.models.event_model import EventModel

logger = logging.getLogger(__name__)

# WebSocket连接管理
_active_connections = {}


def push_pending_events():
    """推送待处理的事件"""
    from app.api.websocket import manager as ws_manager

    db = SessionLocal()
    try:
        # 获取未推送、已处理、且确认为安全事件的事件
        events = db.query(RSSEvent).filter(
            RSSEvent.is_pushed == False,
            RSSEvent.is_processed == True,
            RSSEvent.is_security_event == True
        ).limit(50).all()

        for event in events:
            try:
                push_event(event, db, ws_manager)
            except Exception as e:
                logger.error(f"推送事件 {event.id} 失败: {e}")

        db.commit()

    finally:
        db.close()


def push_event(event: RSSEvent, db: Session, ws_manager):
    """推送单个事件"""
    # 查找匹配的用户
    matched_users = find_matched_users(event, db)

    if not matched_users:
        # 没有匹配的用户，标记为已推送
        event.is_pushed = True
        return

    # 构建推送消息
    message = {
        "type": "new_event",
        "data": {
            "id": event.id,
            "title": event.title,
            "severity": event.severity,
            "category": event.category_id,
            "published_at": event.published_at.isoformat() if event.published_at else None
        }
    }

    # 推送给每个匹配的用户
    for user_id in matched_users:
        try:
            # 通过WebSocket推送
            sent = ws_manager.send_personal_message(json.dumps(message), user_id)

            # 记录推送日志
            log = PushLog(
                user_id=user_id,
                event_type="rss",
                event_id=event.id,
                push_channel=PushChannel.EXTENSION,
                push_status=PushStatus.SUCCESS if sent else PushStatus.FAILED,
                pushed_at=datetime.datetime.now() if sent else None,
                error_message=None if sent else "WebSocket连接不存在"
            )
            db.add(log)

        except Exception as e:
            logger.error(f"推送给用户 {user_id} 失败: {e}")
            log = PushLog(
                user_id=user_id,
                event_type="rss",
                event_id=event.id,
                push_channel=PushChannel.EXTENSION,
                push_status=PushStatus.FAILED,
                error_message=str(e)
            )
            db.add(log)

    # 标记为已推送
    event.is_pushed = True


def find_matched_users(event: RSSEvent, db: Session) -> list:
    """查找匹配用户偏好设置的用户"""
    # 获取事件关联的模型
    event_models = db.query(EventModel).filter(
        EventModel.event_type == "rss",
        EventModel.event_id == event.id
    ).all()
    model_ids = [em.model_id for em in event_models]

    # 查询匹配的用户偏好
    query = db.query(UserPreference).filter(UserPreference.is_enabled == True)

    # 匹配分类或模型
    if event.category_id or model_ids:
        from sqlalchemy import or_
        conditions = []
        if event.category_id:
            conditions.append(UserPreference.category_id == event.category_id)
        if model_ids:
            conditions.append(UserPreference.model_id.in_(model_ids))

        query = query.filter(or_(*conditions))

    preferences = query.all()

    # 返回唯一的用户ID列表
    return list(set(p.user_id for p in preferences))


import datetime
