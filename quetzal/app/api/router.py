"""
Router controller to let Connexion link OAS operation ids to custom functions.

On a OpenAPI specification, operationIds can be as specific as:
``app.api.data.workspace.create``. However, other clients may use this long
name, which generates functions with long names. Moreover, the real use-case of
operationId is to provide a unique identifier to each operation.

To simplify the client code, we use Connexion's vendor-specific tag
``x-openapi-router-controller`` to provide a class to associate operations to
Python functions. Following Connexion's implementation, the resolved name is
``controller.operationId`` where ``controller`` is the value of the
``x-openapi-router-controller`` tag.

This Python function provides the functions and associations to use the
``x-openapi-router-controller`` tag and simplify the specification code.

"""

from . import auth as _auth
from . import data as _data


class AuthRouter:
    """Router for authentication operations.

    Use as::

        operationId: auth.func
        x-openapi-router-controller: app.api.router

    Where ``func`` is a member of this class.
    """
    get_token = _auth.get_token
    logout = _auth.logout


class WorkspaceRouter:
    """Router for workspace operations.

    Use as::

        operationId: workspace.func
        x-openapi-router-controller: app.api.router

    Where ``func`` is a member of this class.
    """
    commit = _data.workspace.commit
    create = _data.workspace.create
    delete = _data.workspace.delete
    details = _data.workspace.details
    fetch = _data.workspace.fetch
    scan = _data.workspace.scan


class WorkspaceFilesRouter:
    """Router for operations on files inside a workspace.

    Use as::

        operationId: workspace_file.func
        x-openapi-router-controller: app.api.router

    Where ``func`` is a member of this class.
    """
    create = _data.file.create
    details = _data.file.details_w
    fetch = _data.file.fetch_w
    set_metadata = _data.file.set_metadata
    update_metadata = _data.file.update_metadata


class WorkspaceQueryRouter:
    """Router for operations on queries inside a workspace.

    Use as::

        operationId: workspace_query.func
        x-openapi-router-controller: app.api.router

    Where ``func`` is a member of this class.
    """
    create = _data.query.create
    fetch = _data.query.fetch
    details = _data.query.details


class PublicRouter:
    """Router for operations on public resources.

    Use as::

        operationId: public.func
        x-openapi-router-controller: app.api.router

    Where ``func`` is a member of this class.
    """
    file_details = _data.file.details
    file_fetch = _data.file.fetch


# Synonyms needed for easier/more-readable operationIds
auth = AuthRouter
workspace = WorkspaceRouter
workspace_file = WorkspaceFilesRouter
workspace_query = WorkspaceQueryRouter
public = PublicRouter
