FROM python:3.6-slim

# Python unbuffered so that messages appear immediately
# TODO: consider moving this to the docker-compose environment
ENV PYTHONUNBUFFERED 1

# Prepare application
RUN mkdir /code
WORKDIR /code

# Copy and install requirements
COPY requirements.txt requirements-dev.txt requirements-test.txt ./
RUN pip install -r requirements.txt && \
    pip install -r requirements-dev.txt && \
    pip install -r requirements-test.txt


# Add application source code
COPY config.py wsgi.py openapi.yaml ./
COPY app ./app
COPY migrations ./migrations

# Add entrypoints
COPY docker/app/entrypoint-server.sh docker/app/entrypoint-worker.sh /

# Flask configuration
ENV FLASK_ENV development

EXPOSE 5000
ENTRYPOINT /entrypoint-server.sh
