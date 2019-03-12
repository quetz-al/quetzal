from flask import render_template, url_for

from quetzal.app.redoc import bp


@bp.route('/redoc', methods=['GET'])
def redoc():
    spec_url = url_for('/api/v1./api/v1_openapi_json', _external=True, _scheme='https')
    return render_template('redoc/index.html',
                           title='Quetzal API - ReDoc',
                           spec_url=spec_url)
