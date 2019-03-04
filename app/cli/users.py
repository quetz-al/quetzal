import click
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import User, Role

user_cli = AppGroup('user', help='User operations.')
role_cli = AppGroup('role', help='Role operations.')


@user_cli.command('create')
@click.argument('username')
@click.argument('email')
@click.password_option()
def user_create(username, email, password):
    """Create a user"""
    user = User(username=username, email=email)
    user.set_password(password)

    try:
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
        role = Role.query.filter_by(name=rn).first()
        if role is None:
            raise click.ClickException(f'Role {rn} does not exist')

        if role in user.roles:
            raise click.ClickException(f'User {username} already in role {rn}')
        user.roles.append(role)

    db.session.add(user)
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
    role = Role.query.filter_by(name=rolename).first()
    if user is None:
        raise click.ClickException(f'User {username} does not exist')
    if role is None:
        raise click.ClickException(f'Role {rolename} does not exist')

    if role not in user.roles:
        raise click.ClickException(f'User {username} does not have role {role.name}')
    user.roles.remove(role)

    db.session.add(user)
    db.session.commit()

    click.secho(f'User {user.username} is no longer part of role {role.name}')
