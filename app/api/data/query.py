import logging

from flask import current_app, url_for
from requests import codes
import sqlparse

from app import db
from app.api.exceptions import APIException
from app.models import MetadataQuery, QueryDialect, Workspace


logger = logging.getLogger(__name__)


def fetch(*, wid, user, token_info=None):
    return {}, 200


def create(*, wid, body, user, token_info=None):

    workspace = Workspace.get_or_404(wid)
    # TODO: check state

    code = sqlparse.format(body['query'], strip_comments=True, reindent=True, keyword_case='upper')

    query = MetadataQuery.get_or_create(dialect=QueryDialect(body['dialect']),
                                        code=code,
                                        workspace=workspace,
                                        owner=user)
    db.session.add(query)
    db.session.commit()

    response_headers = {
        'Location': url_for('.app_api_data_query_details',
                            id=workspace.id, query_id=query.id)
    }

    return query.to_dict(), codes.moved_permanently, response_headers


def details(*, wid, qid, user, token_info=None):

    workspace = Workspace.get_or_404(wid)
    query = MetadataQuery.get_or_404(qid)
    if query.workspace != workspace:
        raise APIException(status=codes.not_found,
                           title='MetadataQuery not found',
                           detail=f'MetadataQuery {qid} was not found on workspace {wid}')

    if workspace.pg_schema_name is None:
        raise APIException(status=codes.precondition_failed,
                           title='Cannot query an unscanned workspace',
                           detail='Queries need a workspace that has been correctly scanned')

    engine = db.get_engine(app=current_app, bind='read_only_bind')
    conn = engine.raw_connection()
    with conn.cursor() as cursor:
        cursor.execute(f'SET SEARCH_PATH TO {workspace.pg_schema_name}')
        cursor.execute(query.code)
        column_names = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(column_names, row)))

        return query.to_dict(results), codes.ok


