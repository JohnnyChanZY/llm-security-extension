"""
模型API路由
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model import Model
from app.schemas.model import ModelResponse
from app.schemas.response import ResponseModel
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=ResponseModel[List[ModelResponse]])
def get_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型列表（仅启用的）"""
    models = db.query(Model).filter(Model.is_active == True).order_by(Model.sort_order).all()
    return ResponseModel(
        code=0,
        data=[ModelResponse.model_validate(m) for m in models]
    )
