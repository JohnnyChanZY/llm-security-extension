"""
模型管理API路由（管理员）
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model import Model
from app.schemas.model import ModelCreate, ModelUpdate, ModelResponse
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin

router = APIRouter()


@router.get("", response_model=ResponseModel[List[ModelResponse]])
def get_all_models(
    include_disabled: bool = False,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取模型列表（含禁用的）"""
    query = db.query(Model)
    if not include_disabled:
        query = query.filter(Model.is_active == True)
    models = query.order_by(Model.sort_order).all()
    return ResponseModel(
        code=0,
        data=[ModelResponse.model_validate(m) for m in models]
    )


@router.post("", response_model=ResponseModel[ModelResponse])
def create_model(
    model_data: ModelCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """新增模型"""
    model = Model(
        name=model_data.name,
        vendor=model_data.vendor,
        description=model_data.description,
        is_active=model_data.is_active,
        sort_order=model_data.sort_order
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    return ResponseModel(
        code=0,
        message="创建成功",
        data=ModelResponse.model_validate(model)
    )


@router.put("/{model_id}", response_model=ResponseModel[ModelResponse])
def update_model(
    model_id: int,
    update_data: ModelUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新模型"""
    model = db.query(Model).filter(Model.id == model_id).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1005,
                "message": "模型不存在",
                "data": None
            }
        )

    if update_data.name is not None:
        model.name = update_data.name
    if update_data.vendor is not None:
        model.vendor = update_data.vendor
    if update_data.description is not None:
        model.description = update_data.description
    if update_data.is_active is not None:
        model.is_active = update_data.is_active
    if update_data.sort_order is not None:
        model.sort_order = update_data.sort_order

    db.commit()
    db.refresh(model)

    return ResponseModel(
        code=0,
        message="更新成功",
        data=ModelResponse.model_validate(model)
    )


@router.delete("/{model_id}", response_model=ResponseModel)
def delete_model(
    model_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除模型"""
    model = db.query(Model).filter(Model.id == model_id).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1005,
                "message": "模型不存在",
                "data": None
            }
        )

    db.delete(model)
    db.commit()

    return ResponseModel(code=0, message="删除成功")
