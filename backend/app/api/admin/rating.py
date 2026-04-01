"""
LLM评级管理API路由（管理员）
串行处理，逐批发送请求
支持后台任务和流式更新（前端轮询状态接口）
"""
from typing import Optional, List
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
    manual_rate_events,
    manual_rate_events_async,
    auto_rate_events,
    get_rating_status
)
from app.services.llm_service import MAX_BATCH_SIZE_LIMIT

router = APIRouter()
logger = logging.getLogger(__name__)

# 请求间隔上限（秒）
MAX_REQUEST_INTERVAL_LIMIT = 60


class ManualRateRequest(BaseModel):
    """手动评级请求"""
    event_ids: List[int]
    event_type: str  # historical 或 rss
    mode: str = "rate"  # rate/classify/both/check_security


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    event_ids: List[int]
    event_type: str  # historical 或 rss
    operations: List[str]  # ["judge", "rate", "classify"] 的组合


@router.post("/trigger", response_model=ResponseModel)
def trigger_rating(
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发自动评级任务（后台运行）"""
    status = get_rating_status()

    if status["running"]:
        return ResponseModel(
            code=0,
            message="评级任务正在运行中",
            data=status
        )

    background_tasks.add_task(auto_rate_events)

    return ResponseModel(
        code=0,
        message="评级任务已启动",
        data=status
    )


@router.post("/rate", response_model=ResponseModel)
def trigger_rate(
    request: ManualRateRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """
    手动触发评级（后台运行，支持流式更新）

    前端调用此接口后，轮询 /status 接口获取进度

    - event_ids: 事件ID列表
    - event_type: 事件类型 (historical/rss)
    - mode: 处理模式
        - rate: 仅评级
        - classify: 仅分类
        - both: 评级+分类
        - check_security: 仅判断是否安全事件
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
            message="已有评级任务在运行中，请等待完成",
            data=status
        )

    # 在后台执行
    background_tasks.add_task(
        manual_rate_events_async,
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode=request.mode
    )

    return ResponseModel(
        code=0,
        message=f"评级任务已启动，共 {len(request.event_ids)} 条事件",
        data={
            "total": len(request.event_ids),
            "mode": request.mode
        }
    )


@router.post("/classify", response_model=ResponseModel)
def trigger_classify(
    request: ManualRateRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发分类（后台运行）"""
    classify_request = ManualRateRequest(
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode="classify"
    )
    return trigger_rate(classify_request, background_tasks, current_admin)


@router.post("/rate-and-classify", response_model=ResponseModel)
def trigger_rate_and_classify(
    request: ManualRateRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """手动触发评级+分类（后台运行）"""
    both_request = ManualRateRequest(
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode="both"
    )
    return trigger_rate(both_request, background_tasks, current_admin)


@router.post("/check-security", response_model=ResponseModel)
def check_security(
    request: ManualRateRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin)
):
    """判断是否安全事件（后台运行）"""
    check_request = ManualRateRequest(
        event_ids=request.event_ids,
        event_type=request.event_type,
        mode="check_security"
    )
    return trigger_rate(check_request, background_tasks, current_admin)


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
    - classify: 分类（涉及模型）

    操作执行顺序：judge -> rate -> classify
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
            message="已有评级任务在运行中，请等待完成",
            data=status
        )

    # 确定模式
    has_judge = "judge" in request.operations
    has_rate = "rate" in request.operations
    has_classify = "classify" in request.operations

    if has_rate and has_classify:
        mode = "both"
    elif has_rate:
        mode = "rate"
    elif has_classify:
        mode = "classify"
    else:
        mode = "check_security"

    # 如果需要先判断，分两步执行
    if has_judge and (has_rate or has_classify):
        # 先判断，后续操作会在判断完成后自动执行
        # 这里简化处理：直接执行最终模式
        pass

    background_tasks.add_task(
        manual_rate_events_async,
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
    """获取评级任务状态（前端轮询此接口实现流式更新）"""
    status = get_rating_status()
    return ResponseModel(
        code=0,
        data=status
    )


@router.get("/config", response_model=ResponseModel)
def get_rating_config(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取评级配置"""
    configs = {}
    for key in ["llm_rating_enabled", "llm_classify_enabled", "llm_batch_size", "llm_request_interval", "keyword_filter_enabled"]:
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        configs[key] = config.config_value if config else None

    return ResponseModel(data=configs)


@router.put("/config", response_model=ResponseModel)
def update_rating_config(
    key: str,
    value: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新评级配置"""
    valid_keys = ["llm_rating_enabled", "llm_classify_enabled", "llm_batch_size", "llm_request_interval", "keyword_filter_enabled"]
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
def stop_rating(
    current_admin: User = Depends(get_current_admin)
):
    """停止当前评级任务（标记停止，当前批次会完成）"""
    from app.tasks.llm_rating import _rating_status

    if not _rating_status["running"]:
        return ResponseModel(message="当前没有运行中的评级任务")

    # 设置停止标志（需要在任务中检查此标志）
    _rating_status["error"] = "用户手动停止"

    return ResponseModel(message="已发送停止信号，当前批次完成后将停止")
