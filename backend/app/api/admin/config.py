"""
系统配置API路由（管理员）
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.system_config import SystemConfig
from app.schemas.config import ConfigResponse, ConfigUpdate, LLMConfigResponse
from app.schemas.response import ResponseModel
from app.api.deps import get_current_admin

router = APIRouter()


@router.get("", response_model=ResponseModel[List[ConfigResponse]])
def get_configs(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取所有配置"""
    configs = db.query(SystemConfig).all()
    return ResponseModel(
        code=0,
        data=[ConfigResponse.model_validate(c) for c in configs]
    )


@router.put("/{config_key}", response_model=ResponseModel[ConfigResponse])
def update_config(
    config_key: str,
    update_data: ConfigUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新配置项"""
    config = db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()

    if not config:
        # 创建新配置
        config = SystemConfig(
            config_key=config_key,
            config_value=update_data.config_value
        )
        db.add(config)
    else:
        config.config_value = update_data.config_value

    db.commit()
    db.refresh(config)

    return ResponseModel(
        code=0,
        message="更新成功",
        data=ConfigResponse.model_validate(config)
    )


@router.get("/llm", response_model=ResponseModel[LLMConfigResponse])
def get_llm_config(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取LLM配置"""
    configs = {c.config_key: c.config_value for c in db.query(SystemConfig).all()}

    return ResponseModel(
        code=0,
        data=LLMConfigResponse(
            llm_classify_enabled=configs.get("llm_classify_enabled", "false").lower() == "true",
            llm_rating_enabled=configs.get("llm_rating_enabled", "false").lower() == "true",
            llm_batch_size=int(configs.get("llm_batch_size", "30")),
            llm_max_concurrent_batches=int(configs.get("llm_max_concurrent_batches", "3")),
            llm_request_interval=float(configs.get("llm_request_interval", "2")),
            max_batch_size=100,
            max_concurrent_batches=10,
            max_request_interval=60.0
        )
    )
