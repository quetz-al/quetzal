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

from quetzal.app import db
from quetzal.app.api.exceptions import (
    InvalidTransitionException, ObjectNotFoundException, QuetzalException
)


logger = logging.getLogger(__name__)


roles_users_table = db.Table('roles_users',
                             db.Column('fk_user_id', db.Integer(), db.ForeignKey('user.id')),
                             db.Column('fk_role_id', db.Integer(), db.ForeignKey('role.id')),
                             UniqueConstraint('fk_user_id', 'fk_role_id'))
"""
Auxiliary table associating users and roles
"""


class Role(db.Model):
    """ Authorization management role on Quetzal

    Quetzal operations are protected by an authorization system based on roles.
    A user may have one to many roles; a role defines what operations the
    associated users can do.

    Note that the *n to n* relationship of roles and users is implemented
    through the :py:attr:`roles_users_table`.

    Attributes
    ----------
    id: int
        Identifier and primary key of a role.
    name: str
        Unique name of the role.
    description: str
        Human-readable description of the role.

    Extra attributes
    ----------------
    users
        Set of users associated with this role. This attribute is defined
        through a backref in :py:class:`User`.

    """
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
    """ Quetzal user

    Almost all operations on Quetzal can only be done with an authenticated
    user. This model defines the internal information that Quetzal needs for
    bookeeping its users, permissions, emails, etc.

    Attributes
    ----------
    id: int
        Identifier and primary key of a user.
    username: str
        Unique string identifier of a user (e.g. admin, alice, bob).
    email: str
        Unique e-mail address of a user.
    password_hash: str
        Internal representation of the user password with salt.
    token: str
        Unique, temporary authorization token.
    token_expiration: datetime
        Expiration date of autorization token.
    active: bool
        Whether this user is active (and consequently can perform operations)
        or not.

    Extra attributes
    ----------------
    roles
        Set of :py:class:`Roles <Role>` associated with this user.
    workspaces
        Set of :py:class:`Workspaces <Workspace>` owned by this user.
    queries
        Set of :py:class:`Queries <Query>` created by this user.

    """

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
        """Property accessor for :py:attr:`active`.

        Needed to conform to the :py:class:`flask_login.UserMixin` interface.
        """
        return self.active

    def set_password(self, password):
        """ Change the password of this user.

        This function set and store the new password as a salt-hashed string.

        The changes on this instance are not propagated to the database (this
        must be done by the caller), but this instance added to the current
        database session.

        Parameters
        ----------
        password: str
            The new password.
        """
        self.password_hash = generate_password_hash(password)
        db.session.add(self)

    def check_password(self, password):
        """ Check if a password is correct.

        Parameters
        ----------
        password: str
            The password to verify against the hash-salted stored password.

        Returns
        -------
        bool
            ``True`` when the provided password matches the hash-salted stored
            one.
        """
        return check_password_hash(self.password_hash, password)

    def get_token(self, expires_in=3600):  # TODO: setting for timeout
        """ Create or retrieve an authorization token

        When a user already has an authorization token, it returns it.

        If there is no authorization token or the existing authorization token
        for this user is expired, this function will create a new one as
        a random string.

        The changes on this instance are not propagated to the database (this
        must be done by the caller), but this instance added to the current
        database session.

        Parameters
        ----------
        expires_in: int
            Expiration time, in seconds from the current date, used when
            creating a new token.

        Returns
        -------
        str
            The authorization token

        """
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        """ Revoke the authorization token

        The changes on this instance are not propagated to the database (this
        must be done by the caller), but this instance added to the current
        database session.

        """
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)
        db.session.add(self)

    @staticmethod
    def check_token(token):
        """ Retrieve a user by token

        No user will be returned when the token is expired or does not exist.

        Parameters
        ----------
        token: str
            Authorization token.

        Returns
        -------
        user: :py:class:`User`
            User with the provided token, or ``None`` when either the token
            was not found or it was expired.

        """
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        logger.debug('Token still valid for %d seconds',
                     (user.token_expiration - datetime.utcnow()).total_seconds())
        return user

    def __repr__(self):
        return f'<User {self.username}>'


class ApiKey(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(60), unique=True)
    key = db.Column(db.String(32), index=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='apikeys')

    @staticmethod
    def check_key(key):
        apikey = ApiKey.query.filter_by(key=key).first()
        if apikey is None:
            return None
        return apikey


@enum.unique
class FileState(enum.Enum):
    """ State of a Quetzal file

    Quetzal files have a status, saved in their *base* metadata under the
    *state* key. It can only have the values defined in this enumeration.

    """
    READY = 'ready'
    """File is ready
    
    It has been uploaded, it can be downloaded, its metadata can be changed and
    when its workspace is committed, it will be moved to the global data storage
    directory or bucket.
    """

    TEMPORARY = 'temporary'
    """File is ready but temporary
    
    Like :py:attr:`READY`, but this file will not be considered when the
    workspace is committed. That is, it will not be copied to the global data
    storage directory or bucket.
    """

    DELETED = 'deleted'
    """File has been deleted.
    
    Deleted files will have their metadata cleared when the workspace is 
    committed. 
    
    If it was an already committed file, its contents will not be
    removed from the global data storage directory or bucket, but its metadata
    will be cleared. If it was a file that was not committed yet, it will be
    erased from its workspace data directory or bucket.
    
    Deleted files are not considered in queries.
    """


@enum.unique
class BaseMetadataKeys(enum.Enum):
    """ Set of metadata keys that exist in the base metadata family

    The base metadata family is completely managed by Quetzal; a user cannot
    set or change its values (with the exception of the value for the *path* or
    *filename* keys). This enumeration defines the set of keys that exist in
    this family.

    """

    ID = 'id'
    """Unique file identifier."""

    FILENAME = 'filename'
    """Filename, without its path component."""

    PATH = 'path'
    """Path component of the filename."""

    SIZE = 'size'
    """Size in bytes of the file."""

    CHECKSUM = 'checksum'
    """MD5 checksum of the file"""

    DATE = 'date'
    """Date when this file was created."""

    URL = 'url'
    """URL where this file is stored."""

    STATE = 'state'
    """State of the file; see :py:class:`FileState`."""


@enum.unique
class WorkspaceState(enum.Enum):
    """ Status of a workspace.

    Workspaces in Quetzal have a state that defines what operations can be
    performed on them. This addresses the need for long-running tasks that
    modify the workspace, such as initialization, committing, deleting, etc.

    The transitions from one state to another is defined on this enumeration
    on the :py:meth:`transitions` function. The following diagram illustrates
    the possible state transitions:

    .. raw:: html

        <object data="_static/diagrams/workspace-states.svg" type="image/svg+xml"></object>

    The verification of state transitions is implemented in
    the :py:attr:`quetzal.app.models.Workspace.state` property setter function.

    """

    INITIALIZING = 'initializing'
    """The workspace has just been created. 
    
    The workspace will remain on this state until the initialization routine 
    finishes. No operation is possible until then.
    """

    READY = 'ready'
    """The workspace is ready.
    
    The workspace can now be scanned, updated, committed or deleted. Files can
    be uploaded to it and their metadata can be changed.
    """

    SCANNING = 'scanning'
    """The workspace is updating its internal views.
    
    The workpace will remain on this state until the scanning routine finishes.
    No operation is possible until then.
    """

    UPDATING = 'updating'
    """The workspace is updating its metadata version definition.
    
    The workpace will remain on this state until the updating routine finishes.
    No operation is possible until then.
    """

    COMMITTING = 'committing'
    """The workspace is committing its files and metadata.
    
    The workpace will remain on this state until the committing routine finishes.
    No operation is possible until then.
    """

    DELETING = 'deleting'
    """The workspace is deleting its files and itself.
    
    The workpace will remain on this state until the deleting routine finishes.
    No operation is possible.
    """

    INVALID = 'invalid'
    """The workspace has encountered an unexpected error.
    
    The workpace will remain on this state until the administrator fixes this
    situation.
    No operation is possible.
    """

    CONFLICT = 'conflict'
    """The workspace detected a conflict during its commit routine.
    
    The workpace will remain on this state until the administrator fixes this
    situation.
    No operation is possible.
    """

    DELETED = 'deleted'
    """The workspace has been deleted.
    
    The instance of the workspace remains in database for bookeeping, but there
    is no operation possible with it at this point.
    """

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
            ws.DELETING: {ws.DELETED, ws.INVALID},
            ws.INVALID: {ws.UPDATING, ws.DELETING},
            ws.CONFLICT: {ws.UPDATING, ws.DELETING},
            ws.DELETED: {},
        }

    @staticmethod
    def valid_transition(from_value, to_value):
        """Determine if a state transition is valid"""
        return to_value in WorkspaceState.transitions().get(from_value, {})


class Workspace(db.Model):
    """ Quetzal workspace

    In Quetzal, all operations on files and metadata are *sandboxed* in
    workspaces. Workspaces define the exact metadata families and versions,
    which in turn provides a snapshot of what files and metadata are available.
    This is the base of the reproducibility of dataset in Quetzal and the
    traceability of the data changes.

    Workspaces also provide a storage directory or bucket where the user can
    upload new and temporary data files.

    Attributes
    ----------
    id: int
        Identifier and primary key of a workspace.
    name: str
        Short name for a workspace. Unique together with the owner's username.
    _state: :py:class:`WorkspaceState`
        State of the workspace. Do not use directly, use its property accessors.
    description: str
        Human-readable description of the workspace, its purpose, and any other
        useful comment.
    creation_date: datetime
        Date when the workspace was created.
    temporary: bool
        When ``True``, Quetzal will know that this workspace is intended for
        temporary operations and may be deleted automatically when not used
        for a while. When ``False``, only its owner may delete it.
    data_url: str
        URL to the data directory or bucket where new files associated to this
        workspace will be saved.
    pg_schema_name: str
        Used when creating structured views of the structured metadata, this
        schema name is the postgresql schema where temporary tables exists
        with a copy of the unstructured metadata.
    fk_user_id: int
        Owner of this workspace as a foreign key to a :py:class:`User`.
    fk_last_metadata_id: int
        Reference to the most recent :py:class:`Metadata` object that has been
        committed at the time when this workspace was created. This permits to
        have a reference to which global metadata entries should be taken into
        account when determining the metadata in this workspace.

    Extra attributes
    ----------------
    families
        Set of :py:class:`Families <Family>` (including its version) used for
        this workspace.
    queries
        Set of :py:class:`Queries <Query>` created on this workspace.

    """

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
        """Property accessor for the workspace state"""
        return self._state

    @state.setter
    def state(self, new_state):
        """Property setter for the workspace state

        This function enforces a valid transition as defined in
        :py:func:`quetzal.app.models.WorkspaceState.transitions`.
        """
        if WorkspaceState.valid_transition(self._state, new_state):
            self._state = new_state
        else:
            raise InvalidTransitionException(f'Invalid state transition '
                                             f'{self._state} -> {new_state}')

    @property
    def can_change_metadata(self):
        """Returns ``True`` when metadata can be changed on the current workspace state"""
        return self.state in {WorkspaceState.READY, WorkspaceState.CONFLICT}

    @staticmethod
    def get_or_404(wid):
        """Get a workspace by id or raise a :py:class:`quetzal.app.api.exceptions.ObjectNotFoundException`"""
        w = Workspace.query.get(wid)
        if w is None:
            raise ObjectNotFoundException(status=codes.not_found,
                                          title='Not found',
                                          detail=f'Workspace {wid} does not exist')
        return w

    def make_schema_name(self):
        """Generate a unique schema name for its internal structured metadata views"""
        if self.id is None:
            # Cannot generate schema name if this object is not saved yet
            raise QuetzalException('Workspace does not have an id yet')
        return 'q_{workspace_id}_{user_id}_{date}'.format(
            workspace_id=self.id,
            user_id=self.owner.id if self.owner else None,
            date=datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        )

    def get_base_family(self):
        """Get the base family instance associated with this workspace"""
        return self.families.filter_by(name='base').one()

    def get_previous_metadata(self):
        """Get the global metadata of this workspace

        The global metadata is the metadata that already has been committed,
        but it must also have a version value that is under the values declared
        for this workspace.
        """
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
        """Get the metadata that has been added or modified in this workspace

        In contrast to :py:meth:`get_previous_metadata`, this function only
        retrieves the metadata that has been changed on this workspace after
        its creation.
        """
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
        """Get a union of the previous and new metadata of this workspace

        This function uses a combination of the results of
        :py:meth:`get_previous_metadata` and :py:meth:`get_current_metadata`
        to obtain the merged version of both. This represents the definitive
        metadata of each file, regardless of changes before or after the
        creation of this workspace.

        """
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

    def has_file(self, uuid):
        base = self.get_base_family()
        latest = Metadata.get_latest(uuid, base)
        return latest is not None

    def __repr__(self):
        return f'<Workspace {self.id} [name="{self.name}" ' \
               f'state={self.state.name if self.state else "unset"}] ' \
               f'view={self.pg_schema_name}>'

    def to_dict(self):
        """Return a dictionary representation of the workspace

        This is used in particular to adhere to the OpenAPI specification of
        workspace details objects.

        Returns
        -------
        dict
            Dictionary representation of this object.
        """
        return {
            'id': self.id,
            'name': self.name,
            'status': self.state.name if self.state else None,
            'owner': self.owner.username if self.owner else None,
            'description': self.description,
            'creation_date': self.creation_date,
            'temporary': self.temporary,
            'data_url': self.data_url,
            'families': {f.name: f.version for f in self.families},
        }


class Family(db.Model):
    """ Quetzal metadata family

    In quetzal, metadata are organized in semantic groups that have a name and
    a version number. This is the definition of a metadata _family_. This
    class represents this definition. It is attached to a workspace, until the
    workspace is committed: at this point the family will be disassociated
    from the workspace to become *global* (available as public information).

    Attributes
    ----------
    id: int
        Identifier and primary key of a family.
    name: str
        Name of the family.
    version: int
        Version of the family. Can be ``None`` during a workspace creation, and
        until its initialization, to express the *latest* available version.
    description: str
        Human-readable description of the family and its contents,
        documentation, and any other useful comment.
    fk_workspace_id: int
        Reference to the workspace that uses this family. When ``None``, it
        means that this family and all its associated metadata is public.

    Extra attributes
    ----------------
    metadata_set
        All :py:class:`Metadata` entries associated to this family.

    """

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
        """Create a new family with the same name but next version number

        The new family will be associated to the same workspace.
        """
        return Family(name=self.name,
                      version=self.version + 1,
                      description=self.description,
                      fk_workspace_id=self.fk_workspace_id)


class Metadata(db.Model):
    """ Quetzal unstructured metadata

    Quetzal defines metadata as a dictionary associated with a family. Families
    define the semantic organization and versioning of metadata, while this
    class gathers all the metadata key and values in a dictionary, represented
    as a JSON object.

    Attributes
    ----------
    id: int
        Identifier and primary key of a metadata entry.
    id_file: :py:class:`uuid.UUID`
        Unique identifier of a file as a UUID number version 4. This identifier
        is also present and must be the same as the *id* entry in the `json`
        member.
    json: dict
        A json representation of metadata. Keys are metadata names and values
        are the related values. It may be a nested object if needed.

    Extra attributes
    ----------------
    family
        The related :py:class:`Family` associated to this metadata.

    """

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
        """Return a dictionary representation of the metadata

        Used to conform to the metadata details object on the OpenAPI
        specification.

        Returns
        -------
        dict
            Dictionary representation of this object.
        """
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
        """Retrieve the latest metadata of a file under a particular family

        Todo
        ----
        Define, document, explain or rethink this function with respect to
        :py:func:`Workspace.get_previous_metadata`,
        :py:func:`Workspace.get_current_metadata`, and
        :py:func:`Workspace.get_metadata`.
        """
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
            .filter(Metadata.id_file == file_id,
                    Family.fk_workspace_id.is_(None),
                    Metadata.id <= reference)
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
    def get_latest_global(file_id=None, family_name=None):
        """Retrieve the latest metadata of a file under a particular family

        Todo
        ----
        Define, document, explain or rethink this function with respect to
        :py:func:`Workspace.get_previous_metadata`,
        :py:func:`Workspace.get_current_metadata`, and
        :py:func:`Workspace.get_metadata`.
        """
        # Get the families with null workspace (these are the committed families).
        # From these, get the max version of each family.
        # Finally, what we want is the associated metadata so we need to join
        # with the Metadata
        if file_id is not None:
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
        else:
            queryset = (
                Metadata
                .query
                .join(Family)
                .filter(Family.fk_workspace_id.is_(None),
                        # Handy trick to add an inline filter only when family_name is set
                        Family.name == family_name if family_name is not None else True)
                .distinct(Metadata.id_file, Family.name)
                .order_by(Metadata.id_file, Family.name, Family.version.desc())
            )
        return queryset


class QueryDialect(enum.Enum):
    """Query dialects supported by Quetzal"""

    POSTGRESQL = 'postgresql'
    POSTGRESQL_JSON = 'postgresql_json'


class MetadataQuery(db.Model):
    """ Query for metadata on Quetzal

    Queries on Quetzal are temporarily saved as objects. This was initially
    thought as a mechanism for easier and faster paginations, to avoid verifying
    that a query is valid every time and possibly to compile these queries if
    needed.

    Attributes
    ----------
    id: int
        Identifier and primary key of a query.
    dialect: :py:class:`QueryDialect`
        Dialect used on this query.
    code: str
        String representation of the query. May change in the future.
    fk_workspace_id: int
        Reference to the :py:class:`Workspace` where this query is applied. If
        ``None``, the query is applied on the global, committed metadata.
    fk_user_id: int
        Reference to the :py:class:`User` who created this query.

    """

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dialect = db.Column(db.Enum(QueryDialect), nullable=False)
    code = db.Column(db.Text, nullable=False)

    fk_workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    fk_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    @staticmethod
    def get_or_create(dialect, code, workspace, owner):
        """Retrieve a query by its fields or create a new one"""
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
        """ Create a dict representation of the query and its results

        Used to conform to the OpenAPI specification of the paginable query
        results

        Parameters
        ----------
        results: dict
            Results as a paginable object.

        Returns
        -------
        dict
            Dictionary representation of this object.

        """
        _dict = {
            'id': self.id,
            'workspace_id': self.fk_workspace_id,
            'dialect': self.dialect.value,
            'query': self.code,
        }
        if results is not None:
            _dict.update(results)
        return _dict

    def __repr__(self):
        return f'<MetadataQuery {self.id} ({self.dialect})>'
