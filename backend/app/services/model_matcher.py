"""
模型匹配服务
基于关键词匹配识别事件涉及的LLM模型
"""
import logging
import re
from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session

from app.models.model import Model

logger = logging.getLogger(__name__)


class ModelMatcher:
    """模型匹配器

    基于关键词匹配识别事件内容中涉及的LLM模型。
    支持精确匹配和模糊匹配（如 "GPT-4" 匹配 "GPT-4-Turbo"）。
    """

    # 模型名称到关键词的映射（预定义的关键词扩展）
    MODEL_KEYWORDS: Dict[str, List[str]] = {
        # 国际闭源模型
        "GPT-4": ["gpt-4", "gpt4", "gpt 4", "gpt4o", "gpt-4o", "gpt-4-turbo", "gpt4-turbo"],
        "GPT-3.5": ["gpt-3.5", "gpt3.5", "gpt 3.5", "gpt-3.5-turbo", "gpt35-turbo", "chatgpt"],
        "Claude": ["claude", "claude-2", "claude-3", "claude3", "claude-2.1", "claude-3-opus", "claude-3-sonnet"],
        "Gemini": ["gemini", "gemini-pro", "gemini-ultra", "bard"],
        "Copilot": ["copilot", "github copilot", "microsoft copilot", "bing chat"],

        # 国产模型
        "通义千问": ["通义千问", "qwen", "tongyi", "tongyi qianwen", "通义", "qwen-"],
        "文心一言": ["文心一言", "文心", "ernie", "ernie-bot", "ernie bot"],
        "GLM": ["glm", "chatglm", "chatglm-", "智谱", "zhipu"],
        "Kimi": ["kimi", "moonshot", "月之暗面"],
        "DeepSeek": ["deepseek", "深度求索"],
        "讯飞星火": ["讯飞星火", "星火", "讯飞", "spark", "iflytek"],
        "百川": ["百川", "baichuan", "baichuan-"],
        "混元": ["混元", "hunyuan", "腾讯混元"],

        # 开源模型
        "LLaMA": ["llama", "llama-2", "llama2", "llama-3", "llama3", "llama-", "meta llama"],
        "Mistral": ["mistral", "mistral-", "mixtral"],
        "Qwen": ["qwen", "qwen-", "qwen2", "qwen-2"],  # 与通义千问重复，但Qwen也作为独立开源模型
        "Yi": ["yi-", "零一万物", "01ai"],
        "Phi": ["phi-", "phi-1", "phi-2", "phi-3", "microsoft phi"],
        "Falcon": ["falcon", "falcon-", "tii falcon"],
    }

    def __init__(self, db: Session):
        """初始化模型匹配器

        Args:
            db: 数据库会话
        """
        self.db = db
        self._model_cache: Optional[Dict[int, Dict]] = None

    def _load_models(self) -> Dict[int, Dict]:
        """从数据库加载所有活跃模型

        Returns:
            模型ID到模型信息的映射
        """
        if self._model_cache is not None:
            return self._model_cache

        models = self.db.query(Model).filter(Model.is_active == True).all()
        self._model_cache = {}

        for model in models:
            # 获取预定义的关键词，如果没有则使用模型名称
            keywords = self.MODEL_KEYWORDS.get(model.name, [])

            # 添加模型名称本身作为关键词
            model_name_lower = model.name.lower()
            if model_name_lower not in keywords:
                keywords = [model_name_lower] + keywords

            self._model_cache[model.id] = {
                "id": model.id,
                "name": model.name,
                "vendor": model.vendor,
                "keywords": keywords
            }

        return self._model_cache

    def match_models(self, content: str) -> List[int]:
        """匹配内容涉及的模型

        Args:
            content: 要匹配的内容（标题、描述等）

        Returns:
            匹配的模型ID列表
        """
        if not content:
            return []

        models = self._load_models()
        content_lower = content.lower()
        matched_ids: Set[int] = set()

        for model_id, model_info in models.items():
            for keyword in model_info["keywords"]:
                if keyword.lower() in content_lower:
                    matched_ids.add(model_id)
                    logger.debug(
                        f"模型匹配成功: {model_info['name']} "
                        f"(关键词: {keyword})"
                    )
                    break  # 一个模型匹配一次即可

        return list(matched_ids)

    def match_models_with_details(self, content: str) -> List[Dict]:
        """匹配内容涉及的模型（带详细信息）

        Args:
            content: 要匹配的内容

        Returns:
            匹配的模型详细信息列表
        """
        matched_ids = self.match_models(content)
        models = self._load_models()

        return [models[model_id] for model_id in matched_ids if model_id in models]

    def refresh_cache(self):
        """刷新模型缓存"""
        self._model_cache = None
        self._load_models()


def match_event_models(db: Session, content: str) -> List[int]:
    """便捷函数：匹配事件内容涉及的模型

    Args:
        db: 数据库会话
        content: 事件内容

    Returns:
        匹配的模型ID列表
    """
    matcher = ModelMatcher(db)
    return matcher.match_models(content)
