import inspect
import secrets

import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext

import quetzal.app.models
from quetzal.app import db
from quetzal.app.api.data.tasks import delete_workspace

utils_cli = AppGroup('utils', help='Miscelaneous operations.')


@utils_cli.command('generate-secret-key')
@click.argument('num_bytes', metavar='SIZE', type=click.INT, default=16)
def generate_secret_key(num_bytes):
    """Generate and print a random string of SIZE bytes."""
    rnd = secrets.token_urlsafe(num_bytes)
    click.secho(rnd)


@utils_cli.command()
@click.option('--keep-users', is_flag=True, help='Do not delete users.')
@with_appcontext
def nuke(keep_users):
    """Erase the database. Use with care."""
    width, _ = click.get_terminal_size()
    env = current_app.env
    if env == 'production':
        bad = 'A REALLY BAD IDEA'
    elif env == 'development':
        bad = 'probably ok'
    else:
        bad = 'maybe a bad idea'
    click.secho('*'*width, fg='yellow')
    click.secho('This command will *DELETE* the database, losing *ALL* '
                'metadata, workspaces, users, roles.\n'
                'Please confirm THREE '
                'times by answering the following questions.', fg='yellow')
    click.secho('*'*width, fg='yellow')
    click.confirm('Are you sure?', abort=True, default=False)

    click.secho('*' * width, fg='red')
    click.secho('This is your second warning.\n'
                'All files in the bucket storage will be lost as well. '
                'If you are not sure, abort now.',
                fg='red')
    click.secho('*' * width, fg='red')
    click.confirm('Do you really want to erase all?', abort=True, default=False)

    click.secho('*' * width, bg='red', fg='white', blink=True)
    click.secho(f'This is your last chance. EVERYTHING will be lost.\n'
                f'The only reason you should be doing this is because you '
                f'are resetting a development server.\n'
                f'Your current FLASK_ENV is "{env}" so continuing is {bad}.\n'
                f'This is the final confirmation...',
                bg='red', fg='white', blink=True)
    click.secho('*' * width, bg='red', fg='white', blink=True)
    abort = click.confirm('Do you want to abort?', abort=False, default=True)
    if abort:
        raise click.Abort()

    blacklist = []
    if keep_users:
        blacklist.append(quetzal.app.models.User)
        blacklist.append(quetzal.app.models.Role)

    # Delete all files in all workspaces
    workspaces_with_data = db.session.query(quetzal.app.models.Workspace).filter(
        quetzal.app.models.Workspace._state != quetzal.app.models.WorkspaceState.DELETED,
        quetzal.app.models.Workspace.data_url.isnot(None),
    )
    click.echo(f'Erasing {workspaces_with_data.count()} workspaces...')
    for workspace_id in [w.id for w in workspaces_with_data]:
        # For some weird reason, in this loop I need to use directly the
        # workspace.id instead of the instance or I get a
        # sqlalchemy.orm.exc.DetachedInstanceError
        try:
            delete_workspace(workspace_id, force=True)
        except Exception as ex:
            click.secho(f'Could not delete workspace {workspace_id}: '
                        f'{type(ex).__name__}: {ex}')
            continue

    classes = inspect.getmembers(quetzal.app.models, inspect.isclass)

    with db.session.no_autoflush:
        # Disabling autoflush because intermediate deletes would violate some
        # not null constraints.
        for name, cls in classes:
            if issubclass(cls, db.Model) and cls not in blacklist:
                instances = db.session.query(cls)
                click.echo(f'Erasing all {instances.count()} '
                           f'entries of {cls.__name__}...')
                for i in instances.all():
                    db.session.delete(i)

        db.session.commit()

    click.secho('Database entries removed.', color='blue')
