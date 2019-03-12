#!/usr/bin/env bash

if [[ -z ${USE_GUNICORN} ]]
then
    echo "Serving with Python/Flask"
    flask run --host 0.0.0.0 --port 5000
else
    echo "Serving with gunicorn"
    gunicorn \
        --bind 0.0.0.0:5000 \
        --timeout 3600 \
        wsgi:app
fi
