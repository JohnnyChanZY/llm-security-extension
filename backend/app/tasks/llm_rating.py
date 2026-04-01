"""
LLM自动评级任务
支持批量处理，评级与分类分开处理
采用串行处理：一次发送一批请求，间隔后发送下一批
支持流式更新：每批处理完后提交数据库并更新状态
"""
import logging
import json
import time
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.system_config import SystemConfig
from app.models.rss_event import RSSEvent
from app.models.historical_event import HistoricalEvent
from app.models.category import Category
from app.models.event_model import EventModel
from app.services.llm_service import get_llm_service, get_batch_size, MAX_BATCH_SIZE_LIMIT
from app.services.model_matcher import match_event_models

logger = logging.getLogger(__name__)

# 默认分类代码
DEFAULT_CATEGORY_CODE = "other"

# 请求间隔上限（秒）
MAX_REQUEST_INTERVAL_LIMIT = 60

# 全局状态（供状态查询接口使用）
_rating_status = {
    "running": False,
    "total": 0,
    "processed": 0,
    "current_batch": 0,
    "total_batches": 0,
    "error": None,
    "mode": None,
    "event_type": None
}


def get_rating_status() -> dict:
    """获取当前评级任务状态"""
    return _rating_status.copy()


def get_request_interval(db: Session) -> float:
    """获取请求间隔时间（秒）"""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "llm_request_interval"
    ).first()
    if config and config.config_value:
        try:
            return min(float(config.config_value), MAX_REQUEST_INTERVAL_LIMIT)
        except ValueError:
            pass
    return 2.0  # 默认值


def get_configured_batch_size(db: Session) -> int:
    """获取配置的批次大小"""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "llm_batch_size"
    ).first()
    if config and config.config_value:
        try:
            return min(int(config.config_value), MAX_BATCH_SIZE_LIMIT)
        except ValueError:
            pass
    return get_batch_size()


def matches_keywords(content: str, keywords: list) -> bool:
    """检查内容是否匹配关键词"""
    content_lower = content.lower()
    for keyword in keywords:
        if keyword.lower() in content_lower:
            return True
    return False


def auto_rate_events():
    """自动评级未处理的事件（后台任务）"""
    global _rating_status

    if _rating_status["running"]:
        logger.warning("已有评级任务在运行中")
        return

    db = SessionLocal()

    try:
        # 检查LLM评级开关
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "llm_rating_enabled"
        ).first()

        if not config or config.config_value.lower() != "true":
            logger.debug("LLM自动评级未启用")
            return

        batch_size = get_configured_batch_size(db)
        request_interval = get_request_interval(db)

        # 获取关键词筛选配置
        keyword_filter_config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "keyword_filter_enabled"
        ).first()
        keyword_filter_enabled = (keyword_filter_config and
                                  keyword_filter_config.config_value.lower() == "true")

        keywords = []
        if keyword_filter_enabled:
            keywords_config = db.query(SystemConfig).filter(
                SystemConfig.config_key == "filter_keywords"
            ).first()
            if keywords_config:
                try:
                    keywords = json.loads(keywords_config.config_value)
                except json.JSONDecodeError:
                    logger.error("关键词配置JSON解析失败")
                    keywords = []

        # 获取所有未处理的事件
        rss_events = db.query(RSSEvent).filter(
            RSSEvent.is_security_event == None,
            RSSEvent.is_processed == False
        ).all()

        historical_events = db.query(HistoricalEvent).filter(
            HistoricalEvent.is_security_event == None,
            HistoricalEvent.is_processed == False
        ).all()

        if not rss_events and not historical_events:
            logger.debug("没有待处理的事件")
            return

        # 分批
        rss_batches = [rss_events[i:i + batch_size] for i in range(0, len(rss_events), batch_size)]
        historical_batches = [historical_events[i:i + batch_size] for i in range(0, len(historical_events), batch_size)]

        all_batches = [(batch, "RSS") for batch in rss_batches] + [(batch, "Historical") for batch in historical_batches]

        if not all_batches:
            logger.debug("没有待处理的事件")
            return

        total_events = len(rss_events) + len(historical_events)
        total_batches = len(all_batches)

        # 初始化状态
        _rating_status["running"] = True
        _rating_status["total"] = total_events
        _rating_status["processed"] = 0
        _rating_status["current_batch"] = 0
        _rating_status["total_batches"] = total_batches
        _rating_status["error"] = None
        _rating_status["mode"] = "auto"

        logger.info(
            f"开始串行处理: 共 {total_events} 条事件, "
            f"{total_batches} 批, 批次大小 {batch_size}, 间隔 {request_interval}秒"
        )

        llm_service = get_llm_service()
        all_security_events = []

        # 第一阶段：逐批处理安全判断
        for batch_idx, (batch, event_type) in enumerate(all_batches):
            _rating_status["current_batch"] = batch_idx + 1

            logger.info(f"处理第 {batch_idx + 1}/{total_batches} 批（安全判断），事件数: {len(batch)}")

            try:
                security_events = _process_batch_security(
                    db=db,
                    events=batch,
                    llm_service=llm_service,
                    keywords=keywords,
                    keyword_filter_enabled=keyword_filter_enabled,
                    event_type=event_type
                )

                if security_events:
                    all_security_events.extend([(e, event_type) for e in security_events])

                _rating_status["processed"] += len(batch)
                db.commit()

            except Exception as e:
                logger.error(f"第 {batch_idx + 1} 批安全判断失败: {e}")

            if batch_idx < total_batches - 1:
                time.sleep(request_interval)

        logger.info(f"安全判断完成: 安全事件 {len(all_security_events)} 条")

        if not all_security_events:
            return

        # 第二阶段：逐批处理评级
        security_batches = [
            all_security_events[i:i + batch_size]
            for i in range(0, len(all_security_events), batch_size)
        ]

        total_rating_batches = len(security_batches)
        _rating_status["total_batches"] = total_rating_batches
        _rating_status["current_batch"] = 0

        for batch_idx, batch_with_types in enumerate(security_batches):
            _rating_status["current_batch"] = batch_idx + 1

            batch = [e for e, _ in batch_with_types]

            logger.info(f"处理第 {batch_idx + 1}/{total_rating_batches} 批（评级），事件数: {len(batch)}")

            try:
                _process_batch_rating(
                    db=db,
                    events=batch,
                    llm_service=llm_service,
                    event_type=batch_with_types[0][1] if batch_with_types else "RSS"
                )
                db.commit()

            except Exception as e:
                logger.error(f"第 {batch_idx + 1} 批评级失败: {e}")

            if batch_idx < total_rating_batches - 1:
                time.sleep(request_interval)

        # 第三阶段：识别模型
        models_matched = _identify_models_for_events(db, all_security_events)
        db.commit()

        logger.info(f"处理完成: 评级 {len(all_security_events)} 条, 模型识别 {models_matched} 个关联")

    except Exception as e:
        logger.error(f"LLM自动评级任务失败: {e}", exc_info=True)
        _rating_status["error"] = str(e)
        db.rollback()
    finally:
        _rating_status["running"] = False
        db.close()


def manual_rate_events_async(
    event_ids: List[int],
    event_type: str,
    mode: str = "rate"
):
    """手动触发评级/分类（后台任务，支持流式更新）

    Args:
        event_ids: 事件ID列表
        event_type: 事件类型 (historical/rss)
        mode: 处理模式 (rate/classify/both/check_security)
    """
    global _rating_status

    if _rating_status["running"]:
        logger.warning("已有评级任务在运行中")
        return

    db = SessionLocal()

    try:
        Model = HistoricalEvent if event_type == "historical" else RSSEvent
        events = db.query(Model).filter(Model.id.in_(event_ids)).all()

        if not events:
            _rating_status["error"] = "未找到事件"
            return

        # 获取配置
        batch_size = get_configured_batch_size(db)
        request_interval = get_request_interval(db)

        # 获取分类列表
        categories = db.query(Category).filter(Category.is_active == True).all()
        category_list = [{"code": c.code, "name": c.name, "description": c.description} for c in categories]

        # 分批
        batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
        total_batches = len(batches)

        # 初始化状态
        _rating_status["running"] = True
        _rating_status["total"] = len(events)
        _rating_status["processed"] = 0
        _rating_status["current_batch"] = 0
        _rating_status["total_batches"] = total_batches
        _rating_status["error"] = None
        _rating_status["mode"] = mode
        _rating_status["event_type"] = event_type

        logger.info(
            f"开始手动评级: 共 {len(events)} 条事件, "
            f"{total_batches} 批, 批次大小 {batch_size}, 模式 {mode}"
        )

        llm_service = get_llm_service()
        processed = 0
        models_matched = 0

        # 逐批处理
        for batch_idx, batch in enumerate(batches):
            _rating_status["current_batch"] = batch_idx + 1

            logger.info(f"处理第 {batch_idx + 1}/{total_batches} 批，事件数: {len(batch)}")

            try:
                batch_processed, batch_models = _process_single_batch(
                    db=db,
                    events=batch,
                    llm_service=llm_service,
                    category_list=category_list,
                    event_type=event_type,
                    mode=mode
                )

                processed += batch_processed
                models_matched += batch_models
                _rating_status["processed"] = processed

                # 每批处理后立即提交数据库（流式更新）
                db.commit()

            except Exception as e:
                logger.error(f"第 {batch_idx + 1} 批处理失败: {e}")
                _rating_status["error"] = f"第 {batch_idx + 1} 批处理失败: {e}"

            # 等待间隔时间（最后一批不等待）
            if batch_idx < total_batches - 1:
                time.sleep(request_interval)

        logger.info(f"处理完成: 共处理 {processed} 条事件, 模型识别 {models_matched} 个关联")

    except Exception as e:
        logger.error(f"手动评级任务失败: {e}", exc_info=True)
        _rating_status["error"] = str(e)
        db.rollback()
    finally:
        _rating_status["running"] = False
        _rating_status["mode"] = None
        _rating_status["event_type"] = None
        db.close()


def _process_single_batch(
    db: Session,
    events: List[Any],
    llm_service,
    category_list: List[Dict],
    event_type: str,
    mode: str
) -> Tuple[int, int]:
    """处理单个批次

    Returns:
        (处理数量, 模型关联数量)
    """
    events_data = [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "raw_content": e.raw_content
        }
        for e in events
    ]

    processed = 0
    models_matched = 0

    if mode == "check_security":
        results = llm_service.batch_check_security(events_data)
        result_map = {r["id"]: r for r in results}

        for event in events:
            result = result_map.get(event.id, {"is_security_event": True})
            event.is_security_event = result.get("is_security_event", True)
            processed += 1

    elif mode == "rate":
        results = llm_service.batch_rate_events(events_data)
        result_map = {r["id"]: r for r in results}

        for event in events:
            result = result_map.get(event.id, {"severity": "medium", "cvss_score": 5.0, "cvss_vector": ""})
            severity = result.get("severity", "medium")
            cvss_score = result.get("cvss_score")
            cvss_vector = result.get("cvss_vector", "")

            valid_severities = ["none", "low", "medium", "high", "critical"]
            if severity not in valid_severities:
                severity = "medium"

            event.severity = severity
            event.severity_source = "llm"
            event.cvss_score = cvss_score
            event.cvss_vector = cvss_vector if cvss_vector else None
            event.is_processed = True
            processed += 1

            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "classify":
        results = llm_service.batch_classify_events(events_data, category_list)
        result_map = {r["id"]: r for r in results}

        for event in events:
            result = result_map.get(event.id, {"category_code": None})
            category_code = result.get("category_code")

            if category_code:
                category = db.query(Category).filter(Category.code == category_code).first()
                if category:
                    event.category_id = category.id
            else:
                default_category = db.query(Category).filter(Category.code == "other").first()
                if default_category:
                    event.category_id = default_category.id
            event.is_processed = True
            processed += 1

            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "both":
        results = llm_service.batch_rate_and_classify(events_data, category_list)
        result_map = {r["id"]: r for r in results}

        for event in events:
            result = result_map.get(event.id, {"severity": "medium", "cvss_score": 5.0, "cvss_vector": "", "category_code": None})
            severity = result.get("severity", "medium")
            cvss_score = result.get("cvss_score")
            cvss_vector = result.get("cvss_vector", "")
            category_code = result.get("category_code")

            valid_severities = ["none", "low", "medium", "high", "critical"]
            if severity not in valid_severities:
                severity = "medium"

            event.severity = severity
            event.severity_source = "llm"
            event.cvss_score = cvss_score
            event.cvss_vector = cvss_vector if cvss_vector else None

            if category_code:
                category = db.query(Category).filter(Category.code == category_code).first()
                if category:
                    event.category_id = category.id
            else:
                default_category = db.query(Category).filter(Category.code == "other").first()
                if default_category:
                    event.category_id = default_category.id

            event.is_processed = True
            processed += 1

            models_matched += _identify_and_create_event_models(db, event, event_type)

    return processed, models_matched


def _process_batch_security(
    db: Session,
    events: List[Any],
    llm_service,
    keywords: List[str],
    keyword_filter_enabled: bool,
    event_type: str
) -> List[Any]:
    """处理单批次的安全事件判断"""
    events_to_process = []

    # 关键词筛选
    for event in events:
        if keyword_filter_enabled and keywords:
            content = f"{event.title} {event.description or event.raw_content or ''}"
            if not matches_keywords(content, keywords):
                event.is_security_event = False
                event.is_processed = True
                continue
        events_to_process.append(event)

    if not events_to_process:
        return []

    # LLM判断
    events_data = [
        {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
        for e in events_to_process
    ]

    security_results = llm_service.batch_check_security(events_data)
    security_map = {r["id"]: r for r in security_results}

    security_events = []
    for event in events_to_process:
        result = security_map.get(event.id, {"is_security_event": True, "reason": "默认通过"})
        event.is_security_event = result.get("is_security_event", True)

        if event.is_security_event:
            security_events.append(event)
        else:
            event.is_processed = True

    return security_events


def _process_batch_rating(
    db: Session,
    events: List[Any],
    llm_service,
    event_type: str
):
    """处理单批次的评级"""
    if not events:
        return

    events_data = [
        {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
        for e in events
    ]

    rating_results = llm_service.batch_rate_events(events_data)
    rating_map = {r["id"]: r for r in rating_results}

    for event in events:
        result = rating_map.get(event.id, {"severity": "medium", "cvss_score": 5.0, "cvss_vector": ""})
        severity = result.get("severity", "medium")
        cvss_score = result.get("cvss_score")
        cvss_vector = result.get("cvss_vector", "")

        valid_severities = ["none", "low", "medium", "high", "critical"]
        if severity not in valid_severities:
            severity = "medium"

        event.severity = severity
        event.severity_source = "llm"
        event.cvss_score = cvss_score
        event.cvss_vector = cvss_vector if cvss_vector else None
        event.is_processed = True


def _identify_models_for_events(db: Session, events_with_types: List[Tuple[Any, str]]) -> int:
    """识别事件涉及的模型"""
    models_matched = 0

    for event, event_type in events_with_types:
        event_type_code = "rss" if event_type == "RSS" else "historical"
        content = f"{event.title} {event.description or event.raw_content or ''}"
        matched_model_ids = match_event_models(db, content)

        if matched_model_ids:
            for model_id in matched_model_ids:
                existing = db.query(EventModel).filter(
                    EventModel.event_type == event_type_code,
                    EventModel.event_id == event.id,
                    EventModel.model_id == model_id
                ).first()

                if not existing:
                    event_model = EventModel(
                        event_type=event_type_code,
                        event_id=event.id,
                        model_id=model_id
                    )
                    db.add(event_model)
                    models_matched += 1

    return models_matched


def _identify_and_create_event_models(db: Session, event, event_type: str) -> int:
    """识别事件涉及的模型并创建关联"""
    content = f"{event.title} {event.description or event.raw_content or ''}"
    matched_model_ids = match_event_models(db, content)
    created_count = 0

    if matched_model_ids:
        for model_id in matched_model_ids:
            existing = db.query(EventModel).filter(
                EventModel.event_type == event_type,
                EventModel.event_id == event.id,
                EventModel.model_id == model_id
            ).first()

            if not existing:
                event_model = EventModel(
                    event_type=event_type,
                    event_id=event.id,
                    model_id=model_id
                )
                db.add(event_model)
                created_count += 1

    return created_count


def manual_rate_events(
    db: Session,
    event_ids: List[int],
    event_type: str,
    mode: str = "rate"
) -> dict:
    """手动触发评级/分类（同步调用，用于少量数据）

    Args:
        db: 数据库会话
        event_ids: 事件ID列表
        event_type: 事件类型 (historical/rss)
        mode: 处理模式 (rate/classify/both/check_security)

    Returns:
        处理结果统计
    """
    Model = HistoricalEvent if event_type == "historical" else RSSEvent
    events = db.query(Model).filter(Model.id.in_(event_ids)).all()

    if not events:
        return {"total": 0, "processed": 0, "message": "未找到事件"}

    # 获取配置
    batch_size = get_configured_batch_size(db)

    # 获取分类列表
    categories = db.query(Category).filter(Category.is_active == True).all()
    category_list = [{"code": c.code, "name": c.name, "description": c.description} for c in categories]

    batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]

    llm_service = get_llm_service()
    processed = 0
    models_matched = 0

    for batch in batches:
        batch_processed, batch_models = _process_single_batch(
            db=db,
            events=batch,
            llm_service=llm_service,
            category_list=category_list,
            event_type=event_type,
            mode=mode
        )
        processed += batch_processed
        models_matched += batch_models

    db.commit()

    return {
        "total": len(events),
        "processed": processed,
        "mode": mode,
        "models_matched": models_matched
    }
