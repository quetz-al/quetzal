import logging

from connexion import request
from flask import current_app, url_for
from requests import codes
from psycopg2 import ProgrammingError
import sqlparse

from quetzal.app import db
from quetzal.app.api.exceptions import APIException
from quetzal.app.helpers.pagination import paginate
from quetzal.app.models import MetadataQuery, QueryDialect, Workspace
from quetzal.app.security import (
    ReadWorkspacePermission, WriteWorkspacePermission
)


logger = logging.getLogger(__name__)


def fetch(*, wid, user, token_info=None):

    workspace = Workspace.get_or_404(wid)

    if not ReadWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to query this workspace')

    pager = paginate(workspace.queries, serializer=MetadataQuery.to_dict)

    return pager.response_object(), 200


def create(*, wid, body, user, token_info=None):

    workspace = Workspace.get_or_404(wid)

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to query this workspace')

    # TODO: check state

    code = sqlparse.format(body['query'], strip_comments=True, reindent=True, keyword_case='upper')
    # TODO: it would be great to avoid this kind of query:
    # "select id from base; select filename from base" >> it has two queries!

    query = MetadataQuery.get_or_create(dialect=QueryDialect(body['dialect']),
                                        code=code,
                                        workspace=workspace,
                                        owner=user)
    db.session.add(query)
    db.session.commit()

    query_args = request.args
    url_for_kws = {}
    if 'per_page' in query_args:
        url_for_kws['per_page'] = query_args['per_page']
    if 'page' in query_args:
        url_for_kws['page'] = query_args['page']
    response_headers = {
        'Location': url_for('/api/v1.app_api_router_workspace_query_details',
                            wid=workspace.id, qid=query.id, **url_for_kws)
    }

    return query.to_dict(), codes.see_other, response_headers


def details(*, wid, qid, user, token_info=None):

    workspace = Workspace.get_or_404(wid)
    if not ReadWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to query this workspace')

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
        try:
            cursor.execute(query.code)
        except ProgrammingError as ex:
            # Log bad permission errors with warning; the user may be trying something fishy
            if ex.pgcode == '42501':
                logger.warning('User query failed due to permissions. Query %s was: %s',
                               query, query.code, exc_info=ex)
            else:
                logger.info('User query failed', exc_info=ex)
            raise APIException(status=codes.bad_request,
                               title='Query failed',
                               detail=f'Query could not be executed due to error:\n{ex!s}')

        pager = paginate(cursor)
        response = query.to_dict(pager.response_object())
        return response, codes.ok


