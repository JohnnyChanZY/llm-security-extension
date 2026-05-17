"""
LLM 服务 - 统一的评级与分类逻辑
支持批量处理以节省 token
使用 CVSS 4.0 标准进行安全等级评定

性能优化说明：
  1. 固定 max_tokens：使用 10k 固定限制，简化配置
  2. 分组并发：事件超出 batch_size 时自动拆分为多批，按 max_concurrent_batches 分组并发
     - 例如：9批次、并发数3 → 分3组：[1,2,3并发] → 等待 → [4,5,6并发] → 等待 → [7,8,9并发]
  3. 异步客户端：新增 AsyncOpenAI，适配 FastAPI 等异步框架，不再阻塞事件循环
  4. 提取公共调用逻辑：_call_llm_sync / _call_llm_async 消除大量重复代码
  5. 动态配置：并发数和等待间隔从数据库读取，支持管理员界面实时调整
"""
import asyncio
import logging
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Tuple

from openai import OpenAI, AsyncOpenAI

from app.core.config import settings
from app.core.llm_logger import get_llm_logger

logger = logging.getLogger(__name__)


def safe_parse_json(content: str) -> Tuple[Optional[List], str]:
    """
    安全解析LLM返回的JSON内容

    处理以下情况：
    1. 内容前后有空白字符
    2. 内容前后有markdown代码块标记
    3. JSON后面有额外的文本
    4. 返回的是单个对象而非数组

    Returns:
        (解析结果或None, 错误信息或空字符串)
    """
    if not content:
        return None, "内容为空"

    # 去除前后空白
    content = content.strip()

    # 去除可能的markdown代码块标记
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    # 尝试直接解析
    try:
        result = json.loads(content)
        return result, ""
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON数组部分
    # 找到第一个 [ 和最后一个 ]
    start_idx = content.find('[')
    end_idx = content.rfind(']')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            json_str = content[start_idx:end_idx + 1]
            result = json.loads(json_str)
            return result, ""
        except json.JSONDecodeError:
            pass

    # 尝试提取JSON对象部分（可能是单个对象或包装对象）
    start_idx = content.find('{')
    end_idx = content.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            json_str = content[start_idx:end_idx + 1]
            result = json.loads(json_str)
            return result, ""
        except json.JSONDecodeError:
            pass

    return None, f"无法解析JSON: {content[:100]}..."

# CVSS 4.0 固定指标值
CVSS4_FIXED_AV = "N"  # Attack Vector: Network (LLM攻击通常通过网络)
CVSS4_FIXED_AT = "N"  # Attack Requirements: None
CVSS4_FIXED_SC = "N"  # Subsequent System Confidentiality: None
CVSS4_FIXED_SI = "N"  # Subsequent System Integrity: None
CVSS4_FIXED_SA = "N"  # Subsequent System Availability: None


def cvss_score_to_severity(score: float) -> str:
    """将CVSS分数映射到严重等级

    Args:
        score: CVSS分数 (0.0-10.0)

    Returns:
        严重等级字符串: critical/high/medium/low/none
    """
    if score == 0.0:
        return "none"
    elif score <= 3.9:
        return "low"
    elif score <= 6.9:
        return "medium"
    elif score <= 8.9:
        return "high"
    else:
        return "critical"


def calculate_cvss_score(
    ac: str,
    pr: str,
    ui: str,
    vc: str,
    vi: str,
    va: str
) -> Tuple[float, str]:
    """计算CVSS 4.0基础分数

    Args:
        ac: Attack Complexity (L/H)
        pr: Privileges Required (N/L/H)
        ui: User Interaction (N/P/A)
        vc: Vulnerable System Confidentiality Impact (N/L/H)
        vi: Vulnerable System Integrity Impact (N/L/H)
        va: Vulnerable System Availability Impact (N/L/H)

    Returns:
        (分数, CVSS向量字符串)
    """
    try:
        from cvss import CVSS4

        # 构建CVSS向量字符串
        vector = (
            f"CVSS:4.0/"
            f"AV:{CVSS4_FIXED_AV}/"
            f"AC:{ac}/"
            f"AT:{CVSS4_FIXED_AT}/"
            f"PR:{pr}/"
            f"UI:{ui}/"
            f"VC:{vc}/"
            f"VI:{vi}/"
            f"VA:{va}/"
            f"SC:{CVSS4_FIXED_SC}/"
            f"SI:{CVSS4_FIXED_SI}/"
            f"SA:{CVSS4_FIXED_SA}"
        )

        c = CVSS4(vector)
        score = c.base_score
        return score, vector

    except Exception as e:
        logger.error(f"CVSS分数计算失败: {e}")
        return 5.0, ""  # 返回中等分数作为默认值

# ──────────────────────────────────────────────
# 并发配置
# ──────────────────────────────────────────────
# 批量处理配置（已移至 config.py，通过 settings.llm_batch_size 配置）
# 这里保留常量作为安全上限，防止配置过大
MAX_BATCH_SIZE_LIMIT = 100  # 硬性上限，防止单次请求过大
MAX_CONCURRENT_BATCHES_LIMIT = 10  # 最大并发批次上限
MAX_REQUEST_INTERVAL_LIMIT = 60.0  # 最大请求间隔上限（秒）

# glm-5 等推理模型会使用大量 token 进行思考(reasoning)，
# 需要设置足够大的 max_tokens 确保有足够空间输出实际内容
# glm-5 上下文最大 200k，输出最大 128k
# 固定使用 10k token 限制
DEFAULT_MAX_TOKENS = 10000


def get_batch_size() -> int:
    """从数据库获取批次大小配置"""
    from app.core.database import SessionLocal
    from app.models.system_config import SystemConfig

    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "llm_batch_size"
        ).first()
        if config and config.config_value:
            return min(int(config.config_value), MAX_BATCH_SIZE_LIMIT)
    except Exception as e:
        logger.debug(f"获取批次大小配置失败，使用默认值: {e}")
    finally:
        db.close()
    return settings.llm_batch_size  # 默认值


def get_max_concurrent_batches() -> int:
    """从数据库获取最大并发批次配置"""
    from app.core.database import SessionLocal
    from app.models.system_config import SystemConfig

    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "llm_max_concurrent_batches"
        ).first()
        if config and config.config_value:
            return min(int(config.config_value), MAX_CONCURRENT_BATCHES_LIMIT)
    except Exception as e:
        logger.debug(f"获取并发配置失败，使用默认值: {e}")
    finally:
        db.close()
    return 3  # 默认值


def get_request_interval() -> float:
    """从数据库获取请求间隔配置"""
    from app.core.database import SessionLocal
    from app.models.system_config import SystemConfig

    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "llm_request_interval"
        ).first()
        if config and config.config_value:
            return min(float(config.config_value), MAX_REQUEST_INTERVAL_LIMIT)
    except Exception as e:
        logger.debug(f"获取请求间隔配置失败，使用默认值: {e}")
    finally:
        db.close()
    return 2.0  # 默认值


class LLMService:
    """LLM 服务类 - 封装评级、分类、安全检查功能"""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.async_client: Optional[AsyncOpenAI] = None
        self.model = settings.llm_model
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 客户端（同步和异步）"""
        if settings.llm_api_key:
            kwargs = dict(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
            self.client = OpenAI(**kwargs)
            self.async_client = AsyncOpenAI(**kwargs)
        else:
            logger.warning("未配置 LLM API 密钥")

    def is_available(self) -> bool:
        """检查 LLM 服务是否可用"""
        return self.client is not None

    # ──────────────────────────────────────────
    # 内部公共调用方法
    # ──────────────────────────────────────────

    def _call_llm_sync(self, messages: List[Dict], max_tokens: int) -> Tuple[str, float]:
        """同步调用 LLM，返回 (content, duration_ms)"""
        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            duration_ms = (time.time() - start) * 1000

            # 检查空响应
            if not content or not content.strip():
                logger.warning(
                    f"LLM 返回空内容，max_tokens={max_tokens}, "
                    f"duration={duration_ms:.0f}ms, model={self.model}"
                )
                # 对于推理模型，可能是 max_tokens 不够
                # 尝试不带 json_object 格式限制重新请求
                logger.info("尝试不带 response_format 限制重新请求...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    max_tokens=max_tokens * 2,  # 给更多空间
                )
                content = response.choices[0].message.content
                duration_ms = (time.time() - start) * 1000

            return content or "", duration_ms
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    async def _call_llm_async(self, messages: List[Dict], max_tokens: int) -> Tuple[str, float]:
        """异步调用 LLM（适用于 FastAPI 等 async 框架），返回 (content, duration_ms)"""
        start = time.time()
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            duration_ms = (time.time() - start) * 1000

            # 检查空响应
            if not content or not content.strip():
                logger.warning(
                    f"[async] LLM 返回空内容，max_tokens={max_tokens}, "
                    f"duration={duration_ms:.0f}ms, model={self.model}"
                )
                logger.info("[async] 尝试不带 response_format 限制重新请求...")
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    max_tokens=max_tokens * 2,
                )
                content = response.choices[0].message.content
                duration_ms = (time.time() - start) * 1000

            return content or "", duration_ms
        except Exception as e:
            logger.error(f"[async] LLM 调用失败: {e}")
            raise

    @staticmethod
    def _chunk_events(events: List[Dict]) -> List[List[Dict]]:
        """将事件列表按 batch_size 切分"""
        size = get_batch_size()
        return [events[i:i + size] for i in range(0, len(events), size)]

    def _run_concurrent(self, fn, chunks: List[List[Dict]],
                        max_concurrent: int = None,
                        request_interval: float = None) -> List[Dict]:
        """
        分组并发执行多个批次，组间有等待时间

        Args:
            fn: 处理单批次的函数
            chunks: 批次列表
            max_concurrent: 最大并发数（None则从数据库读取）
            request_interval: 组间等待时间秒数（None则从数据库读取）

        Returns:
            合并后的结果列表
        """
        n_chunks = len(chunks)
        if n_chunks == 1:
            logger.debug(f"[并发] 单批次处理，事件数: {len(chunks[0])}，跳过并发")
            result = fn(chunks[0])
            # 回调通知进度
            if _progress_callback:
                try:
                    _progress_callback(batch_completed=1, total_batches=1, events_processed=len(result))
                except Exception as e:
                    logger.warning(f"进度回调失败: {e}")
            return result

        # 获取配置
        if max_concurrent is None:
            max_concurrent = get_max_concurrent_batches()
        if request_interval is None:
            request_interval = get_request_interval()

        results: List[Dict] = []
        start_time = time.time()
        batches_completed = 0

        # 分组：每 max_concurrent 个批次为一组
        groups = [chunks[i:i + max_concurrent] for i in range(0, n_chunks, max_concurrent)]
        logger.info(f"[并发] 共 {n_chunks} 批次，分 {len(groups)} 组，每组最多 {max_concurrent} 并发")

        for group_idx, group in enumerate(groups):
            group_start = time.time()

            # 组内并发执行
            with ThreadPoolExecutor(max_workers=len(group)) as executor:
                futures = [executor.submit(fn, chunk) for chunk in group]
                for future in as_completed(futures):
                    try:
                        batch_result = future.result()
                        results.extend(batch_result)
                        batches_completed += 1
                        # 每完成一个批次就回调通知进度
                        if _progress_callback:
                            try:
                                _progress_callback(
                                    batch_completed=batches_completed,
                                    total_batches=n_chunks,
                                    events_processed=len(results)
                                )
                            except Exception as e:
                                logger.warning(f"进度回调失败: {e}")
                    except Exception as e:
                        logger.error(f"并发批次处理失败: {e}")
                        batches_completed += 1  # 即使失败也计数

            group_duration = time.time() - group_start
            logger.info(f"[并发] 第 {group_idx + 1}/{len(groups)} 组完成，耗时 {group_duration:.1f}s")

            # 组间等待（最后一组不等待）
            if group_idx < len(groups) - 1 and request_interval > 0:
                logger.debug(f"[并发] 等待 {request_interval}s 后处理下一组")
                time.sleep(request_interval)

        total_duration = time.time() - start_time
        logger.info(f"[并发] 全部完成，总结果数: {len(results)}，总耗时: {total_duration:.1f}s")
        return results

    async def _run_concurrent_async(self, coro_fn, chunks: List[List[Dict]],
                                    max_concurrent: int = None,
                                    request_interval: float = None) -> List[Dict]:
        """
        异步分组并发执行多个批次，组间有等待时间

        Args:
            coro_fn: 处理单批次的异步函数
            chunks: 批次列表
            max_concurrent: 最大并发数（None则从数据库读取）
            request_interval: 组间等待时间秒数（None则从数据库读取）

        Returns:
            合并后的结果列表
        """
        n_chunks = len(chunks)
        if n_chunks == 1:
            return await coro_fn(chunks[0])

        # 获取配置
        if max_concurrent is None:
            max_concurrent = get_max_concurrent_batches()
        if request_interval is None:
            request_interval = get_request_interval()

        results: List[Dict] = []
        start_time = time.time()

        # 分组：每 max_concurrent 个批次为一组
        groups = [chunks[i:i + max_concurrent] for i in range(0, n_chunks, max_concurrent)]
        logger.info(f"[并发] 共 {n_chunks} 批次，分 {len(groups)} 组，每组最多 {max_concurrent} 并发")

        for group_idx, group in enumerate(groups):
            group_start = time.time()

            # 组内并发执行
            tasks = [coro_fn(chunk) for chunk in group]
            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in group_results:
                if isinstance(r, Exception):
                    logger.error(f"异步批次处理失败: {r}")
                else:
                    results.extend(r)

            group_duration = time.time() - group_start
            logger.info(f"[并发] 第 {group_idx + 1}/{len(groups)} 组完成，耗时 {group_duration:.1f}s")

            # 组间等待（最后一组不等待）
            if group_idx < len(groups) - 1 and request_interval > 0:
                logger.debug(f"[并发] 等待 {request_interval}s 后处理下一组")
                await asyncio.sleep(request_interval)

        total_duration = time.time() - start_time
        logger.info(f"[并发] 全部完成，总结果数: {len(results)}，总耗时: {total_duration:.1f}s")
        return results

    @staticmethod
    def _normalize_result_ids(result: List[Dict]) -> None:
        """原地修复 LLM 可能返回 '事件9' 形式的 ID"""
        for item in result:
            if "id" in item and isinstance(item["id"], str):
                m = re.search(r'\d+', item["id"])
                if m:
                    item["id"] = int(m.group())

    def _unwrap_result(self, content: str, default_fn) -> Optional[List[Dict]]:
        """解析并解包 LLM 返回的 JSON，失败时返回 None"""
        parsed, err = safe_parse_json(content)
        if parsed is None:
            logger.error(f"JSON解析失败: {err}, 原始内容: {content[:200]}")
            return None
        if isinstance(parsed, dict) and "results" in parsed:
            parsed = parsed["results"]
        # LLM 可能对单个事件返回对象而非数组，自动包装
        if isinstance(parsed, dict):
            logger.debug(f"LLM返回单个对象，自动包装为数组: {content[:100]}")
            parsed = [parsed]
        if not isinstance(parsed, list):
            logger.error(f"返回格式异常: {content[:200]}")
            return None
        return parsed

    @staticmethod
    def _build_events_text(events: List[Dict], max_desc: int = 300) -> str:
        """构建事件文本（英文格式）"""
        return "\n\n".join(
            f"[Event {e['id']}]\nTitle: {e['title']}\nDescription: {(e.get('description') or e.get('raw_content') or '')[:max_desc]}"
            for e in events
        )

    # ──────────────────────────────────────────
    # 批量安全检查（同步）
    # ──────────────────────────────────────────

    def batch_check_security(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量判断是否为 AI/LLM 安全事件"""
        if not self.is_available():
            return self._default_security_result(events, "LLM服务不可用")
        if not events:
            return []
        chunks = self._chunk_events(events)
        return self._run_concurrent(self._check_security_chunk, chunks)

    def _check_security_chunk(self, events: List[Dict]) -> List[Dict]:
        system_prompt = """你是AI/LLM安全事件识别专家。判断每个事件是否属于AI/LLM安全相关事件。

✅ 属于安全事件（is_security_event=true）：
- CVE漏洞披露、安全补丁公告
- 提示词注入(Prompt Injection)、越狱(Jailbreak)攻击
- 对抗样本攻击、模型逃逸
- 训练数据泄露、隐私信息泄露
- 模型后门、供应链攻击
- 安全机制绕过、权限提升
- 数据投毒、模型篡改
- 拒绝服务(DoS)攻击相关

❌ 不属于安全事件（is_security_event=false）：
- 产品发布、功能更新、版本迭代
- 使用教程、操作指南
- 行业新闻、市场分析
- 商业推广、合作公告
- 模型能力评测、性能对比（非安全维度）

以JSON数组输出，每项必须包含：
- id: 整数（事件ID）
- is_security_event: 布尔值
- reason: 字符串（≤20字，简要说明）

示例：[{"id":1,"is_security_event":true,"reason":"CVE漏洞披露"},{"id":2,"is_security_event":false,"reason":"产品功能更新"}]"""

        events_text = self._build_events_text(events, max_desc=300)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请判断以下{len(events)}个事件是否属于AI/LLM安全事件：\n\n{events_text}"},
        ]
        llm_logger = get_llm_logger()

        try:
            content, duration_ms = self._call_llm_sync(messages, DEFAULT_MAX_TOKENS)
            llm_logger.log_security_check(model=self.model, events=events,
                                          messages=messages, response=content,
                                          duration_ms=duration_ms)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_security_result(events, "JSON解析失败")
            self._normalize_result_ids(result)
            return result

        except Exception as e:
            logger.error(f"LLM 安全事件判断失败: {e}")
            llm_logger.log_security_check(model=self.model, events=events,
                                          messages=messages, error=str(e),
                                          duration_ms=0)
            return self._default_security_result(events, "判断失败")

    def _default_security_result(self, events: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
        """生成默认的安全检查结果

        当LLM调用失败时，默认标记为非安全事件(is_security_event=False)，
        避免将非安全事件误判为安全事件推送给用户。
        """
        return [{"id": e["id"], "is_security_event": False, "reason": reason} for e in events]

    # ──────────────────────────────────────────
    # 批量评级（同步）
    # ──────────────────────────────────────────

    def batch_rate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量评级事件，使用 CVSS 4.0 标准"""
        if not self.is_available():
            return self._default_rating_result(events)
        if not events:
            return []
        chunks = self._chunk_events(events)
        return self._run_concurrent(self._rate_events_chunk, chunks)

    def _rate_events_chunk(self, events: List[Dict]) -> List[Dict]:
        system_prompt = """你是AI安全风险评估专家，使用CVSS 4.0评估LLM安全事件严重程度。

## CVSS 4.0 指标（请根据事件描述逐项评估）
- AC(攻击复杂度): L=无需绕过安全机制即可利用 / H=需要绕过特定安全机制
- PR(所需权限): N=无需任何权限 / L=需要普通用户权限 / H=需要管理员权限
- UI(用户交互): N=无需用户交互 / P=需要用户被动点击等 / A=需要用户主动参与
- VC(机密性影响): N=无泄露 / L=部分敏感数据泄露 / H=全部/关键数据泄露
- VI(完整性影响): N=无篡改 / L=部分数据被篡改 / H=完全控制数据
- VA(可用性影响): N=无中断 / L=性能下降或部分不可用 / H=完全不可用

## 评估原则
- 根据漏洞实际可利用性和影响范围评估，不要一律给高或一律给低
- 考虑攻击是否需要特殊条件（如需要登录、需要用户交互等）
- 数据泄露类事件重点关注VC，篡改类重点关注VI，DoS类重点关注VA

必须以JSON数组输出，每项包含 id、ac、pr、ui、vc、vi、va。
示例：[{"id":1,"ac":"L","pr":"N","ui":"N","vc":"H","vi":"H","va":"N"}]"""

        events_text = self._build_events_text(events, max_desc=800)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请评估以下{len(events)}个LLM安全事件：\n\n{events_text}"},
        ]
        llm_logger = get_llm_logger()

        try:
            content, duration_ms = self._call_llm_sync(messages, DEFAULT_MAX_TOKENS)
            llm_logger.log_rating(model=self.model, events=events,
                                  messages=messages, response=content,
                                  duration_ms=duration_ms)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_rating_result(events)
            self._normalize_result_ids(result)
            return self._process_cvss_items(result, include_category=False)

        except Exception as e:
            logger.error(f"LLM 评级失败: {e}")
            llm_logger.log_rating(model=self.model, events=events,
                                  messages=messages, error=str(e), duration_ms=0)
            return self._default_rating_result(events)

    def _validate_cvss_metric(self, value: Any, valid: List[str], default: str) -> str:
        """验证 CVSS 指标值"""
        if isinstance(value, str) and value.upper() in valid:
            return value.upper()
        return default

    def _process_cvss_items(self, items: List[Dict], include_category: bool = False) -> List[Dict]:
        """将 LLM 返回的 CVSS 指标列表转化为含分数/severity 的结果"""
        out = []
        for item in items:
            ac = self._validate_cvss_metric(item.get("ac", "L"), ["L", "H"], "L")
            pr = self._validate_cvss_metric(item.get("pr", "N"), ["N", "L", "H"], "N")
            ui = self._validate_cvss_metric(item.get("ui", "N"), ["N", "P", "A"], "N")
            vc = self._validate_cvss_metric(item.get("vc", "N"), ["N", "L", "H"], "N")
            vi = self._validate_cvss_metric(item.get("vi", "N"), ["N", "L", "H"], "N")
            va = self._validate_cvss_metric(item.get("va", "N"), ["N", "L", "H"], "N")

            score, vector = calculate_cvss_score(ac, pr, ui, vc, vi, va)
            entry: Dict[str, Any] = {
                "id": item.get("id"),
                "severity": cvss_score_to_severity(score),
                "cvss_score": score,
                "cvss_vector": vector,
            }
            if include_category:
                entry["category_code"] = item.get("category_code")
            out.append(entry)
        return out

    def _default_rating_result(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成默认的评级结果"""
        return [{
            "id": e["id"],
            "severity": "medium",
            "cvss_score": 5.0,
            "cvss_vector": ""
        } for e in events]

    # ──────────────────────────────────────────
    # 批量分类（同步）
    # ──────────────────────────────────────────

    def batch_classify_events(self, events: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量分类事件"""
        if not self.is_available():
            return self._default_classify_result(events)
        if not events:
            return []
        chunks = self._chunk_events(events)
        return self._run_concurrent(
            lambda chunk: self._classify_events_chunk(chunk, categories), chunks
        )

    def _classify_events_chunk(self, events: List[Dict], categories: List[Dict]) -> List[Dict]:
        cats_text = "\n".join(
            f"- {c['code']}: {c['name']}" + (f" ({c['description']})" if c.get("description") else "")
            for c in categories
        )
        system_prompt = f"""你是AI安全事件分类专家。将事件分类到最合适的类别。

## 可用分类
{cats_text}

## 分类原则
- 根据事件的核心安全问题分类，而非表面描述
- 如果事件涉及多个类别，选择最主要的安全风险类别
- 确实无法匹配任何分类时，category_code设为null（系统会自动归入"其他"）

必须以JSON数组输出，每项包含 id、category_code。
示例：[{{"id":1,"category_code":"LLM01"}},{{"id":2,"category_code":"LLM06"}}]"""

        events_text = self._build_events_text(events, max_desc=300)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请对以下{len(events)}个AI/LLM安全事件进行分类：\n\n{events_text}"},
        ]
        llm_logger = get_llm_logger()

        try:
            content, duration_ms = self._call_llm_sync(messages, DEFAULT_MAX_TOKENS)
            llm_logger.log_classification(model=self.model, events=events,
                                          messages=messages, response=content,
                                          duration_ms=duration_ms)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_classify_result(events)
            self._normalize_result_ids(result)
            return result

        except Exception as e:
            logger.error(f"LLM 分类失败: {e}")
            llm_logger.log_classification(model=self.model, events=events,
                                          messages=messages, error=str(e), duration_ms=0)
            return self._default_classify_result(events)

    def _default_classify_result(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成默认的分类结果"""
        return [{"id": e["id"], "category_code": None} for e in events]

    # ──────────────────────────────────────────
    # 批量评级 + 分类（同步）
    # ──────────────────────────────────────────

    def batch_rate_and_classify(self, events: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量评级并分类事件（单次 LLM 调用完成两项任务）"""
        if not self.is_available():
            return self._default_rate_classify_result(events)
        if not events:
            return []
        chunks = self._chunk_events(events)
        return self._run_concurrent(
            lambda chunk: self._rate_and_classify_chunk(chunk, categories), chunks
        )

    def _rate_and_classify_chunk(self, events: List[Dict], categories: List[Dict]) -> List[Dict]:
        cats_text = "\n".join(f"- {c['code']}: {c['name']}" for c in categories)
        system_prompt = f"""你是AI安全风险评估专家，使用CVSS 4.0评估LLM安全事件并分类。

## CVSS 4.0 指标（请根据事件描述逐项评估）
- AC(攻击复杂度): L=无需绕过安全机制即可利用 / H=需要绕过特定安全机制
- PR(所需权限): N=无需任何权限 / L=需要普通用户权限 / H=需要管理员权限
- UI(用户交互): N=无需用户交互 / P=需要用户被动点击等 / A=需要用户主动参与
- VC(机密性影响): N=无泄露 / L=部分敏感数据泄露 / H=全部/关键数据泄露
- VI(完整性影响): N=无篡改 / L=部分数据被篡改 / H=完全控制数据
- VA(可用性影响): N=无中断 / L=性能下降或部分不可用 / H=完全不可用

## 评估原则
- 根据漏洞实际可利用性和影响范围评估，不要一律给高或一律给低
- 考虑攻击是否需要特殊条件（如需要登录、需要用户交互等）

## 可用分类
{cats_text}

## 分类原则
- 根据事件的核心安全问题分类，而非表面描述
- 确实无法匹配时，category_code设为null

必须以JSON数组输出，每项包含 id、ac、pr、ui、vc、vi、va、category_code。
示例：[{{"id":1,"ac":"L","pr":"N","ui":"N","vc":"H","vi":"H","va":"N","category_code":"LLM01"}}]"""

        events_text = self._build_events_text(events, max_desc=800)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请评估并分类以下{len(events)}个LLM安全事件：\n\n{events_text}"},
        ]
        llm_logger = get_llm_logger()

        try:
            content, duration_ms = self._call_llm_sync(messages, DEFAULT_MAX_TOKENS)
            llm_logger.log_rate_and_classify(model=self.model, events=events,
                                             messages=messages, response=content,
                                             duration_ms=duration_ms)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_rate_classify_result(events)
            self._normalize_result_ids(result)
            return self._process_cvss_items(result, include_category=True)

        except Exception as e:
            logger.error(f"LLM 评级分类失败: {e}")
            llm_logger.log_rate_and_classify(model=self.model, events=events,
                                             messages=messages, error=str(e), duration_ms=0)
            return self._default_rate_classify_result(events)

    def _default_rate_classify_result(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成默认的评级分类结果"""
        return [{
            "id": e["id"],
            "severity": "medium",
            "cvss_score": 5.0,
            "cvss_vector": "",
            "category_code": None
        } for e in events]

    # ──────────────────────────────────────────
    # 异步版本（适用于 FastAPI / async 上下文）
    # ──────────────────────────────────────────

    async def async_batch_check_security(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """异步批量判断是否为 AI/LLM 安全事件"""
        if not self.is_available():
            return self._default_security_result(events, "LLM服务不可用")
        if not events:
            return []
        chunks = self._chunk_events(events)
        return await self._run_concurrent_async(self._async_check_security_chunk, chunks)

    async def _async_check_security_chunk(self, events: List[Dict]) -> List[Dict]:
        system_prompt = """你是AI/LLM安全事件识别专家。判断每个事件是否属于AI/LLM安全相关事件。

✅ 属于安全事件（is_security_event=true）：
- CVE漏洞披露、安全补丁公告
- 提示词注入(Prompt Injection)、越狱(Jailbreak)攻击
- 对抗样本攻击、模型逃逸
- 训练数据泄露、隐私信息泄露
- 模型后门、供应链攻击
- 安全机制绕过、权限提升
- 数据投毒、模型篡改
- 拒绝服务(DoS)攻击相关

❌ 不属于安全事件（is_security_event=false）：
- 产品发布、功能更新、版本迭代
- 使用教程、操作指南
- 行业新闻、市场分析
- 商业推广、合作公告
- 模型能力评测、性能对比（非安全维度）

以JSON数组输出，每项必须包含：
- id: 整数（事件ID）
- is_security_event: 布尔值
- reason: 字符串（≤20字，简要说明）

示例：[{"id":1,"is_security_event":true,"reason":"CVE漏洞披露"},{"id":2,"is_security_event":false,"reason":"产品功能更新"}]"""
        events_text = self._build_events_text(events, max_desc=300)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请判断以下{len(events)}个事件是否属于AI/LLM安全事件：\n\n{events_text}"},
        ]
        try:
            content, _ = await self._call_llm_async(messages, DEFAULT_MAX_TOKENS)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_security_result(events, "JSON解析失败")
            self._normalize_result_ids(result)
            return result
        except Exception as e:
            logger.error(f"[async] LLM 安全事件判断失败: {e}")
            return self._default_security_result(events, "判断失败")

    async def async_batch_rate_and_classify(self, events: List[Dict[str, Any]],
                                            categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """异步批量评级并分类事件"""
        if not self.is_available():
            return self._default_rate_classify_result(events)
        if not events:
            return []
        chunks = self._chunk_events(events)
        return await self._run_concurrent_async(
            lambda chunk: self._async_rate_and_classify_chunk(chunk, categories), chunks
        )

    async def _async_rate_and_classify_chunk(self, events: List[Dict],
                                             categories: List[Dict]) -> List[Dict]:
        cats_text = "\n".join(f"- {c['code']}: {c['name']}" for c in categories)
        system_prompt = f"""你是AI安全风险评估专家，使用CVSS 4.0评估LLM安全事件并分类。

## CVSS 4.0 指标（请根据事件描述逐项评估）
- AC: L=无需绕过安全机制即可利用 / H=需要绕过特定安全机制
- PR: N=无需任何权限 / L=需要普通用户权限 / H=需要管理员权限
- UI: N=无需用户交互 / P=需要用户被动点击等 / A=需要用户主动参与
- VC/VI/VA: N=无影响 / L=部分影响 / H=严重影响

## 评估原则
- 根据漏洞实际可利用性和影响范围评估，不要一律给高或一律给低
- 考虑攻击是否需要特殊条件（如需要登录、需要用户交互等）

## 可用分类
{cats_text}

## 分类原则
- 根据事件的核心安全问题分类，确实无法匹配时设为null

必须以JSON数组输出，每项包含 id、ac、pr、ui、vc、vi、va、category_code。"""
        events_text = self._build_events_text(events, max_desc=800)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请评估并分类以下{len(events)}个LLM安全事件：\n\n{events_text}"},
        ]
        try:
            content, _ = await self._call_llm_async(messages, DEFAULT_MAX_TOKENS)
            result = self._unwrap_result(content, None)
            if result is None:
                return self._default_rate_classify_result(events)
            self._normalize_result_ids(result)
            return self._process_cvss_items(result, include_category=True)
        except Exception as e:
            logger.error(f"[async] LLM 评级分类失败: {e}")
            return self._default_rate_classify_result(events)


# 进度回调类型
ProgressCallback = callable  # type: ignore

# 全局进度回调（由任务层设置）
_progress_callback: Optional[ProgressCallback] = None


def set_progress_callback(callback: Optional[ProgressCallback]):
    """设置进度回调函数"""
    global _progress_callback
    _progress_callback = callback


def get_progress_callback() -> Optional[ProgressCallback]:
    """获取当前进度回调"""
    return _progress_callback


# 单例实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
