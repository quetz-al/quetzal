# TODO: this is just a minimal auth structure. Do the real thing!


def basic_auth(username, password, required_scopes=None):
    if username == 'admin' and password == 'secret':
        return {'sub': 'admin', 'scope': ''}
    return None
