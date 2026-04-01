"""
LLM 调用日志记录器
记录 LLM API 调用的完整信息到文件，用于调试和审计
"""
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import lru_cache

from app.core.config import settings


@lru_cache()
def get_llm_logger():
    """获取 LLM 日志记录器单例"""
    return LLMLogger()


class LLMLogger:
    """LLM 调用日志记录器"""

    def __init__(self):
        self.enabled = settings.llm_log_enabled
        self.log_dir = Path(settings.llm_log_dir)
        self._setup_log_dir()

    def _setup_log_dir(self):
        """创建日志目录"""
        if self.enabled:
            # 相对于 backend 目录
            backend_dir = Path(__file__).parent.parent.parent
            full_log_dir = backend_dir / self.log_dir
            full_log_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir = full_log_dir

    def _get_log_file_path(self) -> Path:
        """获取当天的日志文件路径"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"llm_{date_str}.log"

    def log_call(
        self,
        operation: str,
        model: str,
        messages: List[Dict[str, str]],
        response: Optional[str] = None,
        event_ids: Optional[List[int]] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """
        记录 LLM 调用

        Args:
            operation: 操作类型 (security_check / rate / classify / rate_and_classify)
            model: 使用的模型名称
            messages: 发送给 LLM 的消息列表
            response: LLM 返回的原始响应
            event_ids: 处理的事件 ID 列表
            error: 错误信息（如果调用失败）
            duration_ms: 调用耗时（毫秒）
        """
        if not self.enabled:
            return

        end_time = datetime.now()
        sent_at = None
        if duration_ms:
            sent_at = (end_time - timedelta(milliseconds=duration_ms)).isoformat()

        log_entry = {
            "timestamp": end_time.isoformat(),
            "sent_at": sent_at,
            "operation": operation,
            "model": model,
            "event_count": len(event_ids) if event_ids else 0,
            "event_ids": event_ids,
            "duration_ms": round(duration_ms, 2) if duration_ms else None,
            "status": "error" if error else "success",
            "error": error,
            "request": {
                "messages": messages
            },
            "response": response
        }

        log_file = self._get_log_file_path()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, indent=2))
                f.write("\n---\n")
        except Exception as e:
            logging.getLogger(__name__).error(f"写入 LLM 日志失败: {e}")

    def log_security_check(
        self,
        model: str,
        events: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        response: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """记录安全检查调用"""
        event_ids = [e.get("id") for e in events]
        self.log_call(
            operation="security_check",
            model=model,
            messages=messages,
            response=response,
            event_ids=event_ids,
            error=error,
            duration_ms=duration_ms
        )

    def log_rating(
        self,
        model: str,
        events: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        response: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """记录评级调用"""
        event_ids = [e.get("id") for e in events]
        self.log_call(
            operation="rating",
            model=model,
            messages=messages,
            response=response,
            event_ids=event_ids,
            error=error,
            duration_ms=duration_ms
        )

    def log_classification(
        self,
        model: str,
        events: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        response: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """记录分类调用"""
        event_ids = [e.get("id") for e in events]
        self.log_call(
            operation="classification",
            model=model,
            messages=messages,
            response=response,
            event_ids=event_ids,
            error=error,
            duration_ms=duration_ms
        )

    def log_rate_and_classify(
        self,
        model: str,
        events: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        response: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """记录评级+分类调用"""
        event_ids = [e.get("id") for e in events]
        self.log_call(
            operation="rate_and_classify",
            model=model,
            messages=messages,
            response=response,
            event_ids=event_ids,
            error=error,
            duration_ms=duration_ms
        )
