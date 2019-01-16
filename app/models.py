from datetime import datetime, timedelta
import base64
import enum
import logging
import os

from flask_login import UserMixin
from requests import codes
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from sqlalchemy.schema import Index, UniqueConstraint, CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.api.exceptions import InvalidTransitionException, APIException


logger = logging.getLogger(__name__)


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

    def get_token(self, expires_in=3600):  # TODO: setting for timeout
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


class WorkspaceState(enum.Enum):
    INITIALIZING = 'initializing'
    READY = 'ready'
    SCANNING = 'scanning'
    UPDATING = 'updating'
    COMMITTING = 'committing'
    DELETING = 'deleting'
    INVALID = 'invalid'
    CONFLICT = 'conflict'
    DELETED = 'deleted'

    @staticmethod
    def transitions():
        """Get the valid transition table for workspace states"""
        ws = WorkspaceState  # synonym for shorter code
        return {
            None: {ws.INITIALIZING},
            ws.INITIALIZING: {ws.READY, ws.INVALID},
            ws.READY: {ws.SCANNING, ws.UPDATING, ws.COMMITTING, ws.DELETING},
            ws.SCANNING: {ws.READY},
            ws.UPDATING: {ws.READY, ws.INVALID},
            ws.COMMITTING: {ws.READY, ws.CONFLICT},
            ws.DELETING: {ws.DELETED},
            ws.INVALID: {ws.UPDATING, ws.DELETING},
            ws.CONFLICT: {ws.UPDATING, ws.DELETING},
            ws.DELETED: {},
        }

    @staticmethod
    def valid_transition(from_value, to_value):
        return to_value in WorkspaceState.transitions().get(from_value, {})


class Workspace(db.Model):

    __table_args__ = (
        UniqueConstraint('name', 'fk_user_id'),                 # Name and user should be unique together
        Index('ix_workspace_name_user', 'name', 'fk_user_id'),  # Index on user and name together
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False)
    _state = db.Column(db.Enum(WorkspaceState), nullable=True)
    description = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.DateTime(timezone=True), server_default=func.now())
    temporary = db.Column(db.Boolean, nullable=False, default=False)
    data_url = db.Column(db.String(2048))

    fk_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    fk_last_metadata_id = db.Column(db.Integer,
                                    db.ForeignKey('metadata.id', use_alter=True, name='workspace_fk_last_metadata_id'),
                                    nullable=True)

    families = db.relationship('Family', backref='workspace', lazy='dynamic')

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if WorkspaceState.valid_transition(self._state, new_state):
            self._state = new_state
        else:
            raise InvalidTransitionException(f'Invalid state transition '
                                             f'{self._state} -> {new_state}')

    @staticmethod
    def get_or_404(id):
        """Get a workspace by id or raise an APIException"""
        w = Workspace.query.get(id)
        if w is None:
            raise APIException(status=codes.not_found,
                               title='Not found',
                               detail=f'Workspace {id} does not exist')
        return w

    @property
    def can_change_metadata(self):
        return self.state in {WorkspaceState.READY, WorkspaceState.CONFLICT}

    def __repr__(self):
        return f'<Workspace {self.id} [name="{self.name}" ' \
               f'state={self.state.name if self.state else "unset"}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state.name if self.state else None,
            'owner': self.owner.username if self.owner else None,
            'description': self.description,
            'creation_date': self.creation_date,
            'temporary': self.temporary,
            'data_url': self.data_url,
            'families': {f.name: f.version for f in self.families},
        }


class Family(db.Model):

    __table_args__ = (
        # There can only one combination of name and workspace id
        UniqueConstraint('name', 'fk_workspace_id'),
        # Do not allow the version and workspace to be simultaneously null
        CheckConstraint('version IS NOT NULL OR fk_workspace_id IS NOT NULL',
                        name='simul_null_check')
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), index=True, nullable=False)
    version = db.Column(db.Integer)
    description = db.Column(db.Text)

    fk_workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    metadata_set = db.relationship('Metadata', backref='family', lazy='dynamic')

    def __repr__(self):
        return f'<Family {self.id} [{self.name}, version {self.version}]>'

    def increment(self):
        return Family(name=self.name,
                      version=self.version + 1,
                      description=self.description,
                      fk_workspace_id=self.fk_workspace_id)


class Metadata(db.Model):

    __table_args__ = (
        # Do not allow metadata without an "id" entry
        CheckConstraint("json ? 'id'", name='check_id'),
        # TODO: add constraint check file_id == json->'id' ?
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_file = db.Column(UUID(as_uuid=True), index=True, nullable=False)
    json = db.Column(JSONB, nullable=False)

    fk_family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)

    def __repr__(self):
        return f'<Metadata {self.id} [{self.family.name}/{self.family.version}] {self.id_file}>'

    def to_dict(self):
        return {
            'id': str(self.id_file),
            'metadata': {
                self.family.name: self.json,
            }
        }

    def copy(self):
        return Metadata(
            id_file=self.id_file,
            json=self.json,
            fk_family_id=self.fk_family_id,
        )

    def update(self, json):
        """ Update the underlying json metadata with the values of a new one

        This function takes the current json saved in this metadata object and
        updates it (like ``dict.update``) with the new values found in the
        `json` input parameter. This does not remove any key; it adds new keys
        or changes any existing one.

        Since SQLAlchemy does not detect changes on a JSONB column unless a
        new object is assigned to it, this function creates a new dictionary
        and replaces the previous one.

        Changes still need to be committed through a DB session object.

        Parameters
        ----------
        json: dict
            A new metadata object that will update over the existing one

        Returns
        -------
        self
        """
        tmp = self.json.copy()
        tmp.update(json)
        self.json = tmp
        return self

    @staticmethod
    def get_latest(file_id, family):
        latest = Metadata.query.filter_by(id_file=file_id, family=family).first()
        # TODO: add unit test so that adding two modifications to a family does not entail two records
        # ie: the first here is the only possible result
        if latest is not None:
            logger.info('Latest is from this workspace: %s', latest)
            return latest

        # Nothing in the workspace was found, try the previous global metadata
        workspace = family.workspace
        reference = 0
        if workspace.fk_last_metadata_id is not None:
            reference = workspace.fk_last_metadata_id
        latest_global = (
            Metadata
            .query
            .filter(Metadata.id_file == file_id, Metadata.id <= reference)
            .join(Family)
            .filter(Family.name == family.name)
            .order_by(Metadata.id.desc())
            .first()
        )
        if latest_global is not None:
            logger.info('Latest is from previous workspace: %s', latest_global)
            return latest_global

        return None
