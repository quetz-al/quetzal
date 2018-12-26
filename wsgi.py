from app import application, db
from app.models import Workspace


@application.shell_context_processor
def make_shell_context():
    return {
        # Handy reference to the database
        'db': db,
        # Add models here
        'Workspace': Workspace,
    }


if __name__ == '__main__':
    application.run()
