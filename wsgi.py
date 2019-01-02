from app import application, db
from app.models import Metadata, Family, User, Workspace, WorkspaceState


@application.shell_context_processor
def make_shell_context():
    return {
        # Handy reference to the database
        'db': db,
        # Add models here
        'User': User,
        'Metadata': Metadata,
        'Family': Family,
        'Workspace': Workspace,
        'WorkspaceState': WorkspaceState,
    }


if __name__ == '__main__':
    application.run()
