"""
AIVD数据采集服务
从GitHub avidml/avid-db获取AVID报告数据
将整个reports目录克隆到本地，然后从本地文件中解析数据条目
"""
import os
import json
import shutil
import subprocess
from datetime import datetime
from typing import List, Dict, Optional
import logging

import requests

logger = logging.getLogger(__name__)

# 项目根目录（backend的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# AIVD临时文件夹路径（包含git仓库）
AIVD_TEMP_DIR = os.path.join(PROJECT_ROOT, "temp", "aivd")
# 报告文件目录
AIVD_REPORTS_DIR = os.path.join(AIVD_TEMP_DIR, "avid-db", "reports")

# GitHub仓库信息
GITHUB_REPO_URL = "https://github.com/avidml/avid-db.git"
GITHUB_BRANCH = "main"


def parse_avid_date(date_str: str) -> Optional[datetime]:
    """
    解析AVID日期字符串

    Args:
        date_str: 日期字符串，如 '2024-09-26'

    Returns:
        datetime对象，解析失败时返回None
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    logger.warning(f"无法解析日期格式: {date_str}")
    return None


def map_risk_level(severity: Optional[str], score: Optional[float]) -> str:
    """
    根据CVSS严重程度和评分映射风险等级

    Args:
        severity: CVSS baseSeverity (CRITICAL, HIGH, MEDIUM, LOW, NONE)
        score: CVSS baseScore

    Returns:
        risk_level: critical, high, medium, 或 low
    """
    if severity:
        severity_upper = severity.upper()
        if severity_upper == "CRITICAL":
            return "critical"
        elif severity_upper == "HIGH":
            return "high"
        elif severity_upper == "MEDIUM":
            return "medium"
        elif severity_upper in ("LOW", "NONE"):
            return "low"

    # 如果没有severity，根据score判断
    if score is not None:
        if score >= 9.0:
            return "critical"
        elif score >= 7.0:
            return "high"
        elif score >= 4.0:
            return "medium"
        else:
            return "low"

    return "low"


class AIVDCollector:
    """AIVD数据采集器 - 从本地克隆的仓库获取JSON报告"""

    def __init__(self):
        # 确保temp目录存在
        os.makedirs(AIVD_TEMP_DIR, exist_ok=True)
        logger.info(f"AIVD临时目录: {AIVD_TEMP_DIR}")

    def clone_or_update_repo(self) -> bool:
        """
        克隆或更新GitHub仓库

        Returns:
            是否成功
        """
        repo_dir = os.path.join(AIVD_TEMP_DIR, "avid-db")

        # 检查是否已存在仓库
        if os.path.exists(os.path.join(repo_dir, ".git")):
            logger.info("AIVD仓库已存在，尝试更新...")
            return self._update_repo(repo_dir)
        else:
            logger.info("开始克隆AIVD仓库...")
            return self._clone_repo(repo_dir)

    def _clone_repo(self, repo_dir: str) -> bool:
        """
        克隆GitHub仓库

        Args:
            repo_dir: 目标目录

        Returns:
            是否成功
        """
        try:
            # 使用git clone命令，只克隆reports目录以减少下载量
            result = subprocess.run(
                [
                    "git", "clone",
                    "--filter=blob:none",
                    "--no-checkout",
                    GITHUB_REPO_URL,
                    repo_dir
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=AIVD_TEMP_DIR
            )

            if result.returncode != 0:
                logger.error(f"克隆仓库失败: {result.stderr}")
                logger.info("尝试使用完整克隆...")
                return self._full_clone(repo_dir)

            # 检出reports目录
            subprocess.run(
                ["git", "sparse-checkout", "set", "reports"],
                cwd=repo_dir,
                capture_output=True,
                text=True
            )

            subprocess.run(
                ["git", "checkout", GITHUB_BRANCH],
                cwd=repo_dir,
                capture_output=True,
                text=True
            )

            logger.info("AIVD仓库克隆成功")
            return True

        except subprocess.TimeoutExpired:
            logger.error("克隆仓库超时")
            return False
        except Exception as e:
            logger.error(f"克隆仓库时出错: {e}")
            return self._full_clone(repo_dir)

    def _full_clone(self, repo_dir: str) -> bool:
        """
        完整克隆仓库（备选方案）

        Args:
            repo_dir: 目标目录

        Returns:
            是否成功
        """
        # 如果有旧的目录，先删除
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)

        try:
            result = subprocess.run(
                ["git", "clone", GITHUB_REPO_URL, repo_dir],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=AIVD_TEMP_DIR
            )

            if result.returncode != 0:
                logger.error(f"完整克隆失败: {result.stderr}")
                return False

            logger.info("AIVD仓库完整克隆成功")
            return True

        except subprocess.TimeoutExpired:
            logger.error("克隆仓库超时")
            return False
        except Exception as e:
            logger.error(f"克隆仓库时出错: {e}")
            return False

    def _update_repo(self, repo_dir: str) -> bool:
        """
        更新已存在的GitHub仓库

        Args:
            repo_dir: 仓库目录

        Returns:
            是否成功
        """
        try:
            # 先尝试git fetch
            result = subprocess.run(
                ["git", "fetch", "origin", GITHUB_BRANCH],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.warning(f"git fetch失败: {result.stderr}，尝试重新克隆")
                return self._clone_repo(repo_dir)

            # 检查是否有更新
            result = subprocess.run(
                ["git", "rev-list", f"HEAD..origin/{GITHUB_BRANCH}", "--count"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            commits_behind = 0
            if result.returncode == 0 and result.stdout.strip():
                try:
                    commits_behind = int(result.stdout.strip())
                except ValueError:
                    pass

            if commits_behind > 0:
                logger.info(f"发现 {commits_behind} 个新提交，执行pull...")
                result = subprocess.run(
                    ["git", "pull", "origin", GITHUB_BRANCH],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode != 0:
                    logger.warning(f"git pull失败: {result.stderr}，可能需要重新克隆")
                    return self._clone_repo(repo_dir)

                logger.info("AIVD仓库更新成功")
            else:
                logger.info("AIVD仓库已是最新")

            return True

        except subprocess.TimeoutExpired:
            logger.error("更新仓库超时，尝试重新克隆")
            return self._clone_repo(repo_dir)
        except Exception as e:
            logger.error(f"更新仓库时出错: {e}，尝试重新克隆")
            return self._clone_repo(repo_dir)

    def collect(self, limit: int = 100) -> List[Dict]:
        """
        主入口：采集并解析AIVD数据

        Args:
            limit: 返回的最大事件数量，0表示不限制

        Returns:
            解析后的AIVD数据列表
        """
        logger.info("开始采集AIVD数据...")

        # 克隆或更新仓库
        if not self.clone_or_update_repo():
            logger.error("无法获取AIVD仓库")
            return []

        # 检查reports目录是否存在
        if not os.path.exists(AIVD_REPORTS_DIR):
            logger.error(f"Reports目录不存在: {AIVD_REPORTS_DIR}")
            return []

        all_reports = []

        # 遍历reports目录下的所有年份子目录
        for year_dir in sorted(os.listdir(AIVD_REPORTS_DIR)):
            year_path = os.path.join(AIVD_REPORTS_DIR, year_dir)

            if not os.path.isdir(year_path):
                continue

            logger.info(f"正在处理年份目录: {year_dir}")

            # 遍历年份目录下的所有JSON文件
            for file_name in sorted(os.listdir(year_path)):
                if not file_name.endswith(".json"):
                    continue

                file_path = os.path.join(year_path, file_name)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        json_data = json.load(f)

                    # 解析单条记录
                    parsed = self.parse_report(json_data)
                    if parsed:
                        all_reports.append(parsed)
                        logger.debug(f"成功解析: {parsed.get('external_id')}")

                except json.JSONDecodeError as e:
                    logger.warning(f"解析JSON文件失败 {file_name}: {e}")
                except Exception as e:
                    logger.warning(f"处理文件时出错 {file_name}: {e}")

                # 限制处理数量
                if limit > 0 and len(all_reports) >= limit * 2:
                    break

            if limit > 0 and len(all_reports) >= limit * 2:
                break

        # 限制返回数量
        if limit > 0 and len(all_reports) > limit:
            all_reports = all_reports[:limit]

        logger.info(f"成功解析 {len(all_reports)} 条AIVD报告")

        return all_reports

    def parse_report(self, data: Dict) -> Optional[Dict]:
        """
        解析单条AVID JSON报告为统一格式

        Args:
            data: AVID JSON数据

        Returns:
            解析后的数据字典，如果解析失败则返回None
        """
        try:
            metadata = data.get("metadata", {})
            report_id = metadata.get("report_id", "")

            if not report_id:
                logger.warning("报告缺少report_id，跳过")
                return None

            # 获取标题：优先使用problemtype.description.value
            title = data.get("problemtype", {}).get("description", {}).get("value", "")
            if not title:
                title = report_id

            # 获取描述
            description = data.get("description", {}).get("value", "")

            # 获取报告日期
            publish_date = parse_avid_date(data.get("reported_date"))

            # 获取来源URL：查找references中type="source"的第一个
            source_url = ""
            references = data.get("references", [])
            for ref in references:
                if ref.get("type") == "source":
                    source_url = ref.get("url", "")
                    break

            # 获取CVSS评分和严重程度
            impact = data.get("impact", {})
            cvss = impact.get("cvss", {})
            severity_score = cvss.get("baseScore")
            severity = cvss.get("baseSeverity")

            # 映射风险等级
            risk_level = map_risk_level(severity, severity_score)

            # 获取受影响的模型：从affects.artifacts中提取type="Model"的name
            affected_models = []
            affects = data.get("affects", {})
            artifacts = affects.get("artifacts", [])
            for artifact in artifacts:
                if artifact.get("type") == "Model":
                    model_name = artifact.get("name", "")
                    if model_name:
                        affected_models.append(model_name)

            return {
                "source_type": "aivd",
                "source_name": "AIVD",
                "title": title,
                "description": description,
                "original_url": source_url,
                "published_at": publish_date,
                "severity": risk_level,
                "severity_source": "nvd" if severity_score else None,
                "affected_versions": ", ".join(affected_models) if affected_models else None,
                "raw_content": json.dumps(data, ensure_ascii=False)
            }

        except Exception as e:
            logger.error(f"解析AVID报告时出错: {e}")
            return None


# 创建默认实例
aivd_collector = AIVDCollector()
