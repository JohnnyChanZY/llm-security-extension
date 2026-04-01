"""
分类API路由
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryResponse
from app.schemas.response import ResponseModel
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=ResponseModel[List[CategoryResponse]])
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分类列表"""
    categories = db.query(Category).filter(Category.is_active == True).order_by(Category.id).all()
    return ResponseModel(
        code=0,
        data=[CategoryResponse.model_validate(c) for c in categories]
    )
