import io

from app.helpers.files import get_readable_info


def test_readable_info():
    # A simple example of a known MD5 value
    buffer = io.BytesIO(b'hello world')
    md5, size = get_readable_info(buffer)
    assert md5 == '5eb63bbbe01eeed093cb22bb8f5acdc3'
    assert size == 11
