import pathlib

import click
from flask.cli import AppGroup

deploy_cli = AppGroup('deploy', help='Deployment operations.')


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
