import logging
import pathlib
import urllib.parse

from flask import current_app

from quetzal.app.api.exceptions import QuetzalException


logger = logging.getLogger(__name__)


def upload(filename, content, location):
    """ Save a file on a local filesystem.

    Implements the *upload* mechanism of the local file storage backend.

    Parameters
    ----------
    filename: str
        Filename where the file will be saved. It can include a relative path.
    content: file-like
        Contents of the file.
    location: str
        URL where the file will be saved. The `filename` parameter will be
        relative to this parameter.

    Returns
    -------
    url: str
        URL to the uploaded file. Its format will be ``file://absolute/path/to/file``.
    path_obj: :py:class:`pathlib.Path`
        Path object where the file was saved.

    Raises
    ------
    quetzal.app.api.exceptions.QuetzalException
        When the location is the global data directory. This is not permitted.

    """
    logger.debug('Saving local file %s at %s', filename, location)

    # Verification that the upload does not change the global data directory
    data_dir = pathlib.Path(current_app.config['QUETZAL_FILE_DATA_DIR']).resolve()
    target_dir = pathlib.Path(urllib.parse.urlparse(location).path).resolve()
    if str(target_dir).startswith(str(data_dir)):
        raise QuetzalException('Cannot upload directly to global data directory')

    # Rewind the file descriptor to the beginning of file in case there was a
    # read operation before
    content.seek(0)

    # Create target directory if needed
    target_path = target_dir / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    filename = str(target_path.resolve())

    # Save the contents
    content.save(filename)

    return f'file://{filename}', target_path
