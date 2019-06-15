.. _`Local development server`:

========================
Local development server
========================

The following instructions assume that you have are using Linux or OSX.
For instructions under Windows, please help us by adapting them and filing
a `pull request <https://github.com/quetz-al/quetzal/pull/new/master>`_.

1. Clone the Quetzal repository:

   .. code-block:: console

    $ git clone git@github.com:quetz-al/quetzal.git

2. Install Docker_. Make sure you are able to create Docker images by following
   the `test Docker installation`_ instructions.

3. Create a virtual environment with your favorite virtual environment manager,
   but make sure it is a Python 3 environment. Then, install the requirement
   libraries:

   .. code-block:: console

    $ python3 -m venv ${HOME}/.virtualenvs/quetzal-env
    $ source ${HOME}/.virtualenvs/quetzal-env/bin/activate
    $ pip install -r requirements-dev.txt


At this point, you will need to prepare your Google Cloud Platform credentials
(if you are going to use Google buckets to save data files) and prepare SSL
certificates.


Google Cloud Platform
---------------------

Using Google buckets to save data needs some preparations described in
:ref:`GCP preparations`.
For a development server you need to follow the
:ref:`GCP project preparations`,
:ref:`GCP credential preparations` and
:ref:`GCP API preparations` instructions.

SSL
---

Quetzal uses HTTPS for all its API operations. This needs a SSL certificate
that can be generated as follows.

1. First, create a SSL key and certificate using ``openssl``:

   .. code-block:: console

    $ mkdir -p conf/ssl
    $ openssl req -x509 -newkey rsa:4096 \
      -keyout conf/ssl/mysite.key -out conf/ssl/mysite.crt \
      -days 365 -nodes

2. Optionally, but highly recommended, generate a DH exchange key prime number:

.. code-block:: console

 $ openssl dhparam -out conf/ssl/dhparam.pem 2048

Note that these are auto-signed keys and they are only suitable for a
development or testing scenario. When deploying on a production server, the
recommended approach is to use `Let's Encrypt`_  as a certificate authority and
`CertBot`_ to obtain the final, signed certificates.
However, you will still need these auto-signed keys as a temporary solution
until `CertBot`_ runs the first time.


Docker-compose
--------------

We are almost ready to have a Quetzal development server ready. This local
server runs as a multi-container application managed by docker-compose.


1. Read the configuration entries in ``config.py`` and change them
   accordingly in the ``docker-compose.yaml`` file.

   If you are going to use Google buckets to store data, follow the instructions
   concerning the `Google Cloud Platform`_ and verify the
   configuration variables with the ``QUETZAL_GCP_`` prefix.

   If you prefer saving your files locally, set the ``QUETZAL_DATA_STORAGE`` to
   ``'file'`` and ignore the instructions related to Google Cloud Platform.

2. Build your docker-compose services:

   .. code-block:: console

    $ docker-compose build

3. Run Quetzal through docker-compose:

   .. code-block:: console

    $ docker-compose up

4. If this the first time you run Quetzal, you need to setup the database,
   create some roles and users. You can do this while the server is running
   with the following script:

   .. code-block:: console

    $ docker-compose exec web ./init.sh

Usage notes
^^^^^^^^^^^

If you want to stop the Quetzal application, use:

.. code-block:: console

 $ docker-compose stop

To reset and erase the Quetzal application, use:

.. code-block:: console

 $ docker-compose down

.. warning:: Using ``docker-compose down`` will erase your database.
  You will lose your data. Use this only to reset and start a fresh Quetzal
  application.

.. _Let's Encrypt: https://letsencrypt.org/
.. _CertBot: https://certbot.eff.org/
.. _Docker: https://docs.docker.com/install/
.. _test Docker installation: https://docs.docker.com/get-started/#test-docker-installation

