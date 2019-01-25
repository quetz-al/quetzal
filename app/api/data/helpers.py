import hashlib
import logging
import os
from urllib.parse import urlparse

from google.cloud import storage
from flask import current_app, g


logger = logging.getLogger(__name__)


def get_client():
    """Create a GCP client built from the app configuration

    The client is saved in the currrent application context and will be reused
    in any future call on this context.
    """
    # Get a client and save it in the context so it can be reused
    if 'google_client' not in g:
        filename = current_app.config['QUETZAL_GCP_CREDENTIALS']
        g.google_client = storage.Client.from_service_account_json(filename)
    return g.google_client


def get_bucket(url, *, client=None):
    """ Get a GCP bucket object from an URL

    Parameters
    ----------
    url: str
        URL of the bucket

    client: google.storage.client.Client, optional
        GCP client instance to use. If not set it uses :py:func:`get_client`.

    Returns
    -------
    bucket: google.storage.bucket.Bucket
        A bucket instance

    """
    if client is None:
        client = get_client()
    bucket_name = urlparse(url).netloc
    return client.get_bucket(bucket_name)


def get_object(url, *, client=None):
    if client is None:
        client = get_client()
    blob_name = urlparse(url).path.lstrip('/')
    bucket = get_bucket(url, client=client)
    return bucket.get_blob(blob_name, client=client)


def get_data_bucket(*, client=None):
    """ Get Quetzal's data bucket

    Parameters
    ----------
    client: google.storage.client.Client, optional
        GCP client instance to use. If not set it uses :py:func:`get_client`.

    Returns
    -------
    bucket: google.storage.bucket.Bucket
        A bucket instance

    """
    data_bucket_url = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    return get_bucket(data_bucket_url, client=client)


def get_readable_info(file_obj):
    """ Extract useful information from reading a file

    This function calculates the md5sum and the file size in bytes from a
    file-like object. It does both operations at the same time, which means
    that there is no need to read the object twice.

    After this function reads the file content, it will set the file pointer
    to its original position through `tell`.

    Parameters
    ----------
    file_obj: file-like
        File object. It needs the `read` and `tell` methods.

    Returns
    -------
    md5sum, size: str, int
        MD5 sum and size of the file object contents

    """
    info = dict()
    size = 0
    position = file_obj.tell()
    hashobj = hashlib.new('md5')
    while True:
        chunk = file_obj.read(4096)
        size += len(chunk)
        if not chunk:
            break
        hashobj.update(chunk)
    file_obj.seek(position)
    return hashobj.hexdigest(), size


def split_check_path(filepath):
    filepath = os.path.normpath('/' + filepath).lstrip('/')  # Protect against traversal
    return os.path.split(filepath)


def log_task(task, level=logging.INFO, limit=10):
    """Log the ids of a task or chain of tasks in celery"""
    ids = []
    while task is not None and len(ids) < limit:
        ids.append(str(task.id))
        if hasattr(task, 'parent'):
            task = task.parent
        else:
            task = None
    # Reverse the order because celery orders it backwards (to my understanding)
    ids = ids[::-1]
    if len(ids) == limit and task is not None:
        ids.append('...')
    logger.log(level, 'Task chain: %s', ' -> '.join(ids))


def print_query(qs):
    # Only for debugging purposes!
    from sqlalchemy.dialects import postgresql
    print(qs.statement.compile(dialect=postgresql.dialect()))
    return qs
