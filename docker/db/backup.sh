#!/bin/bash
set -e

BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
FILENAME="db_dump-${BACKUP_DATE}.bak.gz"

echo "Creating backup of ${DB_HOST} at ${FILENAME}..."

pg_dumpall --username=${POSTGRES_USER} --host=${DB_HOST} | gzip > ${FILENAME}

echo "Uploading to ${GCP_BACKUP_BUCKET}..."
gcloud auth activate-service-account --key-file=/conf/credentials.json
gsutil cp db_dump-${BACKUP_DATE}.bak.gz ${GCP_BACKUP_BUCKET}/db/
