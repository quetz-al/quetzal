#!/usr/bin/env bash

# Script useful to setup an initial Quetzal server with its buckets, database models, users and roles

set -e  # Stop when a command fails

echo "Initializing buckets..."
flask quetzal data init
flask quetzal data init-backups

echo "Initializing database..."
flask db upgrade head

echo "Initializing roles..."
flask quetzal role create public_read \
    --description "Users that can perform read operations"
flask quetzal role create public_write \
    --description "Users that can perform write operations (create workspaces, upload files, ...)"

# Create admin user
if [ -z ${QUETZAL_ADMIN_MAIL} ]
then
    echo "No admin user created. Set QUETZAL_ADMIN_MAIL environment variable and re-run this script."
else
    echo "Creating admin user..."
    flask quetzal user create admin ${QUETZAL_ADMIN_MAIL}
    flask quetzal role add admin public_read public_write
fi
