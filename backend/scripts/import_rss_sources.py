"""
批量导入RSS源脚本
从Markdown表格文件导入RSS源到数据库
"""
import sys
import os
import re

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.rss_source import RSSSource


# 要导入的RSS源列表（从Markdown表格解析）
RSS_SOURCES = [
    {"name": "安全客", "rss_url": "https://api.anquanke.com/data/v1/rss", "source_type": "other"},
    {"name": "Seebug Paper", "rss_url": "https://paper.seebug.org/rss", "source_type": "other"},
    {"name": "嘶吼", "rss_url": "https://www.4hou.com/feed", "source_type": "other"},
    {"name": "腾讯玄武实验室", "rss_url": "https://xlab.tencent.com/cn/atom.xml", "source_type": "other"},
    {"name": "SecWiki News", "rss_url": "https://www.sec-wiki.com/news/rss", "source_type": "other"},
    {"name": "信息安全知识库", "rss_url": "https://vipread.com/feed", "source_type": "other"},
    {"name": "美团技术团队", "rss_url": "https://tech.meituan.com/feed", "source_type": "other"},
    {"name": "华为安全通告", "rss_url": "https://www.huawei.com/cn/rss-feeds/psirt/rss", "source_type": "other"},
    {"name": "腾讯科恩实验室", "rss_url": "https://keenlab.tencent.com/zh/atom.xml", "source_type": "other"},
    {"name": "360 Netlab Blog", "rss_url": "https://blog.netlab.360.com/rss", "source_type": "other"},
    {"name": "斗象能力中心", "rss_url": "https://blog.riskivy.com/feed", "source_type": "other"},
    {"name": "腾讯安全响应中心", "rss_url": "https://security.tencent.com/index.php/feed/blog/0", "source_type": "other"},
    {"name": "Seebug漏洞社区", "rss_url": "https://www.seebug.org/rss/new", "source_type": "other"},
    {"name": "NOSEC漏洞预警", "rss_url": "https://rsshub.zhengjim.com/nosec/hole", "source_type": "other"},
]


def import_rss_sources(db: Session, sources: list):
    """
    导入RSS源到数据库

    Args:
        db: 数据库会话
        sources: RSS源列表，每个元素是包含name和rss_url的字典
    """
    added_count = 0
    skipped_count = 0

    for source_data in sources:
        # 检查是否已存在（根据rss_url）
        existing = db.query(RSSSource).filter(
            RSSSource.rss_url == source_data["rss_url"]
        ).first()

        if existing:
            print(f"  [跳过] {source_data['name']} - RSS链接已存在")
            skipped_count += 1
            continue

        # 创建新的RSS源
        rss_source = RSSSource(
            name=source_data["name"],
            rss_url=source_data["rss_url"],
            source_type=source_data.get("source_type", "other"),
            is_active=True,
            crawl_interval=60
        )
        db.add(rss_source)
        print(f"  [添加] {source_data['name']}")
        added_count += 1

    return added_count, skipped_count


def main():
    """主函数"""
    print("=" * 50)
    print("批量导入RSS源")
    print("=" * 50)

    db = SessionLocal()
    try:
        added, skipped = import_rss_sources(db, RSS_SOURCES)
        db.commit()
        print("\n" + "=" * 50)
        print(f"导入完成！新增: {added}, 跳过: {skipped}")
        print("=" * 50)
    except Exception as e:
        print(f"\n导入失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
