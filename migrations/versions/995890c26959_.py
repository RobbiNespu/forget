"""empty message

Revision ID: 995890c26959
Revises: e036b007017c
Create Date: 2017-08-01 23:24:22.223674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '995890c26959'
down_revision = 'e036b007017c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('accounts', sa.Column('policy_keep_favourites', sa.Boolean(), server_default='TRUE', nullable=True))
    op.drop_column('accounts', 'policy_ignore_favourites')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('accounts', sa.Column('policy_ignore_favourites', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True))
    op.drop_column('accounts', 'policy_keep_favourites')
    # ### end Alembic commands ###
