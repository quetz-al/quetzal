===================
Documentation notes
===================

Things that need documentation
==============================

Database
--------

Changes on the models need an update through the migration system. This is
achieved through the ``flask db`` command. Please set a meaningful migration
name:

.. code:: shell

    flask db migrate -m "workspace model"
    flask db upgrade


Migrations on a running server need special considerations.

.. note:: TODO: add migrations on running server considerations.


It seems that one can apply the migrations to _HEAD_ as follows::

   flask db upgrade head


Google
------

Remember that the Google Cloud Storage API must be enabled

I am currently compiling a list of the exact, minimal roles needed
for the service account on the GCP.

- ``storage.buckets.create``: to create new buckets
- ``storage.buckets.get``: to get information on existing buckets
- ``storage.buckets.delete``: to delete existing buckets
- ``storage.objects.list``: to list objects in buckets
- ``storage.objects.create``: to upload objects in buckets


Metadata
--------

Convention: version 0 is the beginning for any family and there is nothing in it.


Logging
-------

* Application has detailed logs on ``./logs/quetzal.log``.
* The worker has a detailed logs on ``./logs/worker.log``.
* Database has detailed logs on ``./logs/postgres-...``
* The unit test logs are in ``./logs/quetzal-unittests.log``


Unit tests
----------

Unit tests can be run from docker-compose as follows::

  docker-compose run unittests

Run coverage with::

  pytest --cov=. .

