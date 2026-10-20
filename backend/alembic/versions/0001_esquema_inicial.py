from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clients',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('modules', sa.JSON(), nullable=False),
    sa.Column('base_fields', sa.JSON(), nullable=False),
    sa.Column('theme', sa.JSON(), nullable=False),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('settings',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('brands',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('fields', sa.JSON(), nullable=False),
    sa.Column('pipeline', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('brands', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_brands_client_id'), ['client_id'], unique=False)

    op.create_table('projects',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('unity_project_id', sa.String(length=64), nullable=True),
    sa.Column('archived', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'name', name='uq_project_client_name')
    )
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_client_id'), ['client_id'], unique=False)

    op.create_table('roles',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('statements', sa.JSON(), nullable=False),
    sa.Column('builtin', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_roles_client_id'), ['client_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=32), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('is_super_admin', sa.Boolean(), nullable=False),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_client_id'), ['client_id'], unique=False)

    op.create_table('products',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('stage', sa.String(length=200), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('brand_id', sa.String(length=32), nullable=True),
    sa.Column('parent_id', sa.String(length=32), nullable=True),
    sa.Column('retexture_prompt', sa.Text(), nullable=True),
    sa.Column('task_id', sa.String(length=80), nullable=True),
    sa.Column('endpoint', sa.String(length=80), nullable=True),
    sa.Column('credits', sa.Float(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=False),
    sa.Column('photos', sa.JSON(), nullable=False),
    sa.Column('raw_files', sa.JSON(), nullable=False),
    sa.Column('textures', sa.JSON(), nullable=False),
    sa.Column('thumbnail_url', sa.Text(), nullable=True),
    sa.Column('metrics', sa.JSON(), nullable=True),
    sa.Column('original_filename', sa.String(length=255), nullable=True),
    sa.Column('created_by_id', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['parent_id'], ['products.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index('ix_products_client_created', ['client_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_client_id'), ['client_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_status'), ['status'], unique=False)

    op.create_table('user_roles',
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('role_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    op.create_table('product_projects',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('project_id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', 'project_id')
    )


def downgrade() -> None:
    op.drop_table('product_projects')
    op.drop_table('user_roles')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_products_status'))
        batch_op.drop_index(batch_op.f('ix_products_client_id'))
        batch_op.drop_index('ix_products_client_created')

    op.drop_table('products')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_client_id'))

    op.drop_table('users')
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_roles_client_id'))

    op.drop_table('roles')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_client_id'))

    op.drop_table('projects')
    with op.batch_alter_table('brands', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_brands_client_id'))

    op.drop_table('brands')
    op.drop_table('settings')
    op.drop_table('clients')
