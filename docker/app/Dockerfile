FROM python:3.6-slim

# Python unbuffered so that messages appear immediately
# TODO: consider moving this to the docker-compose environment
ENV PYTHONUNBUFFERED 1

# Prepare application
RUN mkdir /code
WORKDIR /code

# Copy and install requirements
COPY requirements.txt requirements-dev.txt requirements-test.txt ./
RUN pip install -r requirements.txt
# requirements-dev.txt and requirements-test.txt are not installed but
# left in the image in case you want to install them

# Add application source code
COPY config.py wsgi.py openapi.yaml init.sh ./
COPY quetzal ./quetzal
COPY migrations ./migrations

# Add entrypoints
COPY docker/app/entrypoint-server.sh docker/app/entrypoint-worker.sh /

# Flask configuration
ENV FLASK_ENV development

# Permit version override
ARG QUETZAL_VERSION
ENV QUETZAL_VERSION ${QUETZAL_VERSION}

EXPOSE 5000
ENTRYPOINT /entrypoint-server.sh
