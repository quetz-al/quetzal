from app import db
from app.models import User

# TODO: scope management


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
    user = User.query.filter_by(token=token).first()
    if user is None or not user.check_token(token):
        return None
    return {
        'sub': user,
        'scope': '',
    }


def get_token(*, user):
    token = user.get_token()
    db.session.commit()
    return {'token': token}
