"""
HTML 清洗服务
用于清洗 RSS 事件描述中的 HTML 标签
"""
import re
from bs4 import BeautifulSoup


def clean_html(html_content: str) -> str:
    """
    清洗 HTML 内容，返回纯文本

    处理：
    - 移除所有 HTML 标签
    - 移除图片标签（不保留占位符）
    - 清理多余空白和换行

    Args:
        html_content: 包含 HTML 的原始内容

    Returns:
        清洗后的纯文本
    """
    if not html_content:
        return ""

    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(html_content, 'lxml')

    # 获取纯文本
    text = soup.get_text(separator=' ')

    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()

    return text
