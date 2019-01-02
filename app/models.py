from datetime import datetime, timedelta
import base64
import enum
import os

from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class WorkspaceState(enum.Enum):
    INITIALIZING = 1
    READY = 2
    PROCESSING = 3
    INVALID = 4
    CONFLICT = 5
    DELETED = 6


class Workspace(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False)
    state = db.Column(db.Enum(WorkspaceState), nullable=False, default=WorkspaceState.INITIALIZING)
    description = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.DateTime(timezone=True), server_default=func.now())
    temporary = db.Column(db.Boolean, nullable=False, default=False)
    data_url = db.Column(db.String(2048))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    families = db.relationship('Family', backref='workspace', lazy='dynamic')

    def __repr__(self):
        return f'<Workspace {self.id} [name="{self.name}" ' \
               f'state={self.state.name if self.state else "unset"}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state.name,
            'owner': self.owner.username,
            'description': self.description,
            'creation_date': self.creation_date,
            'temporary': self.temporary,
            'data_url': self.data_url,
        }


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(256), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)

    workspaces = db.relationship('Workspace', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_token(self, expires_in=3600):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user

    def __repr__(self):
        return f'<User {self.username}>'


class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), index=True, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)

    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    metadata_set = db.relationship('Metadata', backref='family', lazy='dynamic')

    def __repr__(self):
        return f'<Family {self.id} [{self.name}, version {self.version}]>'


class Metadata(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_file = db.Column(UUID(as_uuid=True), index=True, nullable=False)
    json = db.Column(JSONB, nullable=False)

    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)

    def __repr__(self):
        if self.family:
            return f'<Metadata {self.id} ' \
                   f'[{self.id_file} {self.family.name}:v{self.family.version}]>'
        return f'<Metadata {self.id} [{self.id_file} ...]>'
