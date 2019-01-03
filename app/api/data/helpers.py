import hashlib
from urllib.parse import urlparse

from google.cloud import storage
from flask import current_app, g


def get_client():
    # Get a client and save it in the context so it can be reused
    if 'google_client' not in g:
        filename = current_app.config['QUETZAL_GCP_CREDENTIALS']
        g.google_client = storage.Client.from_service_account_json(filename)
    return g.google_client


def get_bucket(url, *, client=None):
    if client is None:
        client = get_client()
    bucket_name = urlparse(url).netloc
    return client.get_bucket(bucket_name)


def get_data_bucket(*, client=None):
    data_bucket_url = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    return get_bucket(data_bucket_url, client=client)


def md5(bs):
    assert type(bs) == bytes, 'Unexpected type for helper md5 function'
    hashobj = hashlib.new('md5')
    hashobj.update(bs)
    return hashobj.hexdigest()
