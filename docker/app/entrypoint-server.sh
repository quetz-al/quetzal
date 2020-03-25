#!/usr/bin/env bash

# See parameter expansion on https://stackoverflow.com/a/13864829/227103
if [ -z ${USE_GUNICORN+x} ]
then
    # Variable USE_GUNICORN is not set
    echo "Serving with Python/Flask"
    flask run --host 0.0.0.0 --port 5000
else
    # Variable USE_GUNICORN is set
    echo "Serving with gunicorn"
    gunicorn \
        --bind 0.0.0.0:5000 \
        --timeout 3600 \
        wsgi:app
fi
