import pathlib
import re

import click
from flask.cli import AppGroup

from quetzal.app import __version__


deploy_cli = AppGroup('deploy', help='Deployment operations.')

# Regex on semver taken from
# https://github.com/semver/semver/issues/232#issuecomment-430840155
semver_re = re.compile(
    r'^'
    r'(?P<Major>0|[1-9]\d*)\.'
    r'(?P<Minor>0|[1-9]\d*)\.'
    r'(?P<Patch>0|[1-9]\d*)'
    r'(?P<PreReleaseTagWithSeparator>'
      r'-(?P<PreReleaseTag>'
        r'(?:0|[1-9]\d*|\d*[A-Z-a-z-][\dA-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][\dA-Za-z-]*))*'
      r')'
    r')?'
    r'(?P<BuildMetadataTagWithSeparator>'
      r'\+(?P<BuildMetadataTag>[\dA-Za-z-]+(\.[\dA-Za-z-]*)*)'
    r')?'
    r'$'
)


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

    # Determine version tag
    app_version = __version__
    semver_match = semver_re.match(app_version)
    if semver_match:
        # take semver without the build tag
        version = '{major}.{minor}.{patch}{prerelease}'.format(
            major=semver_match.group('Major'),
            minor=semver_match.group('Minor'),
            patch=semver_match.group('Patch'),
            prerelease=semver_match.group('PreReleaseTagWithSeparator') or ''
        )
        if semver_match.group('BuildMetadataTagWithSeparator') is not None:
            click.confirm(f'Current version is is {app_version}, which is not a '
                          f'"clean" version. Images will be tagged as "{version}"'
                          f'\nAre you sure you want to push these images?',
                          abort=True, default=False)
    else:
        raise click.ClickException('Version string does not conform to semver')

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
