from flask import current_app

from quetzal.app.api.exceptions import QuetzalException
from quetzal.app.api.data.storage import gcp, local


def upload(filename, contents, location):
    """ Upload a file

    Upload the `contents` as a file named `filename` in `location`.

    This function dispaches the upload operation on the configured storage
    backend.

    Parameters
    ----------
    filename: str
        Target file name where the contents will be saved.
    contents: file-like
        A buffer of bytes with the file contents.
    location: str
        URL of the target location where the file will be saved. This should be
        the URL of a workspace

    Returns
    -------
    url: str
        URL to where the file was uploaded.
    obj: object
        An object pointing where the file was uploaded for further manipulation.
        Its type depends on the data backend.

    Raises
    ------
    quetzal.app.api.exceptions.QuetzalException
        When the storage backend is unknown. Exceptions by the dispatched
        functions are not captured here.

    """
    backend = current_app.config['QUETZAL_DATA_STORAGE']
    if backend == 'file':
        return local.upload(filename, contents, location)
    elif backend == 'GCP':
        return gcp.upload(filename, contents, location)
    else:
        raise QuetzalException(f'Unknown storage backend "{backend}"')


def set_permissions(file_obj, owner):
    """ Set the permissions of the file

    Change the data object `file_obj` permissions to set `owner` as the user
    that owns this file.

    Parameters
    ----------
    file_obj: object
        Object pointing to a file, as returned by :py:func:`upload`.
    owner: quetzal.app.models.User
        User object that will own the file.

    Raises
    ------
    quetzal.app.api.exceptions.QuetzalException
        When the storage backend is unknown. Exceptions by the dispatched
        functions are not captured here.

    """
    backend = current_app.config['QUETZAL_DATA_STORAGE']
    if backend == 'file':
        return local.set_permissions(file_obj, owner)
    elif backend == 'GCP':
        return gcp.set_permissions(file_obj, owner)
    else:
        raise QuetzalException(f'Unknown storage backend "{backend}"')
