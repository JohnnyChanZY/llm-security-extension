"""add keyword filter fields to rss_events

Revision ID: 003_keyword_filter
Revises: 002_security_event
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_keyword_filter'
down_revision: Union[str, None] = '002_security_event'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_keyword_filtered column to rss_events
    op.add_column(
        'rss_events',
        sa.Column(
            'is_keyword_filtered',
            sa.Boolean(),
            nullable=True,
            default=False,
            comment='是否已进行关键词筛选'
        )
    )

    # Add keyword_filter_passed column to rss_events
    op.add_column(
        'rss_events',
        sa.Column(
            'keyword_filter_passed',
            sa.Boolean(),
            nullable=True,
            comment='关键词筛选是否通过(NULL=未筛选)'
        )
    )

    # 为现有数据设置默认值（视为通过筛选）
    op.execute("""
        UPDATE rss_events
        SET is_keyword_filtered = TRUE, keyword_filter_passed = TRUE
        WHERE is_keyword_filtered IS NULL OR is_keyword_filtered = FALSE
    """)


def downgrade() -> None:
    op.drop_column('rss_events', 'keyword_filter_passed')
    op.drop_column('rss_events', 'is_keyword_filtered')
