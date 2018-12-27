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

    flask db migrate -m "workspace and user models"
    flask db upgrade


Migrations on a running server need special considerations.

.. note:: TODO: add migrations on running server considerations.


Google
------

Remember that the Google Cloud Storage API must be enabled

I am currently compiling a list of the exact, minimal roles needed
for the service account on the GCP.

- ``storage.buckets.create``: to create new buckets
- ``storage.buckets.get``: to get information on existing buckets
- ``storage.buckets.delete``: to delete existing buckets
- ``storage.objects.list``: to list objects in buckets
