"""
LLM处理管理API路由（管理员）
支持手动触发安全判断、评级、分类操作
支持后台任务和流式更新（前端轮询状态接口）
"""
from typing import List
import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.models.system_config import SystemConfig
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin
from app.tasks.llm_rating import (
    manual_process_events,
    manual_process_events_async,
    auto_process_events,
    get_rating_status
)
from app.services.llm_service import MAX_BATCH_SIZE_LIMIT

router = APIRouter()
logger = logging.getLogger(__name__)

# 请求间隔上限（秒）
MAX_REQUEST_INTERVAL_LIMIT = 60
# 最大并发批次上限
MAX_CONCURRENT_BATCHES_LIMIT = 10


class ManualProcessRequest(BaseModel):
    """手动处理请求"""
    event_ids: List[int]
    event_type: str  # historical 或 rss
    mode: str = "rate"  # rate/classify/both/check_security


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    event_ids: List[int]
    event_type: str  # historical 或 rss
    operations: List[str]  # ["judge", "rate", "classify"] 的组合


@router.post("/trigger", response_model=ResponseModel)
def trigger_auto_process(
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发自动处理任务（后台运行）"""
    status = get_rating_status()

    if status["running"]:
        return ResponseModel(
            code=0,
            message="处理任务正在运行中",
            data=status
        )

    background_tasks.add_task(auto_process_events)

    return ResponseModel(
        code=0,
        message="处理任务已启动",
        data=status
    )


@router.post("/process", response_model=ResponseModel)
def trigger_process(
    request: ManualProcessRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """
    手动触发处理（后台运行，支持流式更新）

    前端调用此接口后，轮询 /status 接口获取进度

    - event_ids: 事件ID列表
    - event_type: 事件类型 (historical/rss)
    - mode: 处理模式
        - check_security: 仅判断是否安全事件
        - rate: 仅评级
        - classify: 仅分类
        - both: 评级+分类（一次LLM调用完成）
    """
    if not request.event_ids:
        return ResponseModel(code=1, message="请选择要处理的事件")

    if request.event_type not in ["historical", "rss"]:
        return ResponseModel(code=1, message="事件类型必须是 historical 或 rss")

    if request.mode not in ["rate", "classify", "both", "check_security"]:
        return ResponseModel(code=1, message="模式必须是 rate/classify/both/check_security")

    status = get_rating_status()

    if status["running"]:
        return ResponseModel(
            code=2,
            message="已有处理任务在运行中，请等待完成",
            data=status
        )

    # 在后台执行
    background_tasks.add_task(
        manual_process_events_async,
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode=request.mode
    )

    return ResponseModel(
        code=0,
        message=f"处理任务已启动，共 {len(request.event_ids)} 条事件",
        data={
            "total": len(request.event_ids),
            "mode": request.mode
        }
    )


@router.post("/check-security", response_model=ResponseModel)
def check_security(
    request: ManualProcessRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """判断是否安全事件（后台运行）"""
    request.mode = "check_security"
    return trigger_process(request, background_tasks, current_admin)


@router.post("/rate", response_model=ResponseModel)
def trigger_rate(
    request: ManualProcessRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发评级（后台运行）"""
    request.mode = "rate"
    return trigger_process(request, background_tasks, current_admin)


@router.post("/classify", response_model=ResponseModel)
def trigger_classify(
    request: ManualProcessRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发分类（后台运行）"""
    request.mode = "classify"
    return trigger_process(request, background_tasks, current_admin)


@router.post("/rate-and-classify", response_model=ResponseModel)
def trigger_rate_and_classify(
    request: ManualProcessRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发评级+分类（后台运行，一次LLM调用完成）"""
    request.mode = "both"
    return trigger_process(request, background_tasks, current_admin)


@router.post("/batch-operations", response_model=ResponseModel)
def execute_batch_operations(
    request: BatchOperationRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """
    批量执行多个操作（后台运行）

    支持的操作类型：
    - judge: 判断是否为LLM安全事件
    - rate: 评级（安全等级）
    - classify: 分类（事件类别）

    操作执行顺序：judge -> rate/classify
    """
    if not request.event_ids:
        return ResponseModel(code=1, message="请选择要处理的事件")

    if request.event_type not in ["historical", "rss"]:
        return ResponseModel(code=1, message="事件类型必须是 historical 或 rss")

    valid_operations = {"judge", "rate", "classify"}
    for op in request.operations:
        if op not in valid_operations:
            return ResponseModel(code=1, message=f"无效的操作类型: {op}，有效值为: {valid_operations}")

    if not request.operations:
        return ResponseModel(code=1, message="请至少选择一个操作")

    status = get_rating_status()

    if status["running"]:
        return ResponseModel(
            code=2,
            message="已有处理任务在运行中，请等待完成",
            data=status
        )

    # 确定模式
    has_judge = "judge" in request.operations
    has_rate = "rate" in request.operations
    has_classify = "classify" in request.operations

    # 根据操作组合确定处理模式
    if has_rate and has_classify:
        mode = "both"
    elif has_rate:
        mode = "rate"
    elif has_classify:
        mode = "classify"
    else:
        mode = "check_security"

    background_tasks.add_task(
        manual_process_events_async,
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode=mode
    )

    return ResponseModel(
        code=0,
        message=f"任务已启动，共 {len(request.event_ids)} 条事件，操作: {', '.join(request.operations)}",
        data={
            "total": len(request.event_ids),
            "operations": request.operations,
            "mode": mode
        }
    )


@router.get("/status", response_model=ResponseModel)
def get_status(
    current_admin: User = Depends(get_current_admin)
):
    """获取处理任务状态（前端轮询此接口实现流式更新）"""
    status = get_rating_status()
    return ResponseModel(
        code=0,
        data=status
    )


@router.get("/config", response_model=ResponseModel)
def get_process_config(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取处理配置"""
    config_keys = [
        "llm_rating_enabled",
        "llm_classify_enabled",
        "llm_batch_size",
        "llm_max_concurrent_batches",
        "llm_request_interval",
        "keyword_filter_enabled"
    ]
    configs = {}
    for key in config_keys:
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        configs[key] = config.config_value if config else None

    return ResponseModel(data=configs)


@router.put("/config", response_model=ResponseModel)
def update_process_config(
    key: str,
    value: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新处理配置"""
    valid_keys = [
        "llm_rating_enabled",
        "llm_classify_enabled",
        "llm_batch_size",
        "llm_max_concurrent_batches",
        "llm_request_interval",
        "keyword_filter_enabled"
    ]
    if key not in valid_keys:
        return ResponseModel(code=1, message=f"无效的配置项，必须是: {valid_keys}")

    # 验证批次大小
    if key == "llm_batch_size":
        try:
            batch_value = int(value)
            if batch_value < 1 or batch_value > MAX_BATCH_SIZE_LIMIT:
                return ResponseModel(code=1, message=f"批次大小必须在 1-{MAX_BATCH_SIZE_LIMIT} 之间")
        except ValueError:
            return ResponseModel(code=1, message="批次大小必须是整数")

    # 验证最大并发批次
    if key == "llm_max_concurrent_batches":
        try:
            concurrent_value = int(value)
            if concurrent_value < 1 or concurrent_value > MAX_CONCURRENT_BATCHES_LIMIT:
                return ResponseModel(code=1, message=f"最大并发批次必须在 1-{MAX_CONCURRENT_BATCHES_LIMIT} 之间")
        except ValueError:
            return ResponseModel(code=1, message="最大并发批次必须是整数")

    # 验证请求间隔
    if key == "llm_request_interval":
        try:
            interval_value = float(value)
            if interval_value < 0 or interval_value > MAX_REQUEST_INTERVAL_LIMIT:
                return ResponseModel(code=1, message=f"请求间隔必须在 0-{MAX_REQUEST_INTERVAL_LIMIT} 之间")
        except ValueError:
            return ResponseModel(code=1, message="请求间隔必须是数字")

    config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if config:
        config.config_value = value
    else:
        config = SystemConfig(config_key=key, config_value=value)
        db.add(config)

    db.commit()
    return ResponseModel(message=f"配置已更新: {key}={value}")


@router.post("/stop", response_model=ResponseModel)
def stop_process(
    current_admin: User = Depends(get_current_admin)
):
    """停止当前处理任务（标记停止，当前批次会完成）"""
    from app.tasks.llm_rating import _rating_status

    if not _rating_status["running"]:
        return ResponseModel(message="当前没有运行中的处理任务")

    # 设置停止标志
    _rating_status["error"] = "用户手动停止"
    _rating_status["running"] = False

    return ResponseModel(message="已停止处理任务")
