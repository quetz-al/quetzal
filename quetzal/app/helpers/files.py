import hashlib
import os


def split_check_path(filepath):
    filepath = os.path.normpath('/' + filepath).lstrip('/')  # Protect against traversal
    return os.path.split(filepath)


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
