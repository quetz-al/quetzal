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
