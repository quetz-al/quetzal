from flask import Blueprint


bp = Blueprint('redoc', __name__)

# Import routes to create them
from quetzal.app.redoc import routes  # nopep8
