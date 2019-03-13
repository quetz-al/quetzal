FROM nginx:1.15.9

# Add packages needed for certbot
RUN echo "deb http://deb.debian.org/debian stretch-backports main" \
    > /etc/apt/sources.list.d/stretch-backports.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends certbot python-certbot-nginx -t stretch-backports \
    && rm -rf /var/lib/apt/lists/*

COPY nginx_extras.conf /etc/nginx/conf.d/extras.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /
COPY genconf.sh /
COPY renew.sh /

ENTRYPOINT /entrypoint.sh

# Commented in favor of a volume-based or secret file-based approach
#COPY mysite.crt /etc/nginx/ssl/mysite.crt
#COPY mysite.key /etc/nginx/ssl/mysite.key
#COPY dhparam.pem /etc/nginx/ssl/dhparam.pem

# Use this command to get a verbose nginx
# CMD ["nginx-debug", "-g", "daemon off;"]
