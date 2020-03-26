import click
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError

from quetzal.app import db
from quetzal.app.models import ApiKey, User, Role
from quetzal.app.cli.utils import  generate_secret_key

user_cli = AppGroup('user', help='User operations.')
role_cli = AppGroup('role', help='Role operations.')
keys_cli = AppGroup('keys', help='API keys operations.')


@user_cli.command('create')
@click.argument('username')
@click.argument('email')
@click.password_option()
def user_create(username, email, password):
    """Create a user"""
    try:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    except IntegrityError as ex:
        raise click.ClickException('Username or email already exists') from ex
    click.secho(f'User {user.username} ({user.email}) created')


@user_cli.command('list')
def user_list():
    """List existing users"""
    if User.query.count() == 0:
        click.secho('No users exist')
    else:
        click.secho('Users:\nID\tUSERNAME\t\tE-MAIL\t\t\tROLES')
        for user in User.query.all():
            click.secho(f'{user.id}\t{user.username}\t\t{user.email}\t\t\t{",".join([r.name for r in user.roles])}')


@role_cli.command('create')
@click.argument('name')
@click.option('--description', prompt='Role description')
def role_create(name, description):
    """Create a role"""
    role = Role(name=name, description=description)

    try:
        db.session.add(role)
        db.session.commit()
    except IntegrityError as ex:
        raise click.ClickException('Role already exists') from ex

    click.secho(f'Role {role.name} created')


@role_cli.command('delete')
@click.argument('name')
def role_delete(name):
    """Delete a role"""
    role = Role.query.filter_by(name=name).first()
    if role is None:
        raise click.ClickException(f'Role {name} does not exist')
    db.session.delete(role)
    db.session.commit()

    click.secho(f'Role {name} deleted')


@role_cli.command('list')
def role_list():
    """List existing roles"""
    if Role.query.count() == 0:
        click.secho('No roles exist')
    else:
        click.secho('Roles:\nID\tNAME\tDESCRIPTION')
        for role in Role.query.all():
            click.secho(f'{role.id}\t{role.name}\t{role.description}')


@role_cli.command('add')
@click.argument('username', required=True)
@click.argument('rolename', required=True, nargs=-1)
def role_add_user(username, rolename):
    """Add role(s) to a user"""
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise click.ClickException(f'User {username} does not exist')

    for rn in rolename:
        try:
            user.add_role(rn)
        except ValueError as ex:
            raise click.ClickException(f'Could not add role: {ex}') from ex

    db.session.commit()

    click.secho(f'User {user.username} is now part of role'
                f'{"s" if len(rolename) > 1 else ""} '
                f'{", ".join(rolename)}')


@role_cli.command('remove')
@click.argument('username')
@click.argument('rolename')
def role_delete_user(username, rolename):
    """Remove a user from a role"""
    user = User.query.filter_by(username=username).first()
    try:
        user.remove_role(rolename)
    except ValueError as ex:
        raise click.ClickException(f'Could not remove role: {ex}') from ex
    db.session.commit()

    click.secho(f'User {user.username} is no longer part of role {rolename}')


@keys_cli.command('add')
@click.argument('username')
@click.option('--name', required=False, default='unnamed',
              help='Descriptive name of the purpose of this API key')
def key_add(username, name):
    """Generate and associate an API key to a user"""
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise click.ClickException(f'User {username} does not exist')
    key = generate_secret_key.callback(128, show=False)[:32]
    apikey = ApiKey(key=key, name=name, user=user)

    db.session.add(apikey)
    db.session.commit()

    click.secho(f'Key {name} created for user {username}: {key}')


@keys_cli.command('list')
def key_list():
    """List existing API keys"""

    if ApiKey.query.count() == 0:
        click.secho('No API key exist')
    else:
        click.secho('API keys:\nID\tNAME\tUSERNAME')
        for key in ApiKey.query.all():
            click.secho(f'{key.id}\t{key.name}\t{key.user.username}')


@keys_cli.command('revoke')
@click.argument('username')
@click.argument('name')
def key_revoke(username, name):
    """Remove an API key from a user"""

    user = User.query.filter_by(username=username).first()
    if user is None:
        raise click.ClickException(f'User {username} does not exist')

    for key in user.apikeys:
        if key.name == name:
            click.echo(f'Removing key {name} for user {username}')
            db.session.delete(key)
    db.session.commit()
