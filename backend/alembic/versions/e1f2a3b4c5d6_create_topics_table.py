"""create topics table (阶段3收尾：话题)

Revision ID: e1f2a3b4c5d6
Revises: c4d5e6f7a8b9
Create Date: 2026-08-20 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('topics',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('community_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('creator_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_id', 'name', name='uq_topic_community_name')
    )
    op.create_index(op.f('ix_topics_community_id'), 'topics', ['community_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_topics_community_id'), table_name='topics')
    op.drop_table('topics')
    # ### end Alembic commands ###
