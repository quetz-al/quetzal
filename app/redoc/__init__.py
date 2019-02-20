from flask import Blueprint


bp = Blueprint('redoc', __name__)


from app.redoc import routes
