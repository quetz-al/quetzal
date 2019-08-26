import datetime

from flask import Blueprint, redirect, Response, url_for

static_bp = Blueprint('static-content', __name__)
start_time = datetime.datetime.now()


@static_bp.route('/')
def index():
    return redirect(url_for('redoc.redoc'))


@static_bp.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico'))


@static_bp.route('/healthz')
def health():
    now = datetime.datetime.now()
    status = 500
    if (now - start_time).total_seconds() > 10:
        status = 200
    return Response(status=status)
