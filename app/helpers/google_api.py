import logging
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


