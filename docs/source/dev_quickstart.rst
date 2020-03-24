==========
Quickstart
==========

To get a quick development environment follow these steps:

1. Install `poetry <https://python-poetry.org/docs/#installation>`_,
   `Docker <https://docs.docker.com/install/>`_, and
   `docker-compose <https://docs.docker.com/compose/install/>`_
   (usually docker-compose is already included by Docker).

2. Clone a local copy of Quetzal:

   .. code-block:: console

    git clone git@github.com:quetz-al/quetzal.git

3. Create a virtual environment and install Quetzal:

   .. code-block:: console

    cd quetzal
    poetry install

4. For an environment based on docker-compose, build the Docker images:

   .. code-block:: console

    docker-compose build

5. At this point you can get a local Quetzal server that saves files in a local
   filesystem. Launch it with:

   .. code-block:: console

    docker-compose up

6. For a server that runs outside the docker-compose environment (for
   development or testing purposes), modify the ``config.py``
   file according to your needs (in particular the hostnames to the database or
   the rabbit queue) and launch a server with:

   .. code-block:: console

    FLASK_ENV=local-tests flask run --host 0.0.0.0 --port 5000


=============
Cloud storage
=============

Take the development environment to the next step by using cloud storage to
store data... (description on how to do this coming soon).
