from urllib.parse import urlparse

import click
from flask import current_app
from flask.cli import AppGroup

from quetzal.app.helpers.google_api import get_client


data_cli = AppGroup('data', help='Data API operations.')


@data_cli.command('init')
@click.option('--storage-class', help='Bucket storage class. Default: regional',
              type=click.Choice(['regional', 'multi_regional']),
              default='regional')
@click.option('--location', help='Bucket location. Default: europe-west1',
              default='europe-west1')
def data_init_command(storage_class, location):
    """ Initialize bucket for data"""

    if current_app.config['QUETZAL_DATA_STORAGE'] != 'GCP':
        click.secho('No bucket initialization performed: storage is not GCP.')
        return

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

    click.secho(f'Bucket {bucket.name} created successfully!')


@data_cli.command('init-backups')
@click.option('--storage-class', help='Bucket storage class. Default: regional',
              type=click.Choice(['regional', 'multi_regional']),
              default='regional')
@click.option('--location', help='Bucket location. Default: europe-west1',
              default='europe-west1')
def data_init_backups(storage_class, location):
    """ Initialize bucket for backups"""

    if current_app.config['QUETZAL_DATA_STORAGE'] != 'GCP':
        click.secho('No bucket initialization performed: storage is not GCP.')
        return

    data_bucket = current_app.config['QUETZAL_GCP_BACKUP_BUCKET']
    click.secho(f'Creating bucket for backups {data_bucket}...')

    client = get_client()
    bucket_name = urlparse(data_bucket).netloc
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        raise click.ClickException(f'Cannot create bucket {bucket_name}: already exists')

    bucket.storage_class = storage_class.upper()
    bucket.location = location
    bucket.create()

    click.secho(f'Bucket {bucket.name} created successfully!')
