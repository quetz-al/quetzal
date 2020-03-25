import pathlib

import toml


def get_version() -> str:
    """Retrieve version from the project's pyproject.toml file"""
    pyproject = pathlib.Path(__file__).parent / '..' / '..' / 'pyproject.toml'
    try:
        with pyproject.open('r') as f:
            project = toml.load(f)
        return project['tool']['poetry']['version']
    except:
        return '0.0.0'
