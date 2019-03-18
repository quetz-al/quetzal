#!/bin/bash

if [[ -v SERVER_NAMES ]]
then
    echo "Modifying configuration for server names ${SERVER_NAMES}..."
    server_names_spaces=$(echo ${SERVER_NAMES} | tr ',' ' ')
    sed -i \
        -e "s/server_name local.quetz.al;/server_name ${server_names_spaces};/g" \
        /etc/nginx/conf.d/default.conf
fi
