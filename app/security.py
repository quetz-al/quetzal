from app.models import User


def check_basic(username, password, required_scopes=None):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None
    return {
        # I don't know if this is a OAS3 specification or a zalando/connexion
        # implementation-specific element, but the user must be saved under the
        # 'sub' key in order to be propagated into the secured functions
        'sub': user,
        'scope': '',
    }


def check_bearer(token):
    user = User.check_token(token)
    if user is None:
        return None
    return {
        'sub': user,
        'scope': '',
    }


def load_roles(user):
    pass
