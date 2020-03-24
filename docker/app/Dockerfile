################################################################################
# Multi-stage poetry python installation based on
# https://github.com/python-poetry/poetry/issues/1879#issuecomment-59213351

################################################################################
# Stage 1: python-base
#          Used as a base Python image with the environment variables set for
#          Python and poetry
FROM python:3.7-slim AS python-base

ENV \
    # Python-related environment variables
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip-related environment variables
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry-related environment variables
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.0.5 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths-related environment variables
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"
################################################################################

################################################################################
# Stage 2: builder-base
#          Used to build all dependencies. This step may need some compilation
#          tools (like build-essential), which can be quite large, but we don't
#          want to distribute an image with these temporary tools
FROM python-base AS builder-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        # deps for building python deps
        build-essential

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
#COPY config.py wsgi.py openapi.yaml init.sh README.rst ./
#COPY quetzal ./quetzal
#COPY migrations ./migrations
COPY README.rst poetry.lock pyproject.toml ./
#RUN poetry export -f requirements.txt > requirements.txt \
# && poetry export --dev -f requirements.txt > requirements-dev.txt

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN poetry install --no-dev --no-root
################################################################################

################################################################################
# Stage 4: quetzal-base
FROM python-base AS quetzal-base
WORKDIR $PYSETUP_PATH

# copy in our built poetry + venv
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# will become mountpoint of our code
WORKDIR /code
# Copy all quetzal source code except the quetzal package, so that there is
# no rebuild for each new modification
COPY migrations ./migrations
COPY config.py wsgi.py openapi.yaml init.sh pyproject.toml README.rst ./
COPY docker/app/entrypoint-server.sh docker/app/entrypoint-worker.sh /

EXPOSE 5000
ENTRYPOINT /entrypoint-server.sh

################################################################################

################################################################################
# Stage 5: development
#          Used as a development environment of the Quetzal application.
FROM quetzal-base AS development
ENV FLASK_ENV=development

# Install runtime and dev deps. This should be a bit faster because runtime deps
# were installed in hte previous stage
WORKDIR $PYSETUP_PATH
RUN poetry install --no-root

# will become mountpoint of our code
WORKDIR /code
COPY quetzal ./quetzal
################################################################################

################################################################################
# Stage 6: production
#          A leaner version of the development stage. This is the final stage
#          and it is the image that will be distributed.
FROM quetzal-base AS production
ENV FLASK_ENV=production \
    USE_GUNICORN=1

# will become mountpoint of our code
WORKDIR /code
COPY quetzal ./quetzal
################################################################################
