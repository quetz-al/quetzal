#!/usr/bin/env bash

# TODO: document on the importance of --concurrency 1 and -Ofair
celery worker --app app.celery --loglevel DEBUG --concurrency 1 -Ofair
