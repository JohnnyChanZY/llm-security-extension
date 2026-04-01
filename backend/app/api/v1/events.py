"""
事件API路由
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.user import User
from app.models.historical_event import HistoricalEvent
from app.models.rss_event import RSSEvent
from app.models.category import Category
from app.models.event_model import EventModel
from app.models.model import Model
from app.schemas.event import (
    EventResponse, EventListResponse, EventFilter,
    CategoryInfo, RelatedModel
)
from app.schemas.response import ResponseModel
from app.api.deps import get_current_user

router = APIRouter()


def build_event_response(event, event_type: str, db: Session) -> EventResponse:
    """构建事件响应对象"""
    # 获取分类信息
    category_info = None
    if event.category_id:
        category = db.query(Category).filter(Category.id == event.category_id).first()
        if category:
            category_info = CategoryInfo(
                id=category.id,
                code=category.code,
                name=category.name
            )

    # 获取关联模型
    event_models = db.query(EventModel).filter(
        EventModel.event_type == event_type,
        EventModel.event_id == event.id
    ).all()

    affected_models = []
    for em in event_models:
        model = db.query(Model).filter(Model.id == em.model_id).first()
        if model:
            affected_models.append(RelatedModel(
                id=model.id,
                name=model.name,
                vendor=model.vendor
            ))

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        source_type=event.source_type if hasattr(event, 'source_type') else event_type,
        source_name=event.source_name,
        original_url=event.original_url,
        published_at=event.published_at,
        category=category_info,
        cve_id=event.cve_id,
        severity=event.severity,
        severity_source=event.severity_source,
        affected_models=affected_models,
        created_at=event.created_at
    )


@router.get("", response_model=ResponseModel[EventListResponse])
def get_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    model_id: Optional[int] = None,
    severity: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keyword: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取事件列表"""
    # 查询历史事件
    historical_query = db.query(HistoricalEvent)
    # 查询RSS事件
    rss_query = db.query(RSSEvent)

    # 应用筛选条件
    if category:
        category_obj = db.query(Category).filter(Category.code == category).first()
        if category_obj:
            historical_query = historical_query.filter(HistoricalEvent.category_id == category_obj.id)
            rss_query = rss_query.filter(RSSEvent.category_id == category_obj.id)

    if severity:
        historical_query = historical_query.filter(HistoricalEvent.severity == severity)
        rss_query = rss_query.filter(RSSEvent.severity == severity)

    if start_date:
        historical_query = historical_query.filter(HistoricalEvent.published_at >= start_date)
        rss_query = rss_query.filter(RSSEvent.published_at >= start_date)

    if end_date:
        historical_query = historical_query.filter(HistoricalEvent.published_at <= end_date)
        rss_query = rss_query.filter(RSSEvent.published_at <= end_date)

    if keyword:
        keyword_filter = or_(
            HistoricalEvent.title.contains(keyword),
            HistoricalEvent.description.contains(keyword)
        )
        historical_query = historical_query.filter(keyword_filter)
        rss_keyword_filter = or_(
            RSSEvent.title.contains(keyword),
            RSSEvent.description.contains(keyword)
        )
        rss_query = rss_query.filter(rss_keyword_filter)

    if model_id:
        # 通过event_models表关联筛选
        historical_ids = db.query(EventModel.event_id).filter(
            EventModel.event_type == "historical",
            EventModel.model_id == model_id
        ).all()
        historical_ids = [i[0] for i in historical_ids]
        historical_query = historical_query.filter(HistoricalEvent.id.in_(historical_ids))

        rss_ids = db.query(EventModel.event_id).filter(
            EventModel.event_type == "rss",
            EventModel.model_id == model_id
        ).all()
        rss_ids = [i[0] for i in rss_ids]
        rss_query = rss_query.filter(RSSEvent.id.in_(rss_ids))

    # 获取总数
    historical_total = historical_query.count()
    rss_total = rss_query.count()
    total = historical_total + rss_total

    # 分页
    offset = (page - 1) * page_size

    # 合并查询结果
    historical_events = historical_query.order_by(HistoricalEvent.published_at.desc()).offset(offset).limit(page_size).all()
    rss_events = rss_query.order_by(RSSEvent.published_at.desc()).offset(offset).limit(page_size).all()

    # 合并并排序
    all_events = []
    for event in historical_events:
        all_events.append((event, "historical", event.published_at or datetime.min))
    for event in rss_events:
        all_events.append((event, "rss", event.published_at or datetime.min))

    all_events.sort(key=lambda x: x[2], reverse=True)
    all_events = all_events[:page_size]

    # 构建响应
    items = []
    for event, event_type, _ in all_events:
        items.append(build_event_response(event, event_type, db))

    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=0,
        data=EventListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )


@router.get("/unread-count", response_model=ResponseModel)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取未读事件数量"""
    # 这里简化处理，返回最近的未处理事件数量
    # 实际应该有用户已读记录表
    count = db.query(RSSEvent).filter(RSSEvent.is_pushed == False).count()
    return ResponseModel(
        code=0,
        data={"count": count}
    )


@router.get("/recommend", response_model=ResponseModel[EventListResponse])
def get_recommend_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取推荐事件（全部最新事件）"""
    query = db.query(RSSEvent)

    # 应用分类过滤
    if category:
        category_obj = db.query(Category).filter(Category.code == category).first()
        if category_obj:
            query = query.filter(RSSEvent.category_id == category_obj.id)

    total = query.count()
    rss_events = query.order_by(RSSEvent.published_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_event_response(event, "rss", db) for event in rss_events]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=0,
        data=EventListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )


@router.get("/subscribed", response_model=ResponseModel[EventListResponse])
def get_subscribed_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取订阅事件（按用户偏好筛选）

    使用 OR 逻辑：事件匹配任一偏好条件（分类或模型）即返回
    """
    from app.models.user_preference import UserPreference
    from sqlalchemy import or_, and_

    # 获取用户偏好
    preferences = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id,
        UserPreference.is_enabled == True
    ).all()

    if not preferences:
        # 无偏好设置，返回空列表
        return ResponseModel(
            code=0,
            data=EventListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )
        )

    # 获取偏好的模型ID和分类ID
    model_ids = [p.model_id for p in preferences if p.model_id]
    category_ids = [p.category_id for p in preferences if p.category_id]

    # 如果既没有模型偏好也没有分类偏好，返回空列表
    if not model_ids and not category_ids:
        return ResponseModel(
            code=0,
            data=EventListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )
        )

    # 构建 OR 条件：匹配分类或匹配模型
    conditions = []

    # 分类匹配条件
    if category_ids:
        conditions.append(RSSEvent.category_id.in_(category_ids))

    # 模型匹配条件
    if model_ids:
        event_ids_by_model = db.query(EventModel.event_id).filter(
            EventModel.event_type == "rss",
            EventModel.model_id.in_(model_ids)
        ).subquery()
        conditions.append(RSSEvent.id.in_(event_ids_by_model))

    # 查询匹配的RSS事件
    query = db.query(RSSEvent).filter(or_(*conditions))

    # 应用额外的分类参数过滤（用户在UI上选择的分类）
    if category:
        category_obj = db.query(Category).filter(Category.code == category).first()
        if category_obj:
            query = query.filter(RSSEvent.category_id == category_obj.id)

    total = query.count()
    events = query.order_by(RSSEvent.published_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_event_response(event, "rss", db) for event in events]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=0,
        data=EventListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )


@router.get("/{event_id}", response_model=ResponseModel[EventResponse])
def get_event_detail(
    event_id: int,
    event_type: str = Query("historical", regex="^(historical|rss)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取事件详情"""
    if event_type == "historical":
        event = db.query(HistoricalEvent).filter(HistoricalEvent.id == event_id).first()
    else:
        event = db.query(RSSEvent).filter(RSSEvent.id == event_id).first()

    if not event:
        return ResponseModel(
            code=1005,
            message="事件不存在",
            data=None
        )

    return ResponseModel(
        code=0,
        data=build_event_response(event, event_type, db)
    )
