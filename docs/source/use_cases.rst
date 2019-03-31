=========
Use cases
=========

Basic queries
-------------

Downloading files
-----------------

Downloading metadata
--------------------

Uploading files
---------------

Uploading metadata
------------------

.. tabs::

   .. tab:: Quetzal Client CLI

      .. code-block:: console

       $ quetzal-client foo

   .. tab:: Python

      .. code-block:: python

       import quetzal.client
       client = quetzal.client.Client()
       client.foo()

   .. tab:: cURL

      .. code-block:: console

       $ curl -X POST https://api.quetz.al/api/v1/data/workspaces/
