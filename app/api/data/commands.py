import logging
from urllib.parse import urlparse

from flask import current_app

from .helpers import get_client

logger = logging.getLogger(__name__)


class CommandException(Exception):
    pass


def init_buckets():
    """ Initialize data buckets """
    data_bucket = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    logger.info('Creating bucket %s', data_bucket)

    client = get_client()
    bucket_name = urlparse(data_bucket).netloc
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        raise CommandException(f'Cannot create bucket {bucket_name}: already exists')

    bucket.storage_class = 'REGIONAL'
    bucket.location = 'europe-west1'
    bucket.create()

    logger.info('Bucket created %s successfully!', bucket.name)
