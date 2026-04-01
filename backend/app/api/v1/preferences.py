"""
用户偏好API路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model import Model
from app.models.category import Category
from app.models.user_preference import UserPreference
from app.schemas.preference import (
    PreferenceCreate, PreferenceUpdate, PreferenceResponse, PreferenceDetail
)
from app.schemas.response import ResponseModel
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=ResponseModel[List[PreferenceDetail]])
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户关注设置"""
    preferences = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).all()

    result = []
    for p in preferences:
        model_name = None
        category_name = None

        if p.model_id:
            model = db.query(Model).filter(Model.id == p.model_id).first()
            if model:
                model_name = model.name

        if p.category_id:
            category = db.query(Category).filter(Category.id == p.category_id).first()
            if category:
                category_name = category.name

        result.append(PreferenceDetail(
            id=p.id,
            user_id=p.user_id,
            model_id=p.model_id,
            category_id=p.category_id,
            is_enabled=p.is_enabled,
            created_at=p.created_at,
            model_name=model_name,
            category_name=category_name
        ))

    return ResponseModel(code=0, data=result)


@router.post("", response_model=ResponseModel[PreferenceResponse])
def add_preference(
    preference_data: PreferenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加关注设置"""
    # 检查是否已存在
    existing = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id,
        UserPreference.model_id == preference_data.model_id,
        UserPreference.category_id == preference_data.category_id
    ).first()

    if existing:
        # 更新状态
        existing.is_enabled = preference_data.is_enabled
        db.commit()
        db.refresh(existing)
        return ResponseModel(
            code=0,
            message="已更新关注设置",
            data=PreferenceResponse.model_validate(existing)
        )

    # 验证模型和分类是否存在
    if preference_data.model_id:
        model = db.query(Model).filter(Model.id == preference_data.model_id).first()
        if not model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 1005,
                    "message": "模型不存在",
                    "data": None
                }
            )

    if preference_data.category_id:
        category = db.query(Category).filter(Category.id == preference_data.category_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 1005,
                    "message": "分类不存在",
                    "data": None
                }
            )

    # 创建新偏好
    preference = UserPreference(
        user_id=current_user.id,
        model_id=preference_data.model_id,
        category_id=preference_data.category_id,
        is_enabled=preference_data.is_enabled
    )
    db.add(preference)
    db.commit()
    db.refresh(preference)

    return ResponseModel(
        code=0,
        message="添加成功",
        data=PreferenceResponse.model_validate(preference)
    )


@router.delete("/{preference_id}", response_model=ResponseModel)
def delete_preference(
    preference_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除关注设置"""
    preference = db.query(UserPreference).filter(
        UserPreference.id == preference_id,
        UserPreference.user_id == current_user.id
    ).first()

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1005,
                "message": "关注设置不存在",
                "data": None
            }
        )

    db.delete(preference)
    db.commit()

    return ResponseModel(code=0, message="删除成功")


@router.put("/{preference_id}", response_model=ResponseModel[PreferenceResponse])
def update_preference(
    preference_id: int,
    update_data: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新关注设置"""
    preference = db.query(UserPreference).filter(
        UserPreference.id == preference_id,
        UserPreference.user_id == current_user.id
    ).first()

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1005,
                "message": "关注设置不存在",
                "data": None
            }
        )

    if update_data.is_enabled is not None:
        preference.is_enabled = update_data.is_enabled

    db.commit()
    db.refresh(preference)

    return ResponseModel(
        code=0,
        message="更新成功",
        data=PreferenceResponse.model_validate(preference)
    )
