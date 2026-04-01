"""
认证API路由
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_token
)
from app.core.config import settings
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserLogin, UserUpdate, PasswordUpdate,
    UserResponse, TokenResponse, LoginResponse
)
from app.schemas.response import ResponseModel
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=ResponseModel[UserResponse])
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """用户注册"""
    # 检查邮箱是否已存在
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 2001,
                "message": "该邮箱已被注册",
                "data": None
            }
        )

    # 创建用户
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        nickname=user_data.nickname
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return ResponseModel(
        code=0,
        message="注册成功",
        data=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=ResponseModel[LoginResponse])
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """用户登录"""
    # 查找用户
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 2002,
                "message": "邮箱或密码错误",
                "data": None
            }
        )

    # 验证密码
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 2002,
                "message": "邮箱或密码错误",
                "data": None
            }
        )

    # 检查用户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": 1004,
                "message": "用户已被禁用",
                "data": None
            }
        )

    # 生成Token
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return ResponseModel(
        code=0,
        message="登录成功",
        data=LoginResponse(
            user=UserResponse.model_validate(user),
            token=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_minutes * 60
            )
        )
    )


@router.post("/logout", response_model=ResponseModel)
def logout(
    current_user: User = Depends(get_current_user)
):
    """用户登出"""
    # 在无状态JWT模式下，登出只需客户端删除Token
    # 如果需要服务端失效，可以使用Token黑名单
    return ResponseModel(
        code=0,
        message="登出成功"
    )


@router.post("/refresh", response_model=ResponseModel[TokenResponse])
def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """刷新Token"""
    # 验证刷新Token
    user_id = verify_token(refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 1003,
                "message": "刷新Token无效或已过期",
                "data": None
            }
        )

    # 检查用户是否存在且活跃
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 1002,
                "message": "用户不存在或已被禁用",
                "data": None
            }
        )

    # 生成新Token
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return ResponseModel(
        code=0,
        message="刷新成功",
        data=TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60
        )
    )


@router.get("/profile", response_model=ResponseModel[UserResponse])
def get_profile(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return ResponseModel(
        code=0,
        data=UserResponse.model_validate(current_user)
    )


@router.put("/profile", response_model=ResponseModel[UserResponse])
def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    if update_data.nickname is not None:
        current_user.nickname = update_data.nickname

    db.commit()
    db.refresh(current_user)

    return ResponseModel(
        code=0,
        message="更新成功",
        data=UserResponse.model_validate(current_user)
    )


@router.put("/password", response_model=ResponseModel)
def update_password(
    password_data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 2002,
                "message": "旧密码错误",
                "data": None
            }
        )

    # 更新密码
    current_user.password_hash = hash_password(password_data.new_password)
    db.commit()

    return ResponseModel(
        code=0,
        message="密码修改成功"
    )
