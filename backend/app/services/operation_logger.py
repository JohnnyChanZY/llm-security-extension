"""
操作日志记录工具
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog


def log_operation(
    db: Session,
    user_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """记录一条操作日志"""
    log = OperationLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
