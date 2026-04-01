# Admin API Module
from fastapi import APIRouter

from . import config, rss_sources, models, rating, sync, events

router = APIRouter()

router.include_router(config.router, prefix="/configs", tags=["系统配置"])
router.include_router(rss_sources.router, prefix="/rss-sources", tags=["RSS数据源"])
router.include_router(models.router, prefix="/models", tags=["模型管理"])
router.include_router(rating.router, prefix="/rating", tags=["LLM评级"])
router.include_router(sync.router, prefix="/sync", tags=["数据同步"])
router.include_router(events.router, prefix="/events", tags=["事件管理"])
