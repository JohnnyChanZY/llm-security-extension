"""
NVD数据采集服务
从National Vulnerability Database获取CVE数据
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


class NVDCollector:
    """NVD数据采集器"""

    def __init__(self):
        self.api_key = settings.nvd_api_key
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.headers = {
            "apiKey": self.api_key
        }
        # 请求间隔，有API Key时为0.6秒，无API Key时为6秒
        self.request_interval = 0.6 if self.api_key else 6.0

    def fetch_cves(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keyword: Optional[str] = None,
        results_per_page: int = 100,
        start_index: int = 0
    ) -> Dict:
        """
        获取CVE数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            keyword: 搜索关键词
            results_per_page: 每页结果数
            start_index: 起始索引

        Returns:
            API响应数据
        """
        params = {
            "resultsPerPage": results_per_page,
            "startIndex": start_index
        }

        # 设置日期范围
        if start_date:
            params["pubStartDate"] = start_date.strftime("%Y-%m-%dT%H:%M:%S.000")
        if end_date:
            params["pubEndDate"] = end_date.strftime("%Y-%m-%dT%H:%M:%S.000")

        # 设置关键词搜索
        if keyword:
            params["keywordSearch"] = keyword

        try:
            logger.info(f"正在获取NVD数据，参数: {params}")
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            time.sleep(self.request_interval)  # 遵守API限流规则
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取NVD数据失败: {e}")
            raise

    def fetch_recent_cves(self, days: int = 7) -> List[Dict]:
        """
        获取最近N天的CVE数据

        Args:
            days: 天数

        Returns:
            CVE列表
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        all_cves = []
        start_index = 0
        results_per_page = 100

        while True:
            data = self.fetch_cves(
                start_date=start_date,
                end_date=end_date,
                results_per_page=results_per_page,
                start_index=start_index
            )

            vulnerabilities = data.get("vulnerabilities", [])
            all_cves.extend(vulnerabilities)

            total_results = data.get("totalResults", 0)
            logger.info(f"已获取 {len(all_cves)}/{total_results} 条CVE数据")

            # 检查是否还有更多数据
            if len(all_cves) >= total_results:
                break

            start_index += results_per_page

        return all_cves

    def fetch_llm_related_cves(self, days: int = 30) -> List[Dict]:
        """
        获取与LLM相关的CVE数据
        使用关键词搜索

        Args:
            days: 搜索天数范围

        Returns:
            LLM相关CVE列表
        """
        # LLM相关关键词列表
        llm_keywords = [
            "LLM",
            "GPT",
            "ChatGPT",
            "language model",
            "artificial intelligence",
            "machine learning",
            "natural language",
            "prompt",
            "AI model"
        ]

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        all_cves = []
        seen_ids = set()

        for keyword in llm_keywords:
            logger.info(f"搜索关键词: {keyword}")
            data = self.fetch_cves(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date
            )
            vulnerabilities = data.get("vulnerabilities", [])

            for vuln in vulnerabilities:
                cve_id = vuln.get("cve", {}).get("id")
                if cve_id and cve_id not in seen_ids:
                    seen_ids.add(cve_id)
                    all_cves.append(vuln)

        return all_cves

    def parse_cve_data(self, cve_item: Dict) -> Dict:
        """
        解析CVE数据为统一格式

        Args:
            cve_item: CVE原始数据

        Returns:
            解析后的数据字典
        """
        cve = cve_item.get("cve", {})

        # 获取CVE ID
        cve_id = cve.get("id", "")

        # 获取描述
        descriptions = cve.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break

        # 获取CVSS评分
        metrics = cve.get("metrics", {})
        severity_score = None
        severity = None
        if "cvssMetricV31" in metrics:
            cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
            severity_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity")
        elif "cvssMetricV2" in metrics:
            cvss_data = metrics["cvssMetricV2"][0].get("cvssData", {})
            severity_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity")

        # 获取发布日期
        published = cve.get("published", "")

        # 获取影响的产品
        configurations = cve.get("configurations", [])
        affected_products = []
        for config in configurations:
            nodes = config.get("nodes", [])
            for node in nodes:
                cpe_match = node.get("cpeMatch", [])
                for cpe in cpe_match:
                    criteria = cpe.get("criteria", "")
                    if criteria:
                        affected_products.append(criteria)

        # 获取参考链接
        references = cve.get("references", [])
        source_url = references[0].get("url", "") if references else ""

        # 映射严重程度
        severity_mapped = self._map_severity(severity, severity_score)

        return {
            "source_type": "nvd",
            "source_name": "NVD",
            "title": f"{cve_id}: {description[:100]}..." if len(description) > 100 else f"{cve_id}: {description}",
            "description": description,
            "original_url": source_url,
            "published_at": published,
            "cve_id": cve_id,
            "severity": severity_mapped,
            "severity_source": "nvd" if severity_score else None,
            "affected_versions": ", ".join(affected_products[:10]) if affected_products else None,
            "raw_content": str(cve_item),
        }

    def _map_severity(self, severity: Optional[str], score: Optional[float]) -> Optional[str]:
        """映射严重程度到统一格式"""
        if severity:
            severity_upper = severity.upper()
            mapping = {
                "CRITICAL": "critical",
                "HIGH": "high",
                "MEDIUM": "medium",
                "LOW": "low"
            }
            return mapping.get(severity_upper, None)

        if score is not None:
            if score >= 9.0:
                return "critical"
            elif score >= 7.0:
                return "high"
            elif score >= 4.0:
                return "medium"
            else:
                return "low"

        return None

    def collect_and_parse(self, days: int = 7, llm_only: bool = False) -> List[Dict]:
        """
        采集并解析CVE数据

        Args:
            days: 天数范围
            llm_only: 是否只采集LLM相关CVE

        Returns:
            解析后的CVE数据列表
        """
        if llm_only:
            cves = self.fetch_llm_related_cves(days=days)
        else:
            cves = self.fetch_recent_cves(days=days)
        return [self.parse_cve_data(cve) for cve in cves]


# 创建默认实例
nvd_collector = NVDCollector()
