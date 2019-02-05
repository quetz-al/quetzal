FROM nginx

COPY nginx_extras.conf /etc/nginx/conf.d/extras.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY mysite.crt /etc/nginx/ssl/mysite.crt
COPY mysite.key /etc/nginx/ssl/mysite.key
COPY dhparam.pem /etc/nginx/ssl/dhparam.pem

# Use this command to get a verbose nginx
# CMD ["nginx-debug", "-g", "daemon off;"]
