from flask import current_app

from quetzal.app.api.exceptions import QuetzalException
from quetzal.app.api.data.storage import gcp, local


def upload(filename, contents, location):
    backend = current_app.config['QUETZAL_DATA_STORAGE']
    if backend == 'file':
        return local.upload(filename, contents, location)
    elif backend == 'GCP':
        return gcp.upload(filename, contents, location)
    else:
        raise QuetzalException(f'Unknown storage backend "{backend}"')


def set_permissions(file_obj, owner):
    pass
