"""
LLM 事件管理 API（管理员）
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.database import get_db
from app.models.user import User
from app.models.rss_event import RSSEvent
from app.models.historical_event import HistoricalEvent
from app.models.category import Category
from app.schemas.response import ResponseModel, PaginatedData, PaginatedResponse
from app.schemas.event import SeverityLevel
from app.api.deps import get_current_admin
from app.services.operation_logger import log_operation

router = APIRouter()


class AdminEventResponse:
    """管理员事件响应"""
    def __init__(
        self,
        id: int,
        title: str,
        description: Optional[str],
        source_type: Optional[str],
        source_name: Optional[str],
        original_url: Optional[str],
        published_at: Optional[str],
        category_id: Optional[int],
        category_name: Optional[str],
        severity: Optional[str],
        severity_source: Optional[str],
        is_processed: bool,
        is_security_event: Optional[bool],
        created_at: str
    ):
        self.id = id
        self.title = title
        self.description = description
        self.source_type = source_type
        self.source_name = source_name
        self.original_url = original_url
        self.published_at = published_at
        self.category_id = category_id
        self.category_name = category_name
        self.severity = severity
        self.severity_source = severity_source
        self.is_processed = is_processed
        self.is_security_event = is_security_event
        self.created_at = created_at


@router.get("", response_model=PaginatedResponse)
def get_events(
    source_type: Optional[str] = Query(None, description="数据源类型: nvd/aiid/aivd/rss"),
    is_processed: Optional[bool] = Query(None, description="是否已处理"),
    is_security_event: Optional[bool] = Query(None, description="是否为安全事件"),
    severity: Optional[str] = Query(None, description="安全等级: low/medium/high/critical"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    show_filtered: bool = Query(False, description="是否显示未通过筛选的RSS数据"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    获取事件列表（支持数据源筛选）

    - source_type: 数据源类型（nvd/aiid/aivd/rss）
    - is_processed: 是否已处理
    - is_security_event: 是否为安全事件
    - severity: 安全等级
    - keyword: 关键词搜索（标题/描述）
    - show_filtered: 是否显示未通过关键词筛选的RSS数据（默认不显示）
    """
    # 构建查询
    items = []
    total = 0

    # 获取分类映射
    categories = db.query(Category).all()
    category_map = {c.id: c.name for c in categories}

    # 根据 source_type 决定查询哪个表
    if source_type == "rss":
        # 仅查询 RSS 事件
        items, total = _query_rss_events(
            db, is_processed, is_security_event, severity, keyword, page, page_size, category_map,
            show_filtered=show_filtered
        )
    elif source_type in ["nvd", "aiid", "aivd"]:
        # 查询指定来源的历史事件
        items, total = _query_historical_events(
            db, source_type, is_processed, is_security_event, severity, keyword, page, page_size, category_map
        )
    else:
        # 查询所有事件 - 需要先获取总数，再合并分页
        # 1. 先获取两个表的总数
        rss_total = _count_rss_events(db, is_processed, is_security_event, severity, keyword, show_filtered=show_filtered)
        hist_total = _count_historical_events(db, None, is_processed, is_security_event, severity, keyword)
        total = rss_total + hist_total

        # 2. 获取所有符合条件的数据用于合并排序
        # 由于两个表需要合并后按时间排序分页，必须获取全部数据
        # 对于管理员后台，数据量通常可控，直接内存分页
        rss_items, _ = _query_rss_events(
            db, is_processed, is_security_event, severity, keyword, 1, rss_total if rss_total > 0 else 1, category_map,
            show_filtered=show_filtered
        )
        hist_items, _ = _query_historical_events(
            db, None, is_processed, is_security_event, severity, keyword, 1, hist_total if hist_total > 0 else 1, category_map
        )

        # 3. 合并结果并按时间排序
        all_items = rss_items + hist_items
        all_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 4. 内存分页
        start = (page - 1) * page_size
        items = all_items[start:start + page_size]

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )


def _apply_event_filters(query, model, is_processed, is_security_event, severity, keyword):
    """应用通用的事件过滤条件"""
    if is_processed is not None:
        query = query.filter(model.is_processed == is_processed)
    if is_security_event is not None:
        query = query.filter(model.is_security_event == is_security_event)
    if severity:
        query = query.filter(model.severity == severity)
    if keyword:
        query = query.filter(
            or_(
                model.title.contains(keyword),
                model.description.contains(keyword)
            )
        )
    return query


def _count_rss_events(
    db: Session,
    is_processed: Optional[bool],
    is_security_event: Optional[bool],
    severity: Optional[str],
    keyword: Optional[str],
    show_filtered: bool = False
) -> int:
    """统计符合条件的 RSS 事件总数"""
    query = db.query(RSSEvent)

    if not show_filtered:
        query = query.filter(
            or_(
                RSSEvent.keyword_filter_passed == True,
                RSSEvent.keyword_filter_passed == None
            )
        )

    query = _apply_event_filters(query, RSSEvent, is_processed, is_security_event, severity, keyword)
    return query.count()


def _count_historical_events(
    db: Session,
    source_type: Optional[str],
    is_processed: Optional[bool],
    is_security_event: Optional[bool],
    severity: Optional[str],
    keyword: Optional[str]
) -> int:
    """统计符合条件的历史事件总数"""
    query = db.query(HistoricalEvent)

    if source_type:
        query = query.filter(HistoricalEvent.source_type == source_type)

    query = _apply_event_filters(query, HistoricalEvent, is_processed, is_security_event, severity, keyword)
    return query.count()


def _query_rss_events(
    db: Session,
    is_processed: Optional[bool],
    is_security_event: Optional[bool],
    severity: Optional[str],
    keyword: Optional[str],
    page: int,
    page_size: int,
    category_map: dict,
    show_filtered: bool = False
):
    """查询 RSS 事件"""
    query = db.query(RSSEvent)

    # 默认只显示通过关键词筛选的RSS数据
    if not show_filtered:
        query = query.filter(
            or_(
                RSSEvent.keyword_filter_passed == True,
                RSSEvent.keyword_filter_passed == None  # 兼容旧数据
            )
        )

    query = _apply_event_filters(query, RSSEvent, is_processed, is_security_event, severity, keyword)

    total = query.count()
    events = query.order_by(RSSEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [_format_rss_event(e, category_map) for e in events]
    return items, total


def _query_historical_events(
    db: Session,
    source_type: Optional[str],
    is_processed: Optional[bool],
    is_security_event: Optional[bool],
    severity: Optional[str],
    keyword: Optional[str],
    page: int,
    page_size: int,
    category_map: dict
):
    """查询历史事件"""
    query = db.query(HistoricalEvent)

    if source_type:
        query = query.filter(HistoricalEvent.source_type == source_type)

    query = _apply_event_filters(query, HistoricalEvent, is_processed, is_security_event, severity, keyword)

    total = query.count()
    events = query.order_by(HistoricalEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [_format_historical_event(e, category_map) for e in events]
    return items, total


def _format_rss_event(event: RSSEvent, category_map: dict) -> dict:
    """格式化 RSS 事件"""
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "source_type": "rss",
        "source_name": event.source_name,
        "original_url": event.original_url,
        "published_at": event.published_at.isoformat() if event.published_at else None,
        "category_id": event.category_id,
        "category_name": category_map.get(event.category_id),
        "severity": event.severity.value if event.severity else None,
        "severity_source": event.severity_source.value if event.severity_source else None,
        "is_processed": event.is_processed,
        "is_security_event": event.is_security_event,
        "is_keyword_filtered": event.is_keyword_filtered,
        "keyword_filter_passed": event.keyword_filter_passed,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "event_table": "rss"
    }


def _format_historical_event(event: HistoricalEvent, category_map: dict) -> dict:
    """格式化历史事件"""
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "source_type": event.source_type,
        "source_name": event.source_name,
        "original_url": event.original_url,
        "published_at": event.published_at.isoformat() if event.published_at else None,
        "category_id": event.category_id,
        "category_name": category_map.get(event.category_id),
        "severity": event.severity.value if event.severity else None,
        "severity_source": event.severity_source.value if event.severity_source else None,
        "is_processed": event.is_processed,
        "is_security_event": event.is_security_event,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "event_table": "historical"
    }


@router.delete("/rss/{event_id}", response_model=ResponseModel)
def delete_rss_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除 RSS 事件"""
    event = db.query(RSSEvent).filter(RSSEvent.id == event_id).first()
    if not event:
        return ResponseModel(code=1, message="事件不存在")

    db.delete(event)
    db.commit()

    log_operation(
        db, user_id=current_admin.id, action="delete_rss_event",
        target_type="rss_event", target_id=event_id,
        details=f"删除RSS事件: ID={event_id}"
    )

    return ResponseModel(message="删除成功")


@router.delete("/historical/{event_id}", response_model=ResponseModel)
def delete_historical_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除历史事件"""
    event = db.query(HistoricalEvent).filter(HistoricalEvent.id == event_id).first()
    if not event:
        return ResponseModel(code=1, message="事件不存在")

    db.delete(event)
    db.commit()

    log_operation(
        db, user_id=current_admin.id, action="delete_historical_event",
        target_type="historical_event", target_id=event_id,
        details=f"删除历史事件: ID={event_id}"
    )

    return ResponseModel(message="删除成功")


@router.post("/batch-delete", response_model=ResponseModel)
def batch_delete_events(
    event_ids: List[int],
    event_table: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    批量删除事件

    - event_ids: 事件ID列表
    - event_table: 事件表类型 (rss/historical)
    """
    if event_table not in ["rss", "historical"]:
        return ResponseModel(code=1, message="event_table 必须是 rss 或 historical")

    Model = RSSEvent if event_table == "rss" else HistoricalEvent

    deleted = db.query(Model).filter(Model.id.in_(event_ids)).delete(synchronize_session=False)
    db.commit()

    log_operation(
        db, user_id=current_admin.id, action="batch_delete_events",
        target_type=event_table + "_event",
        details=f"批量删除 {deleted} 条{event_table}事件"
    )

    return ResponseModel(message=f"成功删除 {deleted} 条事件", data={"deleted": deleted})


@router.get("/stats", response_model=ResponseModel)
def get_event_stats(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取事件统计"""
    # RSS 事件统计
    rss_total = db.query(RSSEvent).count()
    rss_processed = db.query(RSSEvent).filter(RSSEvent.is_processed == True).count()
    rss_security = db.query(RSSEvent).filter(RSSEvent.is_security_event == True).count()
    rss_non_security = db.query(RSSEvent).filter(RSSEvent.is_security_event == False).count()
    rss_unchecked = db.query(RSSEvent).filter(RSSEvent.is_security_event == None).count()

    # RSS 关键词筛选统计
    rss_filtered = db.query(RSSEvent).filter(RSSEvent.keyword_filter_passed == False).count()
    rss_passed_filter = db.query(RSSEvent).filter(RSSEvent.keyword_filter_passed == True).count()

    # 历史事件统计
    hist_total = db.query(HistoricalEvent).count()
    hist_processed = db.query(HistoricalEvent).filter(HistoricalEvent.is_processed == True).count()
    hist_security = db.query(HistoricalEvent).filter(HistoricalEvent.is_security_event == True).count()
    hist_non_security = db.query(HistoricalEvent).filter(HistoricalEvent.is_security_event == False).count()
    hist_unchecked = db.query(HistoricalEvent).filter(HistoricalEvent.is_security_event == None).count()

    # 按来源统计
    nvd_count = db.query(HistoricalEvent).filter(HistoricalEvent.source_type == "nvd").count()
    aiid_count = db.query(HistoricalEvent).filter(HistoricalEvent.source_type == "aiid").count()
    aivd_count = db.query(HistoricalEvent).filter(HistoricalEvent.source_type == "aivd").count()

    return ResponseModel(data={
        "rss": {
            "total": rss_total,
            "processed": rss_processed,
            "security": rss_security,
            "non_security": rss_non_security,
            "unchecked": rss_unchecked,
            "filtered": rss_filtered,
            "passed_filter": rss_passed_filter
        },
        "historical": {
            "total": hist_total,
            "processed": hist_processed,
            "security": hist_security,
            "non_security": hist_non_security,
            "unchecked": hist_unchecked
        },
        "by_source": {
            "nvd": nvd_count,
            "aiid": aiid_count,
            "aivd": aivd_count,
            "rss": rss_total,
            "rss_passed_filter": rss_passed_filter
        }
    })
