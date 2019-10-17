=====================
Development use cases
=====================

Examples:

* Change behaviour of an existing API operation.
* Change the API definition.
* Change behaviour of background task.
* Cleaning and restarting the development environment.
* Change client behavior.
* Tag a new version.
* Update clients.


Create or modify a database model
=================================

This is done with SQLAlchemy. The procedure is to create a class like:

.. code-block:: python

   from quetzal.app import db


   class Foo(db.Model):
       # ... contents, according to SQLAlchemy ...
       ...


Normally, this goes into the :py:module:`quetzal.app.models` module.

You should also add it to the dictionary created in the
``make_shell_context`` function inside the :py:func:`quetzal.app.create_app`
factory function. This will automatically import the model when running
``flask shell``.

Now, proceed to the Migrations_ procedure.

Migrations
----------

Prepare a migration script
^^^^^^^^^^^^^^^^^^^^^^^^^^

When creating or modifying a database model object, you need to make a
migration script. This is done with alembic:

.. code-block:: console

   flask db migrate --rev-id ID -m MESSAGE

Here, ``ID`` is a revision identifier.
Please use ``0001``, ``0002``, ... and so on,
according to the number of the files in the ``migrations/`` directory.
``MESSAGE`` should be a short description of what the migration does.

Note that if you are running a development instance, you may need to set
some environment variables for the command above to work. For example:

.. code-block:: console

   FLASK_ENV=development DB_HOST=localhost DB_USERNAME=postgres DB_PASSWORD=pg_password flask db migrate --rev-id ID -m MESSAGE

The ``flask db migrate`` command above will create a script called
``migrations/yyyymmdd_ID_MESSAGE.py``. Read and review its contents. It is
important to remove any database modification that does not correspond to
what you have created or modified in your models. Alembic does most of the
job to create this for you, but it does make mistakes.

Apply a migration script
^^^^^^^^^^^^^^^^^^^^^^^^

Finally to *apply* your migration:

.. code-block:: console

   flask db upgrade head

Whenever there is a model database modification and you update Quetzal, you
need to run the migration script.
