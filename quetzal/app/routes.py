from flask import Blueprint, redirect, url_for

static_bp = Blueprint('static-content', __name__)


@static_bp.route('/')
def index():
    return redirect(url_for('redoc.redoc'))


@static_bp.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico'))
