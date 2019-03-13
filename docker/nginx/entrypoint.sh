#!/bin/bash

# turn on bash's job control
# as documented in https://docs.docker.com/config/containers/multi-service_container/
# since we need to run nginx and certbot
set -m
set -o pipefail
set -e

# Change configuration file to add server_name
/genconf.sh

# Run nginx and put it in the background
nginx -g 'daemon off;' &

# Run the certbot initial configuration
echo "Verifying certbot configuration..."
needs_initial_run=""
if [[ -v SERVER_NAMES ]]
then
    for server in $(echo ${SERVER_NAMES} | sed "s/,/ /g")
    do
        if [[ ! -f  "/etc/letsencrypt/live/${server}/fullchain.pem" ]]
        then
            needs_initial_run="1"
        fi
    done
fi
if [[ -v DISABLE_CERTBOT ]]
then
    echo "Certbot initial configuration disabled through DISABLE_CERTBOT"
else
    if [[ -n "${needs_initial_run}" ]]
    then
        echo "Needs an initial run of certbot..."
        sleep 10
        certbot --nginx certonly \
                -n --agree-tos \
                --email ${ADMIN_EMAIL} \
                -d ${SERVER_NAMES}
        sed -i \
            -e "s#/etc/nginx/ssl/mysite.crt#/etc/letsencrypt/live/${SERVER_NAMES}/fullchain.pem#g" \
            /etc/nginx/conf.d/default.conf
        sed -i \
            -e "s#/etc/nginx/ssl/mysite.key#/etc/letsencrypt/live/${SERVER_NAMES}/privkey.pem#g" \
            /etc/nginx/conf.d/default.conf
        echo "Reloading nginx..."
        /etc/init.d/nginx reload
    else
        echo "Certbot configuration already exists"
    fi

    echo "Running certificate renew background job..."
    /renew.sh &
fi

# Bring back the primary process back into the foreground
fg %1
