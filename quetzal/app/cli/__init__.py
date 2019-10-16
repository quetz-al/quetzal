from flask.cli import AppGroup

from .data import data_cli
from .deployment import deploy_cli
from .users import keys_cli, user_cli, role_cli
from .utils import utils_cli

quetzal_cli = AppGroup('quetzal', help='Quetzal operations.')

quetzal_cli.add_command(data_cli)
quetzal_cli.add_command(keys_cli)
quetzal_cli.add_command(user_cli)
quetzal_cli.add_command(role_cli)
quetzal_cli.add_command(deploy_cli)
quetzal_cli.add_command(utils_cli)
