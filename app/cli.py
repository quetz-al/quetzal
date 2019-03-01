import pathlib
import secrets
from urllib.parse import urlparse

import click
from flask import current_app
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError

from app import db
from app.helpers.google_api import get_client
from app.models import User, Role

data_cli = AppGroup('data', help='Data API operations.')
user_cli = AppGroup('user', help='User operations.')
role_cli = AppGroup('role', help='Role operations.')
deploy_cli = AppGroup('deploy', help='Deployment operations.')
utils_cli = AppGroup('utils', help='Miscelaneous operations.')
quetzal_cli = AppGroup('quetzal', help='Quetzal operations.')

quetzal_cli.add_command(data_cli)
quetzal_cli.add_command(user_cli)
quetzal_cli.add_command(role_cli)
quetzal_cli.add_command(deploy_cli)
quetzal_cli.add_command(utils_cli)


@data_cli.command('init')
@click.option('--storage-class', help='Bucket storage class. Default: regional',
              type=click.Choice(['regional', 'multi_regional']),
              default='regional')
@click.option('--location', help='Bucket location. Default: europe-west1',
              default='europe-west1')
def data_init_command(storage_class, location):
    """ Initialize bucket for data"""
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


@data_cli.command('init-backups')
@click.option('--storage-class', help='Bucket storage class. Default: regional',
              type=click.Choice(['regional', 'multi_regional']),
              default='regional')
@click.option('--location', help='Bucket location. Default: europe-west1',
              default='europe-west1')
def data_init_command(storage_class, location):
    """ Initialize bucket for backups"""
    data_bucket = current_app.config['QUETZAL_GCP_BACKUP_BUCKET']
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


@deploy_cli.command('create-images')
@click.option('--registry',
              help='Name of the Docker registry where the images will be pushed.')
@click.argument('images', nargs=-1)
@click.pass_context
def create_docker_images(ctx, registry, images):
    """Create docker images for all services."""
    # This is the map of docker images that need to be built, and the
    # corresponding keyword arguments needed to build them.
    images_kwargs = {
        'nginx': dict(path='docker/nginx'),
        'db': dict(path='docker/db'),
        'rabbitmq': dict(path='docker/rabbitmq'),
        # The image for the app and worker is slightly different, because it
        # uses the root directory as context
        'app': dict(path=str(pathlib.Path().resolve()),
                    dockerfile='docker/app/Dockerfile'),
    }

    # Extra parameter validation
    for i in images:
        if i not in images_kwargs:
            raise click.BadParameter(f'"{i}" is an unknown docker image for Quetzal.',
                                     ctx=ctx, param_hint='images')
    # Default is to build all images
    if not images:
        click.echo('No image supplied, building all images.')
        images = list(images_kwargs)

    # Get the docker client object
    import docker
    client = docker.from_env()
    version = '0.1.0'

    # Build and push each image
    for i in images:
        _build_image(client, tag=f'quetzal/{i}:{version}',
                     registry=registry, **images_kwargs[i])


def _build_image(client, **kwargs):
    tag = kwargs['tag']
    registry = kwargs.pop('registry')
    click.secho(f'Building image {tag}...', fg='blue')
    image, logs = client.images.build(**kwargs)
    for line in logs:
        if 'stream' in line and line['stream'].strip():
            click.echo(line['stream'].strip())
    if registry:
        click.secho(f'Uploading {registry}/{tag}...', fg='blue')
        full_tag = f'{registry}/{tag}'
        image.tag(full_tag)
        for line in client.images.push(full_tag, stream=True, decode=True):
            if 'error' in line:
                raise click.ClickException(line['error'].strip())
            if 'stream' in line and line['stream'].strip():
                click.echo(line['stream'].strip())
    return image


@utils_cli.command('generate-secret-key')
@click.argument('num_bytes', metavar='SIZE', type=click.INT, default=16)
def generate_secret_key(num_bytes):
    """Generate and print a random string of SIZE bytes."""
    rnd = secrets.token_urlsafe(num_bytes)
    click.secho(rnd)


@utils_cli.command()
def nuke():
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
    click.confirm('Are you sure?', abort=True, default=False)

    click.secho('*' * width, bg='red', fg='white', blink=True)
    click.secho(f'This is your last chance. EVERYTHING will be lost.\n'
                f'The only reason you should be doing this is because you '
                f'are resetting a development server.\n'
                f'Your current FLASK_ENV is "{env}" so continuing is {bad}.\n'
                f'I am going to ask differently...',
                bg='red', fg='white', blink=True)
    click.secho('*' * width, bg='red', fg='white', blink=True)
    abort = click.confirm('Do you want to abort?', abort=False, default=True)
    if abort:
        raise click.Abort()

    click.secho('Not implemented yet, phew!', fg='blue')
