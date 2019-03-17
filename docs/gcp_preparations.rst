==================================
Google Cloud Platform preparations
==================================

Quetzal can be deployed as a Kubernetes application on Google Cloud Platform
(GCP). To achieve this, follow this guide.

Project
=======

1. Create a project on the `GCP console`_ by selecting `New project`_ .

   When you create a GCP project, you will give it a unique name, its project
   id. In this guide, this identifier will be referred as
   ``<your-project-id>``.

2. After creating the project, head to the `IAM & admin`_ menu to see the list
   of members of the project.

   Make sure that your email address is listed as a `project owner`.

3. Download and install gcloud_.

   Most of the operations described in this guide can be done through the
   `GCP console`_, a very rich web-based application to manage your cloud resources
   and services. However, this guide will do all operations on the command-line
   interface using ``gcloud``, because it is easier to describe.

4. Once you have installed gcloud, authenticate with the email address listed
   in step 2.

   .. code-block:: console

    $ gcloud auth login
    # ... a browser window will appear to login ...

5. Configure the default settings of the project.

   .. code-block:: console

    $ gcloud config set project <your-project-id>
    $ gcloud config set compute/zone europe-west1-c # or some other region

5. Verify your configuration.

   .. code-block:: console

    $ gcloud config list
    [compute]
    region = europe-west1
    zone = europe-west1-c
    [core]
    account = your.email@example.com    # << verify that this is your email...
    disable_usage_reporting = True
    project = <your-project-id>         # << ... and that this is your GCP project

    Your active configuration is: [default]

Credentials
===========

Quetzal uses and manages several GCP resources through the GCP JSON API.
This access is subject to the permissions defined by the Identity and Access
Management (IAM) component of GCP. You need to create a service account for
Quetzal and associate a list of permissions to it. In other words, you need to
setup some *credentials*. The following steps explain how to create
these credentials.

1. Create a service account. Note the `email` entry, which will be used later.

   .. code-block:: console

    $ gcloud iam service-accounts create quetzal-service-account \
        --display-name="Quetzal application service account" \
        --format json
    Created service account [quetzal-service-account].
    {
      "displayName": "Quetzal application service account",
      "email": "quetzal-service-account@<your-organization>.iam.gserviceaccount.com",
      ...
    }

2. Create a credentials key JSON file for the service account.

   In the following code example, it is saved as ``conf/credentials.json``.

   .. code-block:: console

    $ gcloud iam service-accounts keys create \
       conf/credentials.json \
       --iam-account=quetzal-service-account@<your-organization>.iam.gserviceaccount.com

   .. important:: Anyone with this file could use your GCP resources, so this
     file should not be shared or committed to your version control system.

     Keep it secret, keep it safe.

3. Create an IAM role.

   We need to create a role that encapsulates all the permissions needed
   by the Quetzal application. These permissions are listed on the
   ``gcp_role.yaml`` file.

   .. code-block:: console

    $ gcloud iam roles create quetzal_app_role \
      --project <your-project-id> \
      --file gcp_role.yaml

4. Associate the service account to the IAM role.

   Finally, the service account created before needs to be associated with the
   permissions defined in the IAM role.

   .. code-block:: console

    $ gcloud projects add-iam-policy-binding <your-project-id> \
      --member=serviceAccount:quetzal-service-account@<your-organization>.iam.gserviceaccount.com \
      --role=projects/<your-organization>/roles/quetzal_app_role

APIs
====

Quetzal uses several GCP services through their APIs. You need the enable the
following APIs on `GCP API library`_:

* Cloud Storage, used to store all files in Quetzal.
* Kubernetes Engine API, used to create a Kubernetes cluster that hosts the
  Quetzal services.

Docker & Kubernetes
===================

Quetzal uses Docker images and the Google Container Registry (GCR).

1. Install Docker_. Make sure you are able to create Docker images by following
   the `test Docker installation`_ instructions.

2. Use gcloud to configure a Docker registry. This will enable Docker to push
   images to GCR.

   .. code-block:: console

    $ gcloud auth configure-docker

3. Finally, install the kubernetes client:

   .. code-block:: console

     $ gcloud components install kubectl


IP address reservation
======================

This step is optional. When deploying Quetzal, you might want to associate it
to some fixed IP address (in order to associate it in your DNS records). You
can reserve one IP as follows:

.. code-block:: console

  $ gcloud compute addresses create quetzal-stage-server-ip \
   --description="Quetzal server external IP" \
   --global --network-tier=PREMIUM


.. _GCP console: https://console.cloud.google.com
.. _New project: https://console.cloud.google.com/projectcreate
.. _IAM & admin: https://console.cloud.google.com/iam-admin/iam
.. _GCP API library: https://console.cloud.google.com/apis/library
.. _gcloud: https://cloud.google.com/sdk/
.. _Docker: https://docs.docker.com/install/
.. _test Docker installation: https://docs.docker.com/get-started/#test-docker-installation
