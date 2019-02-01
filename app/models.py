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
from app.api.exceptions import (
    InvalidTransitionException, ObjectNotFoundException, QuetzalException
)


logger = logging.getLogger(__name__)


roles_users_table = db.Table('roles_users',
                             db.Column('fk_user_id', db.Integer(), db.ForeignKey('user.id')),
                             db.Column('fk_role_id', db.Integer(), db.ForeignKey('role.id')),
                             UniqueConstraint('fk_user_id', 'fk_role_id'))


class Role(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __repr__(self):
        return f'<Role {self.name} ({self.id})>'

    def __eq__(self, other):
        if not isinstance(other, Role):
            return False
        if other.id is not None:
            return other.id == self.id
        return other.name == self.name


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(256), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    active = db.Column(db.Boolean(), default=True, nullable=False)

    roles = db.relationship('Role', secondary=roles_users_table,
                            backref=db.backref('users', lazy='dynamic'))
    workspaces = db.relationship('Workspace', backref='owner', lazy='dynamic')
    queries = db.relationship('MetadataQuery', backref='owner', lazy='dynamic')

    @property
    def is_active(self):
        return self.active

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
    pg_schema_name = db.Column(db.String(63))

    fk_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    fk_last_metadata_id = db.Column(db.Integer,
                                    db.ForeignKey('metadata.id', use_alter=True, name='workspace_fk_last_metadata_id'),
                                    nullable=True)

    families = db.relationship('Family', backref='workspace', lazy='dynamic')
    queries = db.relationship('MetadataQuery', backref='workspace', lazy='dynamic')

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

    @property
    def can_change_metadata(self):
        return self.state in {WorkspaceState.READY, WorkspaceState.CONFLICT}

    @staticmethod
    def get_or_404(wid):
        """Get a workspace by id or raise an APIException"""
        w = Workspace.query.get(wid)
        if w is None:
            raise ObjectNotFoundException(status=codes.not_found,
                                          title='Not found',
                                          detail=f'Workspace {wid} does not exist')
        return w

    def make_schema_name(self):
        if self.id is None:
            # Cannot generate schema name if this object is not saved yet
            raise QuetzalException('Workspace does not have id yet')
        return 'view_{workspace_id}_{user_id}_{date}'.format(
            workspace_id=self.id,
            user_id=self.owner.id if self.owner else None,
            date=datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        )

    def get_base_family(self):
        return self.families.filter_by(name='base').one()

    def get_previous_metadata(self):
        # Important note: there can be repeated entries!
        reference = self.fk_last_metadata_id
        related_family_names = set(f.name for f in self.families.all())
        previous_meta = (
            Metadata
            .query
            .join(Family)
            .filter(Family.name.in_(related_family_names),
                    # Check that the family's workspace is None: this means is committed
                    Family.fk_workspace_id.is_(None))
        )
        if self.fk_last_metadata_id is not None:
            # Verify the reference when there is one defined, otherwise it means
            # that there was no metadata before
            previous_meta = previous_meta.filter(Metadata.id <= reference)
        return previous_meta

    def get_current_metadata(self):
        # Important note: there can be repeated entries!
        related_family_names = set(f.name for f in self.families.all())
        workspace_meta = (
            Metadata
            .query
            .join(Family)
            .filter(Family.name.in_(related_family_names),
                    Family.workspace == self)
        )
        return workspace_meta

    def get_metadata(self):
        # Important note: this one does not have repeated entries!
        merged_metadata = (
            self.get_previous_metadata()
            .union(
                self.get_current_metadata()
            )
            .join(Family)  # Need to join again with family to use it in the distinct
            .distinct(Metadata.id_file, Family.name)
            .order_by(Metadata.id_file, Family.name, Metadata.id.desc())
        )
        return merged_metadata

    def __repr__(self):
        return f'<Workspace {self.id} [name="{self.name}" ' \
               f'state={self.state.name if self.state else "unset"}] ' \
               f'view={self.pg_schema_name}>'

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
    name = db.Column(db.String(60), index=True, nullable=False)  # 63 due to postgres limit, -3 for internal suffixes
    version = db.Column(db.Integer)  # Can be temporary nullable during workspace creation
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
        # TODO: add index on id? Would it be useful? For jsonb indices, see https://stackoverflow.com/a/17808864/227103
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
        # There is the only possible result (tested by test_update_metadata_db_records)
        if latest is not None:
            logger.info('Latest is from this workspace: %s', latest)
            return latest

        # Nothing in the workspace was found, try the previous global metadata
        # Important: this function only looks on the global workspace until
        # a certain metadata id reference. It will not find metadata that has
        # been added after this reference because this would be new metadata
        # that the workspace should not be able to access
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

    @staticmethod
    def get_latest_global(file_id, family_name=None):
        # Get the families with null workspace (these are the committed families).
        # From these, get the max version of each family.
        # Finally, what we want is the associated metadata so we need to join
        # with the Metadata
        queryset = (
            Metadata
            .query
            .join(Family)
            .filter(Metadata.id_file == file_id,
                    Family.fk_workspace_id.is_(None),
                    # Handy trick to add an inline filter only when family_name is set
                    Family.name == family_name if family_name is not None else True)
            .distinct(Family.name)
            .order_by(Family.name, Family.version.desc())
        )
        return queryset.all()


class QueryDialect(enum.Enum):
    POSTGRESQL = 'postgresql'


class MetadataQuery(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dialect = db.Column(db.Enum(QueryDialect), nullable=False)
    code = db.Column(db.Text, nullable=False)

    fk_workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    fk_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    @staticmethod
    def get_or_create(dialect, code, workspace, owner):
        instance = (
            MetadataQuery
            .query
            .filter_by(dialect=dialect,
                       code=code,
                       workspace=workspace,
                       owner=owner)
            .first()
        )
        if instance is None:
            instance = MetadataQuery(dialect=dialect, code=code, workspace=workspace, owner=owner)
        return instance

    @staticmethod
    def get_or_404(qid):
        """Get a workspace by id or raise an APIException"""
        q = MetadataQuery.query.get(qid)
        if q is None:
            raise ObjectNotFoundException(status=codes.not_found,
                                          title='Not found',
                                          detail=f'MetadataQuery {qid} does not exist')
        return q

    def to_dict(self, results=None):
        _dict = {
            'id': self.id,
            'workspace_id': self.fk_workspace_id,
            'dialect': self.dialect.value,
            'query': self.code,
        }
        if results is not None:
            _dict['results'] = results
        return _dict

    def __repr__(self):
        return f'<MetadataQuery {self.id} ({self.dialect})>'
