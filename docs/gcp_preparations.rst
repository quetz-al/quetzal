==================================
Google Cloud Platform preparations
==================================

Quetzal can be deployed as a Kubernetes application on Google Cloud Platform
(GCP). To achieve this, follow this guide.

Project
=======

Create a project on the `GCP console`_. When you create a GCP project, you will
give it a unique name, its project id. In this guide, this identifier will be
referred as ``<your-project-id>``.


Most of the operations described in this guide can be done through the
`GCP console`_, a very rich web-based application to manage your cloud resources
and services. However, this guide will do all operations on the command-line
interface using ``gcloud``, because it is easier to describe.
Download and install gcloud_.

Credentials
===========

Quetzal uses and manages several GCP resources through the GCP JSON API.
This access is subject to the permissions defined by the Identity and Access
Management (IAM) component of GCP. You need to create a service account for
Quetzal and associate a list of permissions to it. In other words, you need to
setup some *credentials*. The following steps explain how to create
these credentials.

1. First, make sure that your gcloud command-line utility is correctly
   configured for your project.

   .. code-block:: console

    $ gcloud config list
    [compute]
    region = europe-west1
    zone = europe-west1-c
    [core]
    account = your.email@example.com    # << make sure this is your email...
    disable_usage_reporting = True
    project = your-project-id           # << ... and that this is your GCP project

    Your active configuration is: [default]

2. Create a service account. Note the `email` entry, which will be used later.

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

3. Create a credentials key JSON file for the service account.

   In the following code example, it is saved as ``conf/credentials.json``.

   .. code-block:: console

    $ gcloud iam service-accounts keys create \
       conf/credentials.json \
       --iam-account=quetzal-service-account@<your-organization>.iam.gserviceaccount.com

   .. important:: Anyone with this file could use your GCP resources, so this
     file should not be shared or committed to your version control system.

     Keep it secret, keep it safe.

4. Create an IAM role.

   We need to create a role that encapsulates all the permissions needed
   by the Quetzal application. These permissions are listed on the
   ``gcp_role.yaml`` file.

   .. code-block:: console

    $ gcloud iam roles create quetzal_app_role \
      --project <your-project-id> \
      --file gcp_role.yaml

5. Associate the service account to the IAM role.

   Finally, the service account created before needs to be associated with the
   permissions defined in the IAM role.

   .. code-block:: console

    $ gcloud projects add-iam-policy-binding <your-project-id> \
      --member=serviceAccount:quetzal-service-account@<your-organization>.iam.gserviceaccount.com \
      --role=projects/<your-organization>/roles/quetzal_app_role

.. _GCP console: https://console.cloud.google.com
.. _gcloud: https://cloud.google.com/sdk/
