from urllib.parse import urlparse

import click
from flask import current_app
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError

from app import db
from app.helpers.google_api import get_client
from app.models import User, Role


data_cli = AppGroup('data', help='Quetzal data API operations')
user_cli = AppGroup('user', help='Quetzal user operations')
role_cli = AppGroup('role', help='Quetzal role operations')


@data_cli.command('init')
@click.option('--storage-class', help='Bucket storage class. Default: regional',
              type=click.Choice(['regional', 'multi_regional']),
              default='regional')
@click.option('--location', help='Bucket location. Default: europe-west1',
              default='europe-west1')
def data_init_command(storage_class, location):
    """ Initialize data buckets """
    data_bucket = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    click.secho(f'Creating bucket {data_bucket}...')

    client = get_client()
    bucket_name = urlparse(data_bucket).netloc
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        raise click.ClickException(f'Cannot create bucket {bucket_name}: already exists')

    bucket.storage_class = storage_class.upper()
    bucket.location = location
    bucket.create()

    click.secho(f'Bucket created {bucket.name} successfully!')


@user_cli.command('create')
@click.argument('username')
@click.argument('email')
@click.password_option()
def user_create(username, email, password):
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
    role = Role.query.filter_by(name=name).first()
    if role is None:
        raise click.ClickException(f'Role {name} does not exist')
    db.session.delete(role)
    db.session.commit()

    click.secho(f'Role {name} deleted')


@role_cli.command('list')
def role_list():
    if Role.query.count() == 0:
        click.secho('No roles exist')
    else:
        click.secho('Roles:\nID\tNAME\tDESCRIPTION')
        for role in Role.query.all():
            click.secho(f'{role.id}\t{role.name}\t{role.description}')


@role_cli.command('add')
@click.argument('username')
@click.argument('rolename')
def role_add_user(username, rolename):
    user = User.query.filter_by(username=username).first()
    role = Role.query.filter_by(name=rolename).first()
    if user is None:
        raise click.ClickException(f'User {username} does not exist')
    if role is None:
        raise click.ClickException(f'Role {rolename} does not exist')

    if role in user.roles:
        raise click.ClickException(f'User {username} already in role {rolename}')
    user.roles.append(role)

    db.session.add(user)
    db.session.commit()

    click.secho(f'User {user.username} is now part of role {role.name}')


@role_cli.command('remove')
@click.argument('username')
@click.argument('rolename')
def role_delete_user(username, rolename):
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
