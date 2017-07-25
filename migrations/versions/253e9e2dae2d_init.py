"""init

Revision ID: 253e9e2dae2d
Revises: 
Create Date: 2017-07-25 09:50:45.374362

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '253e9e2dae2d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('display_name', sa.String(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_table('account',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('remote_id', sa.String(), nullable=False),
    sa.Column('service', sa.Enum('twitter', name='enum_services'), nullable=False),
    sa.Column('credentials', sa.JSON(), nullable=True),
    sa.Column('policy_enabled', sa.Boolean(), nullable=True),
    sa.Column('policy_keep_younger', sa.Interval(), nullable=True),
    sa.Column('policy_keep_latest', sa.Integer(), nullable=True),
    sa.Column('policy_delete_every', sa.Interval(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_account_user_id_users')),
    sa.PrimaryKeyConstraint('remote_id', 'service', name=op.f('pk_account'))
    )
    op.create_table('sessions',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('token', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users')),
    sa.PrimaryKeyConstraint('token', name=op.f('pk_sessions'))
    )


def downgrade():
    op.drop_table('sessions')
    op.drop_table('account')
    op.drop_table('users')
