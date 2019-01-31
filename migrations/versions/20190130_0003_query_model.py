"""query model

Revision ID: 0003
Revises: 0002
Create Date: 2019-01-30 17:46:42.311005

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('query',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dialect', sa.Enum('POSTGRESQL', name='querydialect'), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('fk_workspace_id', sa.Integer(), nullable=True),
    sa.Column('fk_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['fk_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['fk_workspace_id'], ['workspace.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key('workspace_fk_last_metadata_id', 'workspace', 'metadata', ['fk_last_metadata_id'], ['id'], use_alter=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('workspace_fk_last_metadata_id', 'workspace', type_='foreignkey')
    op.drop_table('query')
    # ### end Alembic commands ###