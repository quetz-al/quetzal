import logging
from collections import namedtuple
from functools import partial

from flask_principal import Permission, RoleNeed


logger = logging.getLogger(__name__)


WorkspaceNeed = namedtuple('workspace_need', ['operation', 'workspace_id'])
ReadWorkspaceNeed = partial(WorkspaceNeed, 'read')  # Equivalent to WorkspaceNeed('read', ...)
WriteWorkspaceNeed = partial(WorkspaceNeed, 'write')  # Equivalent to WorkspaceNeed('write', ...)

PublicReadPermission = Permission(RoleNeed('public_read'))
PublicWritePermission = Permission(RoleNeed('public_read'),
                                   RoleNeed('public_write'))
PublicCommitPermission = Permission(RoleNeed('public_read'),
                                    RoleNeed('public_write'),
                                    RoleNeed('public_commit'))


class ReadWorkspacePermission(Permission):
    def __init__(self, workspace_id):
        # To read a workspace, one must have:
        # public_read role and a workspace-specific read permission
        super().__init__(PublicReadPermission,
                         ReadWorkspaceNeed(workspace_id))


class WriteWorkspacePermission(Permission):
    def __init__(self, workspace_id):
        # To read a workspace, one must have:
        # public_write role and a workspace-specific write permission
        super().__init__(PublicWritePermission, WriteWorkspaceNeed(workspace_id))


class CommitWorkspacePermission(Permission):
    def __init__(self, workspace_id):
        # To commit a workspace, one must have:
        # public_commit role and a workspace-specific write permission
        super().__init__(PublicCommitPermission,
                         WriteWorkspaceNeed(workspace_id))


def load_identity(sender, identity):
    from quetzal.app.models import User
    user = User.query.get(identity.id)

    # Inactive users are not authorized to anything
    if not user.is_active:
        return identity

    # Add role authorizations
    for role in user.roles:
        identity.provides.add(RoleNeed(role.name))

    # Add workspace authorizations:
    # The owner of a workspace can read and write to it
    for workspace in user.workspaces:
        identity.provides.add(ReadWorkspaceNeed(workspace.id))
        identity.provides.add(WriteWorkspaceNeed(workspace.id))

    return identity
