"""
LLM安全事件推送系统 - FastAPI入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import router as v1_router
from app.api.admin import router as admin_router
from app.api.websocket import register_websocket_route
from app.tasks.scheduler import scheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 抑制第三方库的详细日志，避免在命令行刷屏
# OpenAI/httpx/httpcore: 避免输出完整的 LLM 请求/响应内容
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# urllib3: 避免输出完整的 HTTP 请求/响应内容（requests 库底层）
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
# APScheduler: 避免输出任务调度的详细日志
logging.getLogger("apscheduler").setLevel(logging.WARNING)
# aiohttp: 避免 WebSocket 和异步 HTTP 请求的详细日志
logging.getLogger("aiohttp").setLevel(logging.WARNING)
# websockets: 避免 WebSocket 帧级别的详细日志
logging.getLogger("websockets").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在初始化应用...")

    # 初始化数据库
    try:
        init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化跳过（可能表已存在）: {e}")

    # 初始化种子数据
    try:
        from app.core.seed import seed_all
        seed_all()
    except Exception as e:
        logger.warning(f"种子数据初始化跳过: {e}")

    # 启动定时任务
    try:
        scheduler.start()
    except Exception as e:
        logger.warning(f"定时任务启动失败: {e}")

    logger.info("应用启动完成")

    yield

    # 关闭时执行
    logger.info("正在关闭应用...")
    scheduler.stop()
    logger.info("应用已关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    description="LLM安全事件推送系统API - 提供安全事件采集、分析和推送功能",
    version=settings.app_version,
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(v1_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/admin")

# 注册WebSocket路由
register_websocket_route(app)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
