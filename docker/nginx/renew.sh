#!/bin/bash

while /bin/true
do
    sleep 86400  # One day
    echo "Renewing certificates..."
    certbot renew
done
