from requests import codes

from app import db


def get_token(*, user):
    token = user.get_token()
    db.session.commit()
    return {'token': token}, codes.ok


def logout(*, user):
    user.revoke_token()
    db.session.commit()
    return None, codes.no_content
