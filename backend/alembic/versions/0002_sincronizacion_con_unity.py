from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('unity_syncs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('project_id', sa.String(length=32), nullable=False),
    sa.Column('unity_project_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('unity_asset_id', sa.String(length=64), nullable=True),
    sa.Column('unity_asset_version', sa.String(length=64), nullable=True),
    sa.Column('unity_dataset_id', sa.String(length=64), nullable=True),
    sa.Column('files_done', sa.JSON(), nullable=False),
    sa.Column('submitted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.Column('synced_at', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'project_id', name='uq_unity_product_project')
    )
    with op.batch_alter_table('unity_syncs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_unity_syncs_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_unity_syncs_project_id'), ['project_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('unity_syncs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_unity_syncs_project_id'))
        batch_op.drop_index(batch_op.f('ix_unity_syncs_product_id'))

    op.drop_table('unity_syncs')
