"""
AIID数据采集服务
从AI Incident Database网站获取AI安全事件数据
通过下载CSV快照文件获取数据
"""
import os
import re
import csv
import tarfile
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 项目根目录（backend的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# AIID临时文件夹路径
AIID_TEMP_DIR = os.path.join(PROJECT_ROOT, "temp", "aiid")


def parse_iso_date(date_str: str) -> Optional[datetime]:
    """
    解析ISO 8601格式日期字符串

    Args:
        date_str: 日期字符串，如 '2025-06-06T00:00:00Z'

    Returns:
        datetime对象，解析失败时返回None
    """
    if not date_str:
        return None

    # 尝试多种日期格式
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",      # 2025-06-06T00:00:00Z
        "%Y-%m-%dT%H:%M:%S.%fZ",   # 2025-06-06T00:00:00.000Z
        "%Y-%m-%d",                 # 2025-06-06
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    logger.warning(f"无法解析日期格式: {date_str}")
    return None


class AIIDCollector:
    """AIID数据采集器 - 从CSV快照文件获取数据"""

    # 快照页面URL
    SNAPSHOT_URL = "https://incidentdatabase.ai/research/snapshots/"

    # 下载基础URL
    DOWNLOAD_BASE_URL = "https://incidentdatabase.ai"

    # 备用直接下载链接（用于页面无法访问时的降级方案）
    FALLBACK_SNAPSHOT_URL = "https://incidentdatabase.ai/research/1.0/csv.tar.bz2"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LLM-Security-Alert-System/1.0"
        })
        # 确保temp目录存在
        os.makedirs(AIID_TEMP_DIR, exist_ok=True)
        logger.info(f"AIID临时目录: {AIID_TEMP_DIR}")

    def fetch_latest_snapshot_url(self) -> Optional[str]:
        """
        访问快照页面，解析HTML获取最新下载链接

        Returns:
            最新CSV文件的下载URL，失败时返回None
        """
        try:
            logger.info(f"正在访问快照页面: {self.SNAPSHOT_URL}")
            response = self.session.get(self.SNAPSHOT_URL, timeout=60)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # 查找所有.tar.bz2下载链接
            links = soup.find_all('a', href=re.compile(r'\.tar\.bz2$'))

            if not links:
                logger.warning("未找到.tar.bz2下载链接")
                return None

            # 获取最新的下载链接（通常页面中第一个或最后一个）
            latest_link = links[0].get('href')

            if not latest_link.startswith('http'):
                latest_link = self.DOWNLOAD_BASE_URL + latest_link

            logger.info(f"找到最新快照: {latest_link}")
            return latest_link

        except requests.exceptions.RequestException as e:
            logger.error(f"获取快照页面失败: {e}")
            logger.info(f"使用备用快照URL: {self.FALLBACK_SNAPSHOT_URL}")
            return self.FALLBACK_SNAPSHOT_URL
        except Exception as e:
            logger.error(f"解析快照页面时出错: {e}")
            logger.info(f"使用备用快照URL: {self.FALLBACK_SNAPSHOT_URL}")
            return self.FALLBACK_SNAPSHOT_URL

    def download_and_extract(self, url: str) -> Optional[str]:
        """
        下载.tar.bz2压缩包并解压，获取CSV文件路径

        Args:
            url: 压缩包下载URL

        Returns:
            解压后CSV文件路径，失败时返回None
        """
        try:
            # 使用时间戳命名本次下载的文件夹
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sub_dir = os.path.join(AIID_TEMP_DIR, timestamp)
            os.makedirs(sub_dir, exist_ok=True)

            download_path = os.path.join(sub_dir, "snapshot.tar.bz2")

            # 下载文件
            logger.info(f"正在下载快照文件: {url}")
            response = self.session.get(url, timeout=600)  # 10分钟超时
            response.raise_for_status()

            with open(download_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"下载完成，文件大小: {os.path.getsize(download_path)} bytes")

            # 解压.tar.bz2文件
            logger.info("正在解压文件...")
            with tarfile.open(download_path, 'r:bz2') as tar:
                tar.extractall(sub_dir)

            # 查找CSV文件 - 优先查找reports.csv
            csv_path = None

            # 首先查找reports.csv
            for root, dirs, files in os.walk(sub_dir):
                for file in files:
                    if file == 'reports.csv':
                        csv_path = os.path.join(root, file)
                        logger.info(f"找到reports.csv: {csv_path}")
                        break
                if csv_path:
                    break

            # 如果没找到reports.csv，查找其他CSV文件作为降级方案
            if not csv_path:
                for root, dirs, files in os.walk(sub_dir):
                    for file in files:
                        if file.endswith('.csv'):
                            csv_path = os.path.join(root, file)
                            logger.info(f"找到CSV文件: {csv_path}")
                            break
                    if csv_path:
                        break

            if not csv_path:
                logger.error("解压后未找到CSV文件")
                return None

            # 将CSV路径和临时目录保存，供后续清理使用
            self._last_download_dir = sub_dir
            self._last_csv_path = csv_path

            return csv_path

        except requests.exceptions.RequestException as e:
            logger.error(f"下载快照文件失败: {e}")
            return None
        except tarfile.TarError as e:
            logger.error(f"解压文件失败: {e}")
            return None
        except Exception as e:
            logger.error(f"处理快照文件时出错: {e}")
            return None

    def read_csv_data(self, csv_path: str) -> List[Dict]:
        """
        读取CSV文件并解析事件数据

        Args:
            csv_path: CSV文件路径

        Returns:
            事件列表
        """
        events = []
        try:
            logger.info(f"正在读取CSV文件: {csv_path}")

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append(row)

            logger.info(f"成功读取 {len(events)} 条记录")
            return events

        except Exception as e:
            logger.error(f"读取CSV文件失败: {e}")
            return []

    def parse_incident(self, row: Dict) -> Optional[Dict]:
        """
        解析单条CSV记录为统一格式

        Args:
            row: CSV行数据

        Returns:
            解析后的数据字典，如果解析失败则返回None
        """
        try:
            # 获取必要字段
            report_number = row.get('report_number', '')
            title = row.get('title', '')
            description = row.get('text', '') or row.get('description', '')
            source_url = row.get('url', '')
            date_published = row.get('date_published', '')
            date_submitted = row.get('date_submitted', '')
            # 获取作者字段（AIID CSV中使用authors字段）
            authors = row.get('authors', '') or row.get('author', '')

            if not report_number:
                logger.warning("记录缺少report_number，跳过")
                return None

            # 过滤掉author为空的事件，保留有作者的事件
            if not authors or not authors.strip():
                logger.debug(f"记录 {report_number} 缺少author，跳过")
                return None

            # 使用report_number作为唯一标识
            external_id = f"AIID-{report_number}"

            # 优先使用发布日期，转换为datetime对象
            publish_date_str = date_published or date_submitted or ''
            publish_date = parse_iso_date(publish_date_str)

            return {
                "source_type": "aiid",
                "source_name": "AIID",
                "title": title or f"AI事件 {report_number}",
                "description": description or title or f"AI事件 {report_number}",
                "original_url": source_url,
                "published_at": publish_date,
            }

        except Exception as e:
            logger.error(f"解析CSV记录时出错: {e}")
            return None

    def collect(self, limit: int = 0) -> List[Dict]:
        """
        主入口：采集并解析AIID数据

        Args:
            limit: 返回的最大事件数量，0表示不限制

        Returns:
            解析后的AIID数据列表
        """
        # 获取最新快照URL
        snapshot_url = self.fetch_latest_snapshot_url()
        if not snapshot_url:
            logger.error("无法获取AIID快照URL")
            return []

        # 下载并解压
        csv_path = self.download_and_extract(snapshot_url)
        if not csv_path:
            logger.error("无法下载或解压AIID快照")
            return []

        # 读取CSV数据
        raw_data = self.read_csv_data(csv_path)

        # 解析数据
        parsed_incidents = []
        for row in raw_data:
            parsed = self.parse_incident(row)
            if parsed:
                parsed_incidents.append(parsed)

        # 限制返回数量（保留最新的），limit=0表示不限制
        if limit > 0 and len(parsed_incidents) > limit:
            parsed_incidents = parsed_incidents[-limit:]

        logger.info(f"成功解析 {len(parsed_incidents)} 条AIID事件")

        # 清理旧的下载文件，只保留最新下载的那个用于下次更新比对
        self._cleanup_old_files()

        return parsed_incidents

    def _cleanup_old_files(self):
        """
        清理旧的下载文件，只保留最新下载的文件夹
        """
        if not hasattr(self, '_last_download_dir') or not self._last_download_dir:
            return

        try:
            # 获取temp目录下的所有子文件夹
            all_dirs = []
            if os.path.exists(AIID_TEMP_DIR):
                for item in os.listdir(AIID_TEMP_DIR):
                    item_path = os.path.join(AIID_TEMP_DIR, item)
                    if os.path.isdir(item_path):
                        all_dirs.append((item_path, os.path.getmtime(item_path)))

            if not all_dirs:
                return

            # 按修改时间排序，最新的排在最后
            all_dirs.sort(key=lambda x: x[1])

            # 只保留最新下载的文件夹，删除其他的
            latest_dir = self._last_download_dir

            for dir_path, _ in all_dirs:
                if dir_path != latest_dir and os.path.exists(dir_path):
                    logger.info(f"清理旧下载文件夹: {dir_path}")
                    shutil.rmtree(dir_path)

            logger.info("旧文件清理完成")

        except Exception as e:
            logger.error(f"清理旧文件时出错: {e}")


# 创建默认实例
aiid_collector = AIIDCollector()
