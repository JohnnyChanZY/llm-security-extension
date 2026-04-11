"""
WebSocket推送服务
"""
import logging
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.models.user import User

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 用户ID -> WebSocket连接的映射
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"用户 {user_id} WebSocket连接成功")

    def disconnect(self, user_id: int):
        """断开WebSocket连接"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"用户 {user_id} WebSocket连接断开")

    def send_personal_message(self, message: str, user_id: int) -> bool:
        """发送消息给指定用户（同步版本）"""
        if user_id in self.active_connections:
            try:
                import asyncio
                websocket = self.active_connections[user_id]
                # 在异步环境中使用
                asyncio.create_task(websocket.send_text(message))
                return True
            except Exception as e:
                logger.error(f"发送消息给用户 {user_id} 失败: {e}")
                return False
        return False

    async def send_personal_message_async(self, message: str, user_id: int):
        """发送消息给指定用户（异步版本）"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                logger.error(f"发送消息给用户 {user_id} 失败: {e}")
                self.disconnect(user_id)

    async def broadcast(self, message: str):
        """广播消息给所有连接"""
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"广播消息给用户 {user_id} 失败: {e}")
                self.disconnect(user_id)


# 创建全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket端点"""
    # 先接受连接（必须在接受后才能关闭）
    await websocket.accept()

    # 验证Token
    user_id = verify_token(token, token_type="access")
    if not user_id:
        logger.warning(f"WebSocket认证失败: token无效或已过期")
        await websocket.close(code=4001, reason="认证失败")
        return

    # 检查用户是否存在
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            await websocket.close(code=4002, reason="用户不存在或已被禁用")
            return
    finally:
        db.close()

    # 注册连接到管理器
    manager.active_connections[int(user_id)] = websocket
    logger.info(f"用户 {user_id} WebSocket连接成功")

    try:
        while True:
            # 等待客户端消息（用于心跳检测）
            data = await websocket.receive_text()

            # 处理心跳
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # 其他消息暂时忽略
                pass

    except WebSocketDisconnect:
        manager.disconnect(int(user_id))
    except Exception as e:
        logger.error(f"WebSocket异常: {e}")
        manager.disconnect(int(user_id))


# 注册WebSocket路由的函数
def register_websocket_route(app):
    """注册WebSocket路由到FastAPI应用"""
    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket, token: str = Query(...)):
        await websocket_endpoint(websocket, token)
