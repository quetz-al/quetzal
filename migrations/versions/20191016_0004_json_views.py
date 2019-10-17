"""add postgresql_json to dialects enum

Revision ID: 0004
Revises: 0003
Create Date: 2019-10-16 17:11:15.652795

"""
# Adds a new
# Inspired from https://stackoverflow.com/a/14845740/227103

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


old_options = ('POSTGRESQL',)
new_options = sorted(old_options + ('POSTGRESQL_JSON',))

old_type = sa.Enum(*old_options, name='querydialect')
new_type = sa.Enum(*new_options, name='querydialect')
tmp_type = sa.Enum(*new_options, name='_querydialect')

tab = sa.sql.table('metadata_query',
                   sa.Column('dialect', new_type, nullable=False))


def upgrade():
    # Create a temporary "_status" type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE metadata_query ALTER COLUMN dialect TYPE _querydialect'
               ' USING dialect::text::_querydialect')
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" dialect type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE metadata_query ALTER COLUMN dialect TYPE querydialect'
               ' USING dialect::text::querydialect')
    tmp_type.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # Convert 'postgresql_json' dialect into 'postgresql'
    op.execute(tab.update().where(tab.c.dialect == u'postgresql_json')
               .values(dialect='postgresql'))
    # Create a tempoary "_dialect" type, convert and drop the "new" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE metadata_query ALTER COLUMN dialect TYPE _querydialect'
               ' USING dialect::text::_querydialect')
    new_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "old" dialect type
    old_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE metadata_query ALTER COLUMN dialect TYPE querydialect'
               ' USING dialect::text::querydialect')
    tmp_type.drop(op.get_bind(), checkfirst=False)
