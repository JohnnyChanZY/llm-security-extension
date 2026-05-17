"""
LLM自动处理任务
支持关键词筛选 -> 安全判断 -> 评级/分类的处理流程
LLM服务层统一处理批次并发和等待，任务层负责数据准备和状态更新

处理流程：
1. 关键词筛选（可选）
2. LLM安全事件判断（LLM服务自动分批并发）
3. LLM评级/分类（LLM服务自动分批并发）
"""
import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Dict, Any, Tuple

from app.core.database import SessionLocal
from app.models.system_config import SystemConfig
from app.models.rss_event import RSSEvent
from app.models.historical_event import HistoricalEvent
from app.models.category import Category
from app.models.event_model import EventModel
from app.services.llm_service import (
    get_llm_service, get_max_concurrent_batches, get_request_interval,
    get_batch_size, set_progress_callback, get_progress_callback
)
from app.services.model_matcher import match_event_models
from app.services.keyword_filter import matches_keywords

logger = logging.getLogger(__name__)

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


def _calculate_total_batches(n_events: int) -> int:
    """计算处理指定数量事件需要的总批次"""
    if n_events == 0:
        return 0
    batch_size = get_batch_size()
    return (n_events + batch_size - 1) // batch_size  # 向上取整


def _make_progress_callback():
    """创建进度回调函数，用于更新 _rating_status"""
    def callback(batch_completed: int, total_batches: int, events_processed: int):
        global _rating_status
        _rating_status["current_batch"] = batch_completed
        _rating_status["total_batches"] = total_batches
        _rating_status["processed"] = events_processed
        logger.debug(f"进度更新: 批次 {batch_completed}/{total_batches}, 已处理 {events_processed}")
    return callback


def get_config_bool(db: Session, key: str, default: bool = False) -> bool:
    """获取布尔类型配置"""
    config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if config and config.config_value:
        return config.config_value.lower() == "true"
    return default


def auto_process_events():
    """
    自动处理未处理的RSS事件（后台任务）

    处理流程：
    1. 关键词筛选（如果启用）
    2. LLM安全事件判断（LLM服务自动分批并发）
    3. LLM评级/分类（LLM服务自动分批并发，根据开关配置）

    注意：历史数据（NVD/AIID/AIVD）不参与此流程，它们默认为安全事件
    """
    global _rating_status

    if _rating_status["running"]:
        logger.warning("已有处理任务在运行中")
        return

    db = SessionLocal()

    try:
        # 获取开关配置
        rating_enabled = get_config_bool(db, "llm_rating_enabled")
        classify_enabled = get_config_bool(db, "llm_classify_enabled")

        # 如果两者都未开启，直接返回
        if not rating_enabled and not classify_enabled:
            logger.debug("LLM评级和分类均未启用")
            return

        # 获取并发配置（用于日志）
        max_concurrent = get_max_concurrent_batches()
        request_interval = get_request_interval()

        # 获取关键词筛选配置
        keyword_filter_enabled = get_config_bool(db, "keyword_filter_enabled")
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

        # 获取待处理的RSS事件（仅RSS需要判断）
        # 条件：is_processed=False 且 (is_security_event=NULL 或 is_security_event=True)
        rss_events = db.query(RSSEvent).filter(
            RSSEvent.is_processed == False,
            or_(
                RSSEvent.is_security_event == None,
                RSSEvent.is_security_event == True
            )
        ).all()

        if not rss_events:
            logger.debug("没有待处理的RSS事件")
            return

        total_events = len(rss_events)

        # 估算总批次（两阶段：筛选判断 + 评级分类）
        phase1_batches = _calculate_total_batches(total_events)
        # phase2 批次数在筛选完成后才能确定，先预估
        estimated_phase2_batches = _calculate_total_batches(total_events)
        estimated_total_batches = phase1_batches + estimated_phase2_batches

        # 初始化状态
        _rating_status["running"] = True
        _rating_status["total"] = total_events
        _rating_status["processed"] = 0
        _rating_status["current_batch"] = 0
        _rating_status["total_batches"] = estimated_total_batches
        _rating_status["error"] = None
        _rating_status["mode"] = "auto"

        # 确定处理模式
        if rating_enabled and classify_enabled:
            process_mode = "both"
        elif rating_enabled:
            process_mode = "rate"
        else:
            process_mode = "classify"

        logger.info(
            f"开始自动处理: 共 {total_events} 条RSS事件, "
            f"预计 {estimated_total_batches} 批次, 并发数 {max_concurrent}, 间隔 {request_interval}s, "
            f"模式: {process_mode}"
        )

        # 设置进度回调
        set_progress_callback(_make_progress_callback())

        llm_service = get_llm_service()

        # 获取分类列表（分类功能需要）
        categories = db.query(Category).filter(Category.is_active == True).all()
        category_list = [{"code": c.code, "name": c.name, "description": c.description} for c in categories]

        # 第一阶段：关键词筛选和安全判断
        logger.info(f"阶段1: 筛选+判断，事件数: {total_events}")

        all_security_events = _process_screening_phase(
            db=db,
            events=rss_events,
            llm_service=llm_service,
            keywords=keywords,
            keyword_filter_enabled=keyword_filter_enabled
        )

        _rating_status["processed"] = len(all_security_events)
        db.commit()

        logger.info(f"筛选判断完成: 安全事件 {len(all_security_events)} 条")

        if not all_security_events:
            return

        # 更新总批次数（第二阶段的实际批次数）
        phase2_batches = _calculate_total_batches(len(all_security_events))
        total_batches = phase1_batches + phase2_batches
        _rating_status["total_batches"] = total_batches

        # 第二阶段：评级/分类
        logger.info(f"阶段2: {process_mode}，事件数: {len(all_security_events)}")

        _process_rating_classify_phase(
            db=db,
            events=all_security_events,
            llm_service=llm_service,
            category_list=category_list,
            mode=process_mode
        )
        db.commit()

        # 第三阶段：识别模型
        models_matched = _identify_models_for_events(db, [(e, "rss") for e in all_security_events])
        db.commit()

        logger.info(f"处理完成: {process_mode} {len(all_security_events)} 条, 模型识别 {models_matched} 个关联")

    except Exception as e:
        logger.error(f"LLM自动处理任务失败: {e}", exc_info=True)
        _rating_status["error"] = str(e)
        db.rollback()
    finally:
        # 清除进度回调
        set_progress_callback(None)
        _rating_status["running"] = False
        db.close()


def _process_screening_phase(
    db: Session,
    events: List[Any],
    llm_service,
    keywords: List[str],
    keyword_filter_enabled: bool
) -> List[Any]:
    """
    处理关键词筛选和安全判断阶段

    Returns:
        确认为安全事件的事件列表
    """
    events_to_judge = []

    # 第一步：关键词筛选
    for event in events:
        # 如果已经判断为安全事件，直接加入待处理列表
        if event.is_security_event == True:
            events_to_judge.append(event)
            continue

        # 未判断的事件，进行关键词筛选
        if keyword_filter_enabled and keywords:
            content = f"{event.title} {event.description or event.raw_content or ''}"
            if not matches_keywords(content, keywords):
                event.is_security_event = False
                event.is_processed = True
                continue

        events_to_judge.append(event)

    if not events_to_judge:
        return []

    # 第二步：LLM安全判断（仅对未判断的事件）
    events_need_judge = [e for e in events_to_judge if e.is_security_event == None]

    if events_need_judge:
        events_data = [
            {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
            for e in events_need_judge
        ]

        # LLM服务会自动分批、并发、等待
        security_results = llm_service.batch_check_security(events_data)
        valid_results = [r for r in security_results if "id" in r]
        invalid_count = len(security_results) - len(valid_results)
        if invalid_count > 0:
            logger.warning(f"安全判断结果中 {invalid_count} 条缺少id字段，已忽略")
        security_map = {r["id"]: r for r in valid_results}

        for event in events_need_judge:
            result = security_map.get(event.id, {"is_security_event": True, "reason": "默认通过"})
            event.is_security_event = result.get("is_security_event", True)

    # 返回确认为安全事件的事件
    security_events = [e for e in events_to_judge if e.is_security_event == True]

    # 非安全事件标记为已处理
    for event in events_to_judge:
        if event.is_security_event == False:
            event.is_processed = True

    return security_events


def _process_rating_classify_phase(
    db: Session,
    events: List[Any],
    llm_service,
    category_list: List[Dict],
    mode: str
):
    """
    处理评级/分类阶段

    Args:
        mode: rate/classify/both
    """
    if not events:
        return

    events_data = [
        {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
        for e in events
    ]

    if mode == "both":
        # LLM服务会自动分批、并发、等待
        results = llm_service.batch_rate_and_classify(events_data, category_list)
        result_map = _safe_result_map(results, "评级分类")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True

    elif mode == "rate":
        results = llm_service.batch_rate_events(events_data)
        result_map = _safe_result_map(results, "评级")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            event.is_processed = True

    elif mode == "classify":
        results = llm_service.batch_classify_events(events_data, category_list)
        result_map = _safe_result_map(results, "分类")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True


def _apply_rating_result(event, result: Dict):
    """应用评级结果到事件"""
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


def _apply_classify_result(db: Session, event, result: Dict, category_list: List[Dict]):
    """应用分类结果到事件"""
    category_code = result.get("category_code")

    if category_code:
        category = db.query(Category).filter(Category.code == category_code).first()
        if category:
            event.category_id = category.id
            return

    # 默认分类
    default_category = db.query(Category).filter(Category.code == "other").first()
    if default_category:
        event.category_id = default_category.id


def _identify_models_for_events(db: Session, events_with_types: List[Tuple[Any, str]]) -> int:
    """识别事件涉及的模型（批量处理）"""
    models_matched = 0
    for event, event_type in events_with_types:
        event_type_code = "rss" if event_type == "rss" else "historical"
        models_matched += _identify_and_create_event_models(db, event, event_type_code)
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


def _safe_result_map(results: List[Dict], context: str = "") -> Dict[Any, Dict]:
    """从LLM结果列表构建 id->result 映射，过滤缺少id的条目"""
    valid = [r for r in results if "id" in r]
    invalid = len(results) - len(valid)
    if invalid > 0:
        logger.warning(f"{context}结果中 {invalid} 条缺少id字段，已忽略" if context else f"结果中 {invalid} 条缺少id字段，已忽略")
    return {r["id"]: r for r in valid}


# ============ 手动触发相关函数 ============

def manual_process_events_async(
    event_ids: List[int],
    event_type: str,
    mode: str = "rate",
    run_judge_first: bool = False
):
    """
    手动触发处理（后台任务）

    Args:
        event_ids: 事件ID列表
        event_type: 事件类型 (historical/rss)
        mode: 处理模式 (rate/classify/both/check_security)
        run_judge_first: 是否先执行安全判断再执行评级/分类
    """
    global _rating_status

    if _rating_status["running"]:
        logger.warning("已有处理任务在运行中")
        return

    db = SessionLocal()

    try:
        Model = HistoricalEvent if event_type == "historical" else RSSEvent
        events = db.query(Model).filter(Model.id.in_(event_ids)).all()

        if not events:
            _rating_status["error"] = "未找到事件"
            return

        # 获取并发配置（用于日志）
        max_concurrent = get_max_concurrent_batches()
        request_interval = get_request_interval()

        # 获取分类列表
        categories = db.query(Category).filter(Category.is_active == True).all()
        category_list = [{"code": c.code, "name": c.name, "description": c.description} for c in categories]

        llm_service = get_llm_service()

        # 如果需要先执行安全判断
        if run_judge_first and mode != "check_security":
            logger.info(f"先执行安全判断: {len(events)} 条事件")
            events_data = [
                {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
                for e in events
            ]
            security_results = llm_service.batch_check_security(events_data)
            valid_results = [r for r in security_results if "id" in r]
            invalid_count = len(security_results) - len(valid_results)
            if invalid_count > 0:
                logger.warning(f"安全判断结果中 {invalid_count} 条缺少id字段，已忽略")
            security_map = {r["id"]: r for r in valid_results}
            for event in events:
                result = security_map.get(event.id, {"is_security_event": True})
                event.is_security_event = result.get("is_security_event", True)
            db.commit()
            logger.info(f"安全判断完成")

        # check_security 模式：处理所有事件
        # rate/classify/both 模式：只处理 is_security_event=True 的事件
        if mode == "check_security":
            events_to_process = events
            skipped_count = 0
        else:
            events_to_process = [e for e in events if e.is_security_event == True]
            skipped_count = len(events) - len(events_to_process)
            if skipped_count > 0:
                logger.info(f"跳过 {skipped_count} 条非安全事件")

        if not events_to_process:
            logger.info(f"没有需要处理的事件（选中 {len(events)} 条，安全事件 0 条）")
            # 设置状态以便前端能正确识别任务完成
            _rating_status["running"] = True
            _rating_status["total"] = 0
            _rating_status["processed"] = 0
            _rating_status["current_batch"] = 0
            _rating_status["total_batches"] = 0
            _rating_status["error"] = None
            _rating_status["mode"] = mode
            _rating_status["event_type"] = event_type
            # 立即标记为完成
            _rating_status["running"] = False
            _rating_status["mode"] = None
            _rating_status["event_type"] = None
            return

        # 计算实际批次数量
        total_batches = _calculate_total_batches(len(events_to_process))

        # 初始化状态
        _rating_status["running"] = True
        _rating_status["total"] = len(events_to_process)
        _rating_status["processed"] = 0
        _rating_status["current_batch"] = 0
        _rating_status["total_batches"] = total_batches
        _rating_status["error"] = None
        _rating_status["mode"] = mode
        _rating_status["event_type"] = event_type

        logger.info(
            f"开始手动处理: 选中 {len(events)} 条, 安全事件 {len(events_to_process)} 条, "
            f"共 {total_batches} 批次, 并发数 {max_concurrent}, 间隔 {request_interval}s, 模式 {mode}"
        )

        # 设置进度回调
        set_progress_callback(_make_progress_callback())

        # 一次性处理所有事件（LLM服务会自动分批、并发、等待，并通过回调更新进度）
        events_data = [
            {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
            for e in events_to_process
        ]

        processed = 0
        models_matched = 0

        if mode == "check_security":
            results = llm_service.batch_check_security(events_data)
            result_map = _safe_result_map(results, "安全判断")

            for event in events_to_process:
                result = result_map.get(event.id, {"is_security_event": True})
                event.is_security_event = result.get("is_security_event", True)
                processed += 1

        elif mode == "rate":
            results = llm_service.batch_rate_events(events_data)
            result_map = _safe_result_map(results, "评级")

            for event in events_to_process:
                result = result_map.get(event.id, {})
                _apply_rating_result(event, result)
                event.is_processed = True
                processed += 1
                models_matched += _identify_and_create_event_models(db, event, event_type)

        elif mode == "classify":
            results = llm_service.batch_classify_events(events_data, category_list)
            result_map = _safe_result_map(results, "分类")

            for event in events_to_process:
                result = result_map.get(event.id, {})
                _apply_classify_result(db, event, result, category_list)
                event.is_processed = True
                processed += 1
                models_matched += _identify_and_create_event_models(db, event, event_type)

        elif mode == "both":
            results = llm_service.batch_rate_and_classify(events_data, category_list)
            result_map = _safe_result_map(results, "评级分类")

            for event in events_to_process:
                result = result_map.get(event.id, {})
                _apply_rating_result(event, result)
                _apply_classify_result(db, event, result, category_list)
                event.is_processed = True
                processed += 1
                models_matched += _identify_and_create_event_models(db, event, event_type)

        _rating_status["processed"] = processed
        db.commit()

        logger.info(f"处理完成: 共处理 {processed} 条事件, 模型识别 {models_matched} 个关联")

    except Exception as e:
        logger.error(f"手动处理任务失败: {e}", exc_info=True)
        _rating_status["error"] = str(e)
        db.rollback()
    finally:
        # 清除进度回调
        set_progress_callback(None)
        _rating_status["running"] = False
        _rating_status["mode"] = None
        _rating_status["event_type"] = None
        db.close()


def _process_single_batch_manual(
    db: Session,
    events: List[Any],
    llm_service,
    category_list: List[Dict],
    event_type: str,
    mode: str
) -> Tuple[int, int]:
    """
    处理单个批次（手动模式）- 保留用于兼容

    注意：此函数已被 manual_process_events_async 内联逻辑替代，保留用于向后兼容

    Returns:
        (处理数量, 模型关联数量)
    """
    if not events:
        return 0, 0

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
        result_map = _safe_result_map(results, "安全判断")

        for event in events:
            result = result_map.get(event.id, {"is_security_event": True})
            event.is_security_event = result.get("is_security_event", True)
            processed += 1

    elif mode == "rate":
        results = llm_service.batch_rate_events(events_data)
        result_map = _safe_result_map(results, "评级")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "classify":
        results = llm_service.batch_classify_events(events_data, category_list)
        result_map = _safe_result_map(results, "分类")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "both":
        results = llm_service.batch_rate_and_classify(events_data, category_list)
        result_map = _safe_result_map(results, "评级分类")

        for event in events:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    return processed, models_matched


def manual_process_events(
    db: Session,
    event_ids: List[int],
    event_type: str,
    mode: str = "rate"
) -> dict:
    """
    手动触发处理（同步调用，用于少量数据）

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

    # 获取分类列表
    categories = db.query(Category).filter(Category.is_active == True).all()
    category_list = [{"code": c.code, "name": c.name, "description": c.description} for c in categories]

    # check_security 模式：处理所有事件
    # rate/classify/both 模式：只处理 is_security_event=True 的事件
    if mode == "check_security":
        events_to_process = events
    else:
        events_to_process = [e for e in events if e.is_security_event == True]

    if not events_to_process:
        return {
            "total": len(events),
            "processed": 0,
            "mode": mode,
            "models_matched": 0,
            "message": f"选中 {len(events)} 条，无安全事件需要处理"
        }

    llm_service = get_llm_service()

    # 一次性处理所有事件（LLM服务会自动分批、并发、等待）
    events_data = [
        {"id": e.id, "title": e.title, "description": e.description, "raw_content": e.raw_content}
        for e in events_to_process
    ]

    processed = 0
    models_matched = 0

    if mode == "check_security":
        results = llm_service.batch_check_security(events_data)
        result_map = _safe_result_map(results, "安全判断")

        for event in events_to_process:
            result = result_map.get(event.id, {"is_security_event": True})
            event.is_security_event = result.get("is_security_event", True)
            processed += 1

    elif mode == "rate":
        results = llm_service.batch_rate_events(events_data)
        result_map = _safe_result_map(results, "评级")

        for event in events_to_process:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "classify":
        results = llm_service.batch_classify_events(events_data, category_list)
        result_map = _safe_result_map(results, "分类")

        for event in events_to_process:
            result = result_map.get(event.id, {})
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    elif mode == "both":
        results = llm_service.batch_rate_and_classify(events_data, category_list)
        result_map = _safe_result_map(results, "评级分类")

        for event in events_to_process:
            result = result_map.get(event.id, {})
            _apply_rating_result(event, result)
            _apply_classify_result(db, event, result, category_list)
            event.is_processed = True
            processed += 1
            models_matched += _identify_and_create_event_models(db, event, event_type)

    db.commit()

    return {
        "total": len(events),
        "processed": processed,
        "mode": mode,
        "models_matched": models_matched
    }


# ============ 兼容旧函数名（保持向后兼容） ============

def auto_rate_events():
    """兼容旧函数名"""
    auto_process_events()


def manual_rate_events_async(event_ids: List[int], event_type: str, mode: str = "rate", run_judge_first: bool = False):
    """兼容旧函数名"""
    manual_process_events_async(event_ids, event_type, mode, run_judge_first)


def manual_rate_events(db: Session, event_ids: List[int], event_type: str, mode: str = "rate") -> dict:
    """兼容旧函数名"""
    return manual_process_events(db, event_ids, event_type, mode)
