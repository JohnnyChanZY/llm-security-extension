"""fix severity enum values

Revision ID: 005_fix_severity
Revises: 004_cvss_fields
Create Date: 2026-03-28

修复 SeverityLevel 和 SeveritySource 枚举值大小写问题：
- SQLAlchemy Enum 默认使用成员名 (MEDIUM) 而非值 ("medium")
- MySQL ENUM 列定义使用了大写值 ('NVD', 'LLM', 'MANUAL')
- 此迁移修改 MySQL ENUM 定义为小写值
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '005_fix_severity'
down_revision: Union[str, None] = '004_cvss_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """修改 ENUM 定义为小写值"""

    # 修改 historical_events 表的 severity_source 枚举定义
    op.execute("""
        ALTER TABLE historical_events
        MODIFY COLUMN severity_source ENUM('nvd', 'llm', 'manual') COMMENT '等级来源'
    """)

    # 修改 rss_events 表的 severity_source 枚举定义
    op.execute("""
        ALTER TABLE rss_events
        MODIFY COLUMN severity_source ENUM('nvd', 'llm', 'manual') COMMENT '等级来源'
    """)


def downgrade() -> None:
    """回滚：恢复大写 ENUM 定义"""

    # 恢复 historical_events 表的 severity_source 枚举定义
    op.execute("""
        ALTER TABLE historical_events
        MODIFY COLUMN severity_source ENUM('NVD', 'LLM', 'MANUAL') COMMENT '等级来源'
    """)

    # 恢复 rss_events 表的 severity_source 枚举定义
    op.execute("""
        ALTER TABLE rss_events
        MODIFY COLUMN severity_source ENUM('NVD', 'LLM', 'MANUAL') COMMENT '等级来源'
    """)
