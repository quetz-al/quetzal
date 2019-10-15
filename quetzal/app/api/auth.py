from flask import current_app
from flask_principal import identity_changed, Identity
from requests import codes

from quetzal.app import db
from quetzal.app.models import ApiKey, User


def get_token(*, user):
    token = user.get_token()
    db.session.commit()
    return {'token': token}, codes.ok


def logout(*, user):
    user.revoke_token()
    db.session.commit()
    return None, codes.no_content


def check_basic(username, password, required_scopes=None):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None

    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id, 'basic'))
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

    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id, 'token'))
    return {
        'sub': user,
        'scope': '',
    }


def check_apikey(key, required_scopes=None):
    apikey = ApiKey.check_key(key)
    if apikey is None:
        return None
    user = apikey.user
    if user is None:
        return None
    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id, 'apikey'))
    return {
        'sub': user,
        'scope': '',
    }
