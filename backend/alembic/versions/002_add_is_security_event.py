"""add is_security_event field

Revision ID: 002_security_event
Revises: 001_initial
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_security_event'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_security_event column to historical_events
    op.add_column(
        'historical_events',
        sa.Column(
            'is_security_event',
            sa.Boolean(),
            nullable=True,
            comment='是否为安全事件(None=未判断)'
        )
    )

    # Add is_security_event column to rss_events
    op.add_column(
        'rss_events',
        sa.Column(
            'is_security_event',
            sa.Boolean(),
            nullable=True,
            comment='是否为安全事件(None=未判断)'
        )
    )


def downgrade() -> None:
    op.drop_column('historical_events', 'is_security_event')
    op.drop_column('rss_events', 'is_security_event')
