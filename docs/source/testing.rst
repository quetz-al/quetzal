=======
Testing
=======

For tests that prepares a docker-compose instance, runs the tests and then
discards the docker-compose services:

.. code-block:: console

  FLASK_ENV=tests pytest -o log_cli=true -o log_cli_level=DEBUG


For tests that use an existing docker-compose instance (it is your resposibility
to create it with ``docker-compose up`` and to destroy it with
``docker-compose down``):

.. code-block:: console

  FLASK_ENV=local-tests pytest -o log_cli=true -o log_cli_level=DEBUG
