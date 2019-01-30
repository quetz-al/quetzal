import sqlparse
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.base import Executable
from sqlalchemy.sql.expression import ClauseElement


# Create a table from a query,
# inspired from https://stackoverflow.com/a/30577608/227103
class CreateTableAs(Executable, ClauseElement):

    def __init__(self, name, query):
        self.name = name
        self.query = query


@compiles(CreateTableAs, 'postgresql')
def _create_table_as(element, compiler, **kwargs):
    return 'CREATE TABLE %s AS %s' % (
        element.name,
        compiler.process(element.query)
    )


class DropSchemaIfExists(Executable, ClauseElement):

    def __init__(self, name, cascade=False):
        self.name = name
        self.cascade = cascade


@compiles(DropSchemaIfExists, 'postgresql')
def _drop_schema_if_exists(element, compiler, **kwargs):
    text = 'DROP SCHEMA IF EXISTS %s' % (
        element.name
    )
    if element.cascade:
        text += ' CASCADE'
    return text


class GrantUsageOnSchema(Executable, ClauseElement):

    def __init__(self, schema, user):
        self.schema = schema
        self.user = user


@compiles(GrantUsageOnSchema, 'postgresql')
def _grant_usage_on_schema(element, compiler, **kwargs):
    return 'GRANT USAGE ON SCHEMA %s TO %s' % (
        element.schema,
        element.user
    )


def print_sql(qs):
    # Only for debugging purposes!
    sql_text = str(qs.statement.compile(dialect=postgresql.dialect()))
    print(sqlparse.format(sql_text, reindent=True))
    return qs
