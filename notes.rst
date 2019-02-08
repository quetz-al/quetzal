===================
Documentation notes
===================

Things that need documentation
==============================

Quickstart
----------

To get the code running (needs some conf files though):

.. code:: shell

    docker-compose up
    # in another console:
    docker-compose exec web flask db upgrade head
    docker-compose exec web flask users create admin youremail@example.com --password secret

Also useful: put the ``local.quetz.al`` hostname in your ``/etc/hosts`` file:

.. code::

    127.0.0.1       localhost local.quetz.al


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
- ``storage.objects.delete``: to delete objects in buckets


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

Logging under unit tests is controlled on three places:

1. Through the configuration object ``TestConfig`` and ``LocalTestConfig``.
   This actually reduces some logging of other libraries but does not configure
   anything because this is delegated to pytest. Remember to set one or the
   other with the ``FLASK_ENV`` environment variable.

   Use this for fine-tuning which logger should be enabled/disabled.

2. Through pytest configuration in ``pytest.ini``. This is where the format
   and level is set.

3. Using the command line arguments, which is recommended to change the
   logging level as needed without changing the ini file::

      FLASK_ENV=local-tests pytest --log-level DEBUG pytest


Others
------

* Currently, the upload file endpoint that accepts the file contents and
  metadata cannot be implemented without fixing some major problems. For example,
  a request like::

    curl -X POST \
      http://localhost:5000/api/data/workspaces/2/files/ \
      -H 'Content-Type: multipart/form-data' \
      -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
      -F profileImage=@/Users/david/devel/quetzal/random-small.bin \
      -F 'id=123e4567-e89b-12d3-a456-426655440000;type=text/plain' \
      -F 'address={"street":"red","city":"nyc"};type=application/json'

  with a correponding API specification as::

    post:
      summary: Add a new file
      description: |-
        Upload a new file by sending its contents. The file will not have any
        additional metadata associated to it.
      tags:
        - data
      operationId: app.api.data.file.create
      requestBody:
        content:
          multipart/form-data: # Media type
            schema:            # Request payload
              type: object
              properties:      # Request parts
                id:            # Part 1 (string value)
                  type: string
                  format: uuid
                address:       # Part 2 (object)
                  type: object
                  properties:
                    street:
                      type: string
                    city:
                      type: string
                profileImage:  # Part 3 (an image)
                  type: string
                  format: binary

  will **not** work, complaining that the address is not an object (because it
  is parsed as a string).

  Moreover, if we removed the object in that example, connexion does not work
  well with formData on OAS 3.

  Fixing this requires a tremendous amount of work:

  * I don't think any WSGI implements the correct parsing for multipart/form-data
    requests. We cannot send a application/json inside the form data because the
    request parser (on the WSGI code) parses it as string and does not convert it
    to a dictionary.

  * The problem above could be solved if connexion handled the str to dict
    conversion but it would need more research on how to obtain the part header,
    where the content-type for the specific part is set.

  * An alternative would be to have a specific body validator in connexion that
    does a specific verification and conversion for the case of creating files.
    This is the most feasible solution, but it may open the door to weird
    unknown bugs or security problems. Perhaps we can explore this later.
