from flask import request
from flask_sqlalchemy import BaseQuery, Pagination
from psycopg2 import ProgrammingError
from psycopg2.extensions import cursor
from requests import codes

from quetzal.app.api.exceptions import APIException, ObjectNotFoundException


class CustomPagination(Pagination):
    """A specialization of flask_sqlalchemy pagination object

    This specialization adds a utility method to produce a dictionary that
    conforms to Quetzal's pagination specification.

    In addition to the original constructor parameters, this object takes a
    serializer method that converts whatever object type that the query from the
    paginate call generates and converts it to an object that must be JSON
    serializable. If not provided, the object is used as-is.

    """
    def __init__(self, *args, **kwargs):
        self.serializer = kwargs.pop('serializer') or (lambda x: x)
        super().__init__(*args, **kwargs)

    def response_object(self):
        return {
            'page': self.page,
            'pages': self.pages,
            'total': self.total,
            'results': [self.serializer(i) for i in self.items],
        }

    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        assert not isinstance(self.query, cursor) or cursor.scrollable, \
            'Cannot obtain previous page of a non-scrollable cursor'
        return paginate(self.query, page=self.page - 1, per_page=self.per_page, error_out=error_out)

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return paginate(self.query, page=self.page + 1, per_page=self.per_page, error_out=error_out)


def paginate(queriable, *, page=None, per_page=None, error_out=True, max_per_page=None, serializer=None):
    """Returns ``per_page`` items from page ``page``.

    This is a specialization of `flask_sqlalchemy.BaseQuery.paginate` with some
    custom modifications:

    * It changes the original behavior to respond throw `APIException` instead
      of calling `abort`. The status code has also been changed to 400 instead
      of 404. Normally, this errors should not be reachable since connexion
      handles the input validation.

    * In addition to handling regular `flask_sqlalchemy.BaseQuery` objects,
      it can also accept a cursor.

    * In addition to these changes, this function returns a custom pagination
      object that provides a `response_object` method that can build a response
      according to Quetzal's paginated response specification.

    * Uses keyword arguments to avoid incorrect arguments

    The original docstring is as follows:

    If ``page`` or ``per_page`` are ``None``, they will be retrieved from
    the request query. If ``max_per_page`` is specified, ``per_page`` will
    be limited to that value. If there is no request or they aren't in the
    query, they default to 1 and 20 respectively.

    When ``error_out`` is ``True`` (default), the following rules will
    cause a 404 response:

    * No items are found and ``page`` is not 1.
    * ``page`` is less than 1, or ``per_page`` is negative.
    * ``page`` or ``per_page`` are not ints.

    When ``error_out`` is ``False``, ``page`` and ``per_page`` default to
    1 and 20 respectively.

    Returns a :class:`CustomPagination` object.
    """

    # Fail early if the queriable object is not supported
    if not isinstance(queriable, (BaseQuery, cursor)):
        raise ValueError(f'Cannot paginate a {type(queriable)} object')

    if request:
        if page is None:
            try:
                page = int(request.args.get('page', 1))
            except (TypeError, ValueError):
                if error_out:
                    raise APIException(status=codes.bad_request,
                                       title='Invalid paging parameters',
                                       detail='page parameter must be an integer')

                page = 1

        if per_page is None:
            try:
                per_page = int(request.args.get('per_page', 20))
            except (TypeError, ValueError):
                if error_out:
                    raise APIException(status=codes.bad_request,
                                       title='Invalid paging parameters',
                                       detail='per_page parameter must be an integer')

                per_page = 20
    else:
        if page is None:
            page = 1

        if per_page is None:
            per_page = 20

    if max_per_page is not None:
        per_page = min(per_page, max_per_page)

    if page < 1:
        if error_out:
            raise APIException(status=codes.bad_request,
                               title='Invalid paging parameters',
                               detail='page parameter must be positive')
        else:
            page = 1

    if per_page < 0:
        if error_out:
            raise APIException(status=codes.bad_request,
                               title='Invalid paging parameters',
                               detail='per_page parameter must be positive')
        else:
            per_page = 20

    if isinstance(queriable, BaseQuery):
        items = queriable.limit(per_page).offset((page - 1) * per_page).all()
    else:
        try:
            queriable.scroll((page - 1) * per_page, mode='absolute')
            column_names = [desc[0] for desc in queriable.description]
            items = [dict(zip(column_names, row)) for row in queriable.fetchmany(per_page)]
        except ProgrammingError:
            # Set the items to empty, an error is handled later
            items = []

    if not items and page != 1 and error_out:
        raise ObjectNotFoundException(status=codes.not_found,
                                      title='Not found',
                                      detail='Page request is out of range of results')

    # No need to count if we're on the first page and there are fewer
    # items than we expected.
    if page == 1 and len(items) < per_page:
        total = len(items)
    else:
        if isinstance(queriable, BaseQuery):
            total = queriable.order_by(None).count()
        else:
            total = queriable.rowcount

    return CustomPagination(queriable, page, per_page, total, items, serializer=serializer)
