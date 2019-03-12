"""
Background tasks
"""

import base64
import binascii
import logging
import pathlib

from .helpers.google_api import get_bucket
from .helpers.files import get_readable_info


logger = logging.getLogger(__name__)


def hello():
    try:
        import socket
        hostname = socket.gethostname()
    except:
        hostname = None
    logger.info('Hello, %s is alive', hostname)


def backup_logs(app):
    with app.app_context():
        log_dir = pathlib.Path(app.config['LOG_DIR'])
        log_bucket_name = app.config['QUETZAL_GCP_BACKUP_BUCKET']
        logger.info('Backing up logs in %s to %s', log_dir.name, log_bucket_name)

        bucket = get_bucket(log_bucket_name)
        errors = []

        for log_file in log_dir.glob('*.log'):
            try:
                with open(log_dir / log_file, 'rb') as f:
                    md5, size = get_readable_info(f)
                    blob = bucket.get_blob('logs/' + log_file.name)
                    copy = None

                    if blob is not None:
                        if md5 == binascii.hexlify(base64.b64decode(blob.md5_hash)).decode('utf-8') and size == blob.size:
                            logger.info('Ignoring %s (already uploaded)', log_dir / log_file)
                            continue
                        # If blob exists, we need to rewrite it, but we cannot do this so
                        # let's move it and upload it
                        copy = bucket.blob(blob.name + '.bak')
                        logger.info('Moving %s -> %s', blob.name, copy.name)
                        copy.rewrite(blob)
                        blob.delete()

                    elif blob is None:
                        # Blob does not exist, create it
                        blob = bucket.blob('logs/' + log_file.name)

                    logger.info('Uploading %s -> %s',
                                log_file,
                                log_bucket_name + '/' + blob.name)
                    blob.upload_from_file(f, rewind=True)
                    if copy:
                        copy.delete()

            except Exception as ex:
                errors.append(ex)

        if errors:
            logger.error('Failed to backup %d log files: %s', len(errors), errors)
