# API V1 Module
from fastapi import APIRouter

from . import auth, events, categories, models, preferences

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(events.router, prefix="/events", tags=["事件"])
router.include_router(categories.router, prefix="/categories", tags=["分类"])
router.include_router(models.router, prefix="/models", tags=["模型"])
router.include_router(preferences.router, prefix="/preferences", tags=["偏好"])
