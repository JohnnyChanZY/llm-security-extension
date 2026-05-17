"""
RSS数据源管理API路由（管理员）
"""
from typing import List
from datetime import datetime
import feedparser
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.rss_source import RSSSource
from app.schemas.rss_source import (
    RSSSourceCreate, RSSSourceUpdate, RSSSourceResponse, RSSValidateResponse
)
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin, not_found_exception
from app.tasks.rss_crawler import crawl_source, crawl_all_sources
from app.services.operation_logger import log_operation

router = APIRouter()


@router.get("", response_model=ResponseModel[List[RSSSourceResponse]])
def get_rss_sources(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取RSS数据源列表"""
    sources = db.query(RSSSource).order_by(RSSSource.id).all()
    return ResponseModel(
        code=0,
        data=[RSSSourceResponse.model_validate(s) for s in sources]
    )


@router.post("", response_model=ResponseModel[RSSSourceResponse])
def create_rss_source(
    source_data: RSSSourceCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """创建RSS数据源"""
    source = RSSSource(
        name=source_data.name,
        rss_url=source_data.rss_url,
        source_type=source_data.source_type,
        is_active=source_data.is_active,
        crawl_interval=source_data.crawl_interval
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    log_operation(
        db, user_id=current_admin.id, action="create_rss_source",
        target_type="rss_source", target_id=source.id,
        details=f"创建RSS数据源: {source.name}"
    )

    return ResponseModel(
        code=0,
        message="创建成功",
        data=RSSSourceResponse.model_validate(source)
    )


@router.put("/{source_id}", response_model=ResponseModel[RSSSourceResponse])
def update_rss_source(
    source_id: int,
    update_data: RSSSourceUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新RSS数据源"""
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()

    if not source:
        raise not_found_exception("RSS数据源不存在")

    if update_data.name is not None:
        source.name = update_data.name
    if update_data.rss_url is not None:
        source.rss_url = update_data.rss_url
    if update_data.source_type is not None:
        source.source_type = update_data.source_type
    if update_data.crawl_interval is not None:
        source.crawl_interval = update_data.crawl_interval
    if update_data.is_active is not None:
        source.is_active = update_data.is_active

    db.commit()
    db.refresh(source)

    log_operation(
        db, user_id=current_admin.id, action="update_rss_source",
        target_type="rss_source", target_id=source.id,
        details=f"更新RSS数据源: {source.name}"
    )

    return ResponseModel(
        code=0,
        message="更新成功",
        data=RSSSourceResponse.model_validate(source)
    )


@router.delete("/{source_id}", response_model=ResponseModel)
def delete_rss_source(
    source_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除RSS数据源"""
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()

    if not source:
        raise not_found_exception("RSS数据源不存在")

    source_name = source.name
    db.delete(source)
    db.commit()

    log_operation(
        db, user_id=current_admin.id, action="delete_rss_source",
        target_type="rss_source", target_id=source_id,
        details=f"删除RSS数据源: {source_name}"
    )

    return ResponseModel(code=0, message="删除成功")


@router.post("/{source_id}/validate", response_model=ResponseModel[RSSValidateResponse])
def validate_rss_source(
    source_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """验证RSS链接"""
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()

    if not source:
        raise not_found_exception("RSS数据源不存在")

    try:
        feed = feedparser.parse(source.rss_url)

        if feed.bozo and not feed.entries:
            return ResponseModel(
                code=3001,
                message="RSS链接无效",
                data=RSSValidateResponse(
                    valid=False,
                    message=str(feed.bozo_exception) if hasattr(feed, 'bozo_exception') else "解析失败"
                )
            )

        return ResponseModel(
            code=0,
            data=RSSValidateResponse(
                valid=True,
                message="验证成功",
                title=feed.feed.get('title', ''),
                item_count=len(feed.entries)
            )
        )

    except Exception as e:
        return ResponseModel(
            code=3001,
            message="RSS链接验证失败",
            data=RSSValidateResponse(
                valid=False,
                message=str(e)
            )
        )


@router.post("/actions/crawl-all", response_model=ResponseModel)
def trigger_crawl_all(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """手动触发爬取所有活跃的RSS源"""
    try:
        result = crawl_all_sources(db)

        total = result["total"]
        passed = result["passed_filter"]
        filtered = result["filtered"]
        sources_count = result["sources_count"]
        failed_count = result["failed_count"]

        if failed_count > 0:
            message = f"爬取完成，共处理 {sources_count} 个RSS源（{failed_count} 个失败），新增 {total} 条事件，其中 {passed} 条通过关键词筛选，{filtered} 条被过滤"
        else:
            message = f"爬取完成，共处理 {sources_count} 个RSS源，新增 {total} 条事件，其中 {passed} 条通过关键词筛选，{filtered} 条被过滤"

        return ResponseModel(
            code=0,
            message=message,
            data=result
        )
    except Exception as e:
        return ResponseModel(code=3002, message=f"爬取失败: {str(e)}")


@router.post("/{source_id}/crawl", response_model=ResponseModel)
def trigger_crawl(
    source_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """手动触发爬取单个RSS源"""
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()

    if not source:
        raise not_found_exception("RSS数据源不存在")

    # 执行爬取逻辑
    try:
        result = crawl_source(source, db)
        db.commit()

        # 构建返回消息
        total = result["total"]
        passed = result["passed_filter"]
        filtered = result["filtered"]

        if filtered > 0:
            message = f"爬取完成，新增 {total} 条事件，其中 {passed} 条通过关键词筛选，{filtered} 条被过滤"
        else:
            message = f"爬取完成，新增 {total} 条事件"

        return ResponseModel(
            code=0,
            message=message,
            data=result
        )
    except Exception as e:
        db.rollback()
        return ResponseModel(code=3002, message=f"爬取失败: {str(e)}")
