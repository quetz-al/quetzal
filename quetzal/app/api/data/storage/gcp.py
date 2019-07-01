import logging

from flask import current_app

from quetzal.app.api.exceptions import QuetzalException
from quetzal.app.helpers.google_api import get_bucket


logger = logging.getLogger(__name__)


def upload(filename, content, location):
    """ Save a file on a local filesystem.

    Implements the *upload* mechanism of the GCP backend.

    Parameters
    ----------
    filename: str
        Filename where the file will be saved. It can include a relative path.
    content: file-like
        Contents of the file.
    location: str
        URL of the bucket the file will be saved. The `filename` parameter will
        be relative to this parameter.

    Returns
    -------
    url: str
        URL to the uploaded file. Its format will be ``gs://url/to/file``.
    blob_obj: :py:class:`google.cloud.storage.blob.Blob`
        Blob object where the file was saved.

    Raises
    ------
    quetzal.app.api.exceptions.QuetzalException
        When the location is the global data bucket. This is not permitted.

    """
    logger.debug('Saving GCP file %s at %s', filename, location)

    # Verification that the upload does not change the global data directory
    data_bucket_url = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    if location.startswith(data_bucket_url):
        raise QuetzalException('Cannot upload directly to global data bucket')

    # No rewind needed: this is handled by upload_from_file
    # No target directory creation needed: there are no directories in GCP, they
    # are coded into the file name.
    target_bucket = get_bucket(location)
    blob = target_bucket.blob(filename)
    blob.upload_from_file(content, rewind=True)
    return f'gs://{target_bucket.name}/{blob.name}', blob
