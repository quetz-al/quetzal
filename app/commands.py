from app import db
from app.models import User


def new_user(username, email, password):
    user = User(username=username, email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

