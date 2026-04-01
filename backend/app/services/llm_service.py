"""
LLM 服务 - 统一的评级与分类逻辑
支持批量处理以节省 token
使用 CVSS 4.0 标准进行安全等级评定
"""
import logging
import json
import re
import time
from typing import Optional, List, Dict, Any, Tuple
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError, BadRequestError

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

# 批量处理配置（已移至 config.py，通过 settings.llm_batch_size 配置）
# 这里保留常量作为安全上限，防止配置过大
MAX_BATCH_SIZE_LIMIT = 100  # 硬性上限，防止单次请求过大

# glm-5 等推理模型会使用大量 token 进行思考(reasoning)，
# 需要设置足够大的 max_tokens 确保有足够空间输出实际内容
# glm-5 上下文最大 200k，输出最大 128k
DEFAULT_MAX_TOKENS = 8192


def get_batch_size() -> int:
    """获取配置的批次大小"""
    return min(settings.llm_batch_size, MAX_BATCH_SIZE_LIMIT)


class LLMService:
    """LLM 服务类 - 封装评级、分类、安全检查功能"""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.model = settings.llm_model
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        if settings.llm_api_key:
            self.client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url
            )
        else:
            logger.warning("未配置 LLM API 密钥")

    def is_available(self) -> bool:
        """检查 LLM 服务是否可用"""
        return self.client is not None

    def batch_check_security(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量判断是否为安全事件

        Args:
            events: 事件列表，每个事件包含 id, title, description

        Returns:
            结果列表: [{"id": 1, "is_security_event": true, "reason": "..."}, ...]
        """
        if not self.is_available():
            return [{"id": e["id"], "is_security_event": False, "reason": "LLM服务不可用"} for e in events]

        if not events:
            return []

        # 构建批量提示
        events_text = "\n\n".join([
            f"[事件{e['id']}]\n标题：{e['title']}\n描述：{(e.get('description') or e.get('raw_content') or '')[:300]}"
            for e in events
        ])

        system_prompt = """你是一个AI安全事件识别专家。请判断以下事件是否为AI/LLM相关的安全事件。

## 安全事件定义

✅ 包括：漏洞披露、CVE公告、攻击手法（提示注入/越狱/对抗攻击）、隐私泄露、模型安全风险、安全机制绕过

❌ 不包括：产品发布、功能更新、教程文章、行业动态、商业推广、能力评测

## 输出要求
以JSON数组输出，每个对象包含：
- id: 事件ID
- is_security_event: 布尔值
- reason: 理由（不超过15字）

## 输出示例
[
  {"id": 1, "is_security_event": true, "reason": "CVE漏洞"},
  {"id": 2, "is_security_event": false, "reason": "产品更新"}
]"""

        user_prompt = f"请判断以下{len(events)}个事件是否为AI/LLM安全事件：\n\n{events_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        llm_logger = get_llm_logger()
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=DEFAULT_MAX_TOKENS
            )

            content = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000

            # 记录成功调用
            llm_logger.log_security_check(
                model=self.model,
                events=events,
                messages=messages,
                response=content,
                duration_ms=duration_ms
            )

            # 使用安全解析
            result, parse_error = safe_parse_json(content)
            if result is None:
                logger.error(f"LLM 返回JSON解析失败: {parse_error}, 原始内容: {content[:200]}")
                return self._default_security_result(events, f"JSON解析失败: {parse_error}")

            # 处理可能的包装格式
            if isinstance(result, dict) and "results" in result:
                result = result["results"]
            elif isinstance(result, list):
                pass
            else:
                logger.error(f"LLM 返回格式异常: {content[:200]}")
                return self._default_security_result(events, "返回格式异常")

            # 修复 ID 格式：LLM 可能返回 "事件9" 这样的字符串，需要提取数字
            for item in result:
                if "id" in item and isinstance(item["id"], str):
                    match = re.search(r'\d+', str(item["id"]))
                    if match:
                        item["id"] = int(match.group())

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"LLM 安全事件判断失败: {e}")

            # 记录失败调用
            llm_logger.log_security_check(
                model=self.model,
                events=events,
                messages=messages,
                error=error_msg,
                duration_ms=duration_ms
            )

            return self._default_security_result(events, f"判断失败")

    def _default_security_result(self, events: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
        """生成默认的安全检查结果

        当LLM调用失败时，默认标记为非安全事件(is_security_event=False)，
        避免将非安全事件误判为安全事件推送给用户。
        """
        return [{"id": e["id"], "is_security_event": False, "reason": reason} for e in events]

    def batch_rate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量评级事件 - 使用CVSS 4.0标准

        Args:
            events: 事件列表，每个事件包含 id, title, description

        Returns:
            结果列表: [{"id": 1, "severity": "high", "cvss_score": 8.7, "cvss_vector": "CVSS:4.0/..."}, ...]
        """
        if not self.is_available():
            return self._default_rating_result(events)

        if not events:
            return []

        # 构建批量提示
        events_text = "\n\n".join([
            f"[事件{e['id']}]\n标题：{e['title']}\n描述：{(e.get('description') or e.get('raw_content') or '')[:800]}"
            for e in events
        ])

        system_prompt = """你是一个AI安全风险评估专家，使用CVSS 4.0标准评估LLM安全事件的严重程度。

## 评估指标说明

### 1. 攻击复杂度 (AC) - 攻击是否需要绕过安全机制？
- L (Low): 攻击者无需采取任何额外措施，可重复成功攻击
- H (High): 需要绕过安全增强技术（如ASLR、DEP）或获取目标特定密钥

### 2. 所需权限 (PR) - 攻击前需要什么权限？
- N (None): 无需任何权限，未认证即可攻击
- L (Low): 需要普通用户权限，只能访问非敏感资源
- H (High): 需要管理员/高级权限

### 3. 用户交互 (UI) - 是否需要用户参与？
- N (None): 不需要任何用户交互
- P (Passive): 用户被动参与（如浏览被篡改的网页）
- A (Active): 用户需要主动执行特定操作（如打开文件、点击链接）

### 4. 机密性影响 (VC) - 信息泄露程度？
- N (None): 无信息泄露
- L (Low): 部分非敏感信息泄露
- H (High): 全部或关键敏感信息泄露（如密钥、密码、训练数据）

### 5. 完整性影响 (VI) - 数据篡改程度？
- N (None): 无数据被修改
- L (Low): 部分数据可被修改，但不直接影响系统安全
- H (High): 任意数据可被修改，或修改会直接严重影响系统

### 6. 可用性影响 (VA) - 服务中断程度？
- N (None): 无服务中断
- L (Low): 性能下降或间歇性中断
- H (High): 完全不可用或持续性拒绝服务

## LLM安全事件评估指南

| 场景 | AC | PR | UI | VC | VI | VA |
|------|----|----|----|----|----|----|
| 公开API提示注入 | L | N | N | L-H | L-H | N |
| 越狱攻击获取训练数据 | L-H | N | N | H | N | N |
| 对抗样本攻击 | H | N | N | N | L-H | N |
| 间接提示注入(需用户触发) | L | N | P-A | L-H | L-H | N |
| LLM服务DoS攻击 | L | N | N | N | N | H |

## 输出要求
以JSON数组输出，每个对象包含：
- id: 事件ID
- ac: 攻击复杂度 (L/H)
- pr: 所需权限 (N/L/H)
- ui: 用户交互 (N/P/A)
- vc: 机密性影响 (N/L/H)
- vi: 完整性影响 (N/L/H)
- va: 可用性影响 (N/L/H)

## 输出示例
[
  {"id": 1, "ac": "L", "pr": "N", "ui": "N", "vc": "H", "vi": "H", "va": "N"},
  {"id": 2, "ac": "L", "pr": "N", "ui": "A", "vc": "L", "vi": "N", "va": "N"}
]"""

        user_prompt = f"请根据CVSS 4.0标准评估以下{len(events)}个LLM安全事件：\n\n{events_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        llm_logger = get_llm_logger()
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=DEFAULT_MAX_TOKENS
            )

            content = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000

            # 记录成功调用
            llm_logger.log_rating(
                model=self.model,
                events=events,
                messages=messages,
                response=content,
                duration_ms=duration_ms
            )

            # 使用安全解析
            result, parse_error = safe_parse_json(content)
            if result is None:
                logger.error(f"LLM 返回JSON解析失败: {parse_error}, 原始内容: {content[:200]}")
                return self._default_rating_result(events)

            # 处理可能的包装格式
            if isinstance(result, dict) and "results" in result:
                result = result["results"]
            elif isinstance(result, list):
                pass
            else:
                logger.error(f"LLM 返回格式异常: {content[:200]}")
                return self._default_rating_result(events)

            # 处理结果：计算CVSS分数并映射severity
            processed_result = []
            for item in result:
                # 修复 ID 格式
                if "id" in item and isinstance(item["id"], str):
                    match = re.search(r'\d+', str(item["id"]))
                    if match:
                        item["id"] = int(match.group())

                # 验证并规范化CVSS指标值
                ac = self._validate_cvss_metric(item.get("ac", "L"), ["L", "H"], "L")
                pr = self._validate_cvss_metric(item.get("pr", "N"), ["N", "L", "H"], "N")
                ui = self._validate_cvss_metric(item.get("ui", "N"), ["N", "P", "A"], "N")
                vc = self._validate_cvss_metric(item.get("vc", "N"), ["N", "L", "H"], "N")
                vi = self._validate_cvss_metric(item.get("vi", "N"), ["N", "L", "H"], "N")
                va = self._validate_cvss_metric(item.get("va", "N"), ["N", "L", "H"], "N")

                # 计算CVSS分数
                cvss_score, cvss_vector = calculate_cvss_score(ac, pr, ui, vc, vi, va)

                # 映射到severity
                severity = cvss_score_to_severity(cvss_score)

                processed_result.append({
                    "id": item.get("id"),
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "cvss_vector": cvss_vector
                })

            return processed_result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"LLM 评级失败: {e}")

            # 记录失败调用
            llm_logger.log_rating(
                model=self.model,
                events=events,
                messages=messages,
                error=error_msg,
                duration_ms=duration_ms
            )

            return self._default_rating_result(events)

    def _validate_cvss_metric(self, value: Any, valid_values: List[str], default: str) -> str:
        """验证CVSS指标值

        Args:
            value: 输入值
            valid_values: 有效值列表
            default: 默认值

        Returns:
            验证后的值或默认值
        """
        if isinstance(value, str):
            value_upper = value.upper()
            if value_upper in valid_values:
                return value_upper
        return default

    def _default_rating_result(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成默认的评级结果"""
        return [{
            "id": e["id"],
            "severity": "medium",
            "cvss_score": 5.0,
            "cvss_vector": ""
        } for e in events]

    def batch_classify_events(self, events: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量分类事件

        Args:
            events: 事件列表，每个事件包含 id, title, description
            categories: 分类列表，包含 code 和 name

        Returns:
            结果列表: [{"id": 1, "category_code": "prompt_injection"}, ...]
        """
        if not self.is_available():
            return [{"id": e["id"], "category_code": None} for e in events]

        if not events:
            return []

        # 构建分类列表
        categories_text = "\n".join([
            f"- {c['code']}: {c['name']}" + (f" ({c.get('description')})" if c.get('description') else "")
            for c in categories
        ])

        # 构建批量提示
        events_text = "\n\n".join([
            f"[事件{e['id']}]\n标题：{e['title']}\n描述：{(e.get('description') or e.get('raw_content') or '')[:300]}"
            for e in events
        ])

        system_prompt = f"""你是一个AI安全事件分类专家。请将以下事件分类到最合适的类别。

## 可用分类
{categories_text}

## 输出要求
请以JSON数组格式输出，每个事件一个对象，包含：
- id: 事件ID（与输入一致）
- category_code: 分类代码（必须是上述分类之一，如果无法分类则为 null）

## 输出示例
[
  {{"id": 1, "category_code": "LLM01"}},
  {{"id": 2, "category_code": "LLM06"}}
]"""

        user_prompt = f"请将以下{len(events)}个事件分类：\n\n{events_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        llm_logger = get_llm_logger()
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=DEFAULT_MAX_TOKENS
            )

            content = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000

            # 记录成功调用
            llm_logger.log_classification(
                model=self.model,
                events=events,
                messages=messages,
                response=content,
                duration_ms=duration_ms
            )

            # 使用安全解析
            result, parse_error = safe_parse_json(content)
            if result is None:
                logger.error(f"LLM 返回JSON解析失败: {parse_error}, 原始内容: {content[:200]}")
                return self._default_classify_result(events)

            # 处理可能的包装格式
            if isinstance(result, dict) and "results" in result:
                result = result["results"]
            elif isinstance(result, list):
                pass
            else:
                logger.error(f"LLM 返回格式异常: {content[:200]}")
                return self._default_classify_result(events)

            # 修复 ID 格式：LLM 可能返回 "事件9" 这样的字符串，需要提取数字
            for item in result:
                if "id" in item and isinstance(item["id"], str):
                    match = re.search(r'\d+', str(item["id"]))
                    if match:
                        item["id"] = int(match.group())

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"LLM 分类失败: {e}")

            # 记录失败调用
            llm_logger.log_classification(
                model=self.model,
                events=events,
                messages=messages,
                error=error_msg,
                duration_ms=duration_ms
            )

            return self._default_classify_result(events)

    def _default_classify_result(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成默认的分类结果"""
        return [{"id": e["id"], "category_code": None} for e in events]

    def batch_rate_and_classify(self, events: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量评级并分类事件 - 使用CVSS 4.0标准

        Args:
            events: 事件列表
            categories: 分类列表

        Returns:
            结果列表: [{"id": 1, "severity": "high", "cvss_score": 8.7, "cvss_vector": "...", "category_code": "prompt_injection"}, ...]
        """
        if not self.is_available():
            return self._default_rate_classify_result(events)

        if not events:
            return []

        # 构建分类列表
        categories_text = "\n".join([
            f"- {c['code']}: {c['name']}"
            for c in categories
        ])

        # 构建批量提示
        events_text = "\n\n".join([
            f"[事件{e['id']}]\n标题：{e['title']}\n描述：{(e.get('description') or e.get('raw_content') or '')[:800]}"
            for e in events
        ])

        system_prompt = f"""你是一个AI安全风险评估专家，使用CVSS 4.0标准评估LLM安全事件。

## CVSS 4.0 评估指标

### 可利用性指标
- AC (攻击复杂度): L=无需绕过安全机制/H=需要绕过安全机制
- PR (所需权限): N=无需权限/L=普通用户权限/H=管理员权限
- UI (用户交互): N=无需交互/P=被动交互/A=主动交互

### 影响指标（脆弱系统）
- VC (机密性影响): N=无泄露/L=部分泄露/H=全部/关键泄露
- VI (完整性影响): N=无篡改/L=部分篡改/H=完全控制
- VA (可用性影响): N=无中断/L=性能下降/H=完全不可用

## 可用分类
{categories_text}

## 输出要求
以JSON数组输出，每个对象包含：
- id: 事件ID
- ac: 攻击复杂度 (L/H)
- pr: 所需权限 (N/L/H)
- ui: 用户交互 (N/P/A)
- vc: 机密性影响 (N/L/H)
- vi: 完整性影响 (N/L/H)
- va: 可用性影响 (N/L/H)
- category_code: 分类代码（必须是上述分类之一）

## 输出示例
[
  {{"id": 1, "ac": "L", "pr": "N", "ui": "N", "vc": "H", "vi": "H", "va": "N", "category_code": "LLM01"}},
  {{"id": 2, "ac": "L", "pr": "N", "ui": "A", "vc": "L", "vi": "N", "va": "N", "category_code": "LLM06"}}
]"""

        user_prompt = f"请根据CVSS 4.0标准评估以下{len(events)}个LLM安全事件并分类：\n\n{events_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        llm_logger = get_llm_logger()
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=DEFAULT_MAX_TOKENS
            )

            content = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000

            # 记录成功调用
            llm_logger.log_rate_and_classify(
                model=self.model,
                events=events,
                messages=messages,
                response=content,
                duration_ms=duration_ms
            )

            # 使用安全解析
            result, parse_error = safe_parse_json(content)
            if result is None:
                logger.error(f"LLM 返回JSON解析失败: {parse_error}, 原始内容: {content[:200] if content else ''}")
                return self._default_rate_classify_result(events)

            if isinstance(result, dict) and "results" in result:
                result = result["results"]
            elif isinstance(result, list):
                pass
            else:
                logger.error(f"LLM 返回格式异常: {content[:200] if content else ''}")
                return self._default_rate_classify_result(events)

            # 处理结果：计算CVSS分数并映射severity
            processed_result = []
            for item in result:
                # 修复 ID 格式
                if "id" in item and isinstance(item["id"], str):
                    match = re.search(r'\d+', str(item["id"]))
                    if match:
                        item["id"] = int(match.group())

                # 验证并规范化CVSS指标值
                ac = self._validate_cvss_metric(item.get("ac", "L"), ["L", "H"], "L")
                pr = self._validate_cvss_metric(item.get("pr", "N"), ["N", "L", "H"], "N")
                ui = self._validate_cvss_metric(item.get("ui", "N"), ["N", "P", "A"], "N")
                vc = self._validate_cvss_metric(item.get("vc", "N"), ["N", "L", "H"], "N")
                vi = self._validate_cvss_metric(item.get("vi", "N"), ["N", "L", "H"], "N")
                va = self._validate_cvss_metric(item.get("va", "N"), ["N", "L", "H"], "N")

                # 计算CVSS分数
                cvss_score, cvss_vector = calculate_cvss_score(ac, pr, ui, vc, vi, va)

                # 映射到severity
                severity = cvss_score_to_severity(cvss_score)

                processed_result.append({
                    "id": item.get("id"),
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "cvss_vector": cvss_vector,
                    "category_code": item.get("category_code")
                })

            return processed_result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"LLM 评级分类失败: {e}")

            # 记录失败调用
            llm_logger.log_rate_and_classify(
                model=self.model,
                events=events,
                messages=messages,
                error=error_msg,
                duration_ms=duration_ms
            )

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


# 单例实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
