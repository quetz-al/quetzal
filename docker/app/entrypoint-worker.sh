#!/usr/bin/env bash

set -e

pwd

# TODO: document on the importance of concurrency 1 and Ofair
celery worker --app app.celery --loglevel INFO --concurrency 1 -Ofair
