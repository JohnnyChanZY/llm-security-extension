"""add cvss fields and update severity enum

Revision ID: 004_cvss_fields
Revises: 003_keyword_filter
Create Date: 2026-03-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_cvss_fields'
down_revision: Union[str, None] = '003_keyword_filter'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cvss_score column to historical_events
    op.add_column(
        'historical_events',
        sa.Column(
            'cvss_score',
            sa.Float(),
            nullable=True,
            comment='CVSS 4.0基础分数'
        )
    )

    # Add cvss_vector column to historical_events
    op.add_column(
        'historical_events',
        sa.Column(
            'cvss_vector',
            sa.String(200),
            nullable=True,
            comment='CVSS 4.0向量字符串'
        )
    )

    # Add cvss_score column to rss_events
    op.add_column(
        'rss_events',
        sa.Column(
            'cvss_score',
            sa.Float(),
            nullable=True,
            comment='CVSS 4.0基础分数'
        )
    )

    # Add cvss_vector column to rss_events
    op.add_column(
        'rss_events',
        sa.Column(
            'cvss_vector',
            sa.String(200),
            nullable=True,
            comment='CVSS 4.0向量字符串'
        )
    )

    # Modify severity enum to include 'none' value
    # For MySQL, we need to modify the enum type
    # First alter historical_events
    op.execute("""
        ALTER TABLE historical_events
        MODIFY COLUMN severity ENUM('none', 'low', 'medium', 'high', 'critical')
        COMMENT '安全等级'
    """)

    # Then alter rss_events
    op.execute("""
        ALTER TABLE rss_events
        MODIFY COLUMN severity ENUM('none', 'low', 'medium', 'high', 'critical')
        COMMENT '安全等级'
    """)


def downgrade() -> None:
    # Remove cvss fields from rss_events
    op.drop_column('rss_events', 'cvss_vector')
    op.drop_column('rss_events', 'cvss_score')

    # Remove cvss fields from historical_events
    op.drop_column('historical_events', 'cvss_vector')
    op.drop_column('historical_events', 'cvss_score')

    # Revert severity enum (remove 'none')
    op.execute("""
        ALTER TABLE historical_events
        MODIFY COLUMN severity ENUM('low', 'medium', 'high', 'critical')
        COMMENT '安全等级'
    """)

    op.execute("""
        ALTER TABLE rss_events
        MODIFY COLUMN severity ENUM('low', 'medium', 'high', 'critical')
        COMMENT '安全等级'
    """)
