"""
操作日志API（管理员）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.operation_log import OperationLog
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin

router = APIRouter()


@router.get("", response_model=ResponseModel)
def get_operation_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取操作日志列表（分页）"""
    query = db.query(OperationLog).order_by(OperationLog.created_at.desc())
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]

    return ResponseModel(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })
