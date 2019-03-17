Deploying on GCP
================

The following instructions create a Kubernetes (k8s) cluster with a Quetzal
server running on the *staging* configuration.
Change the *stage-* references to *prod-* to create a production server.

Part 1: GCP Preparations
------------------------

1. Follow the :ref:`Local development server` instructions and make sure that
   you are able to run and launch a development environment. You will need to
   activate your virtual environment.

2. Read and follow the :ref:`Google Cloud Platform preparations`. You will
   need to have a gcloud correctly configured, a JSON credentials file,
   and a reserved external IP address.

3. Build and upload the Docker container images to Google Container Registry.

   .. code-block:: console

    $ flask quetzal deploy create-images \
      --registry gcr.io/<your-project-id>


Part 2: GCP Deployment
----------------------

1. Create k8s cluster.

   .. code-block:: console

    $ gcloud container clusters create quetzal-cluster \
      --num-nodes=4

   This will create 4 Google Compute Engine VM instances that will be used as
   CPU and memory resources managed by k8s. The VM machine type in this example
   is the default `n1-standard-1`_, as shown by:

   .. code-block:: console

    $ gcloud container clusters list
    NAME             LOCATION        MASTER_VERSION  MASTER_IP      MACHINE_TYPE   NODE_VERSION  NUM_NODES  STATUS
    quetzal-cluster  europe-west1-c  1.11.7-gke.4    x.x.x.x        n1-standard-1  1.11.7-gke.4  2          RUNNING

   If you need more resources, you can change the number of nodes with:

   .. code-block:: console

    $ gcloud container clusters resize quetzal-cluster --size N

   or change the type of VM instance type for another machine type that uses
   more CPU or memory. This procedure is out of scope of this guide, but you
   can read more at the
   `node pools documentation <https://cloud.google.com/kubernetes-engine/docs/concepts/node-pools>`_.

2. Create k8s secrets.

   Quetzal uses several services that need some configuration values that are
   sensitive and should be protected. These values are saved as `k8s secrets`_.

   There are three secrets to create:

   * Database secrets

   .. code-block:: console

     # Generate a random password for the database user.
     # Note it down. Keep it secret, keep it safe.
     $ flask quetzal utils generate-secret-key 8
     YRADKSrPzlM

     # Use <your db password> on the following command:
     $ kubectl create secret generic stage-db-secrets \
       --from-literal=username=postgres \
       --from-literal=password=<your db password>

   * Proxy (nginx) SSL secrets

   .. code-block::

      # Create nginx secrets with the following command:
      $ kubectl create secret generic stage-nginx-secrets \
        --from-file=./conf/ssl/dhparam.pem \
        --from-file=./conf/ssl/mysite.crt \
        --from-file=./conf/ssl/mysite.key

   * Application secrets

   .. code-block:: console

     # Generate a secret key for the Flask application.
     # Note it down. Keep it secret, keep it safe.
     $ flask quetzal utils generate-secret-key
     sB-YgPO8ZVCmZyV5XKH0rg

     # Use <your secret key> and <your db password> on the following command:
     $ kubectl create secret generic stage-app-secrets \
       --from-file=./conf/credentials.json \
       --from-literal=SECRET_KEY=<your secret key> \
       --from-literal=DB_USERNAME=postgres \
       --from-literal=DB_PASSWORD=<your db password>

3. Read, verify and modify kubernetes deployment files.

   Check every yaml file that will be used on the next step for potential
   changes needed for your case. For example, if you are deploying a
   production server, make sure that you are not referring to a staging
   resource.

   Check that all ``-deployment.yaml`` files point to the versions of the
   images that you want.

   An important thing to check is if ``db-deployment.yaml`` is using the
   correct disk that you created before:

   .. code-block:: yaml

     ...
     volumes:
       - name: db-data-volume
         gcePersistentDisk:
           pdName: quetzal-stage-db-volume
           fsType: ext4
     ...

   Another important thing to check is the environment variables of the
   ``web-deployment.yaml`` *and* ``worker-deployment.yaml``. Verify that
   their ``SERVER_NAME`` and ``FLASK_ENV`` are correct.

   Finally, verify that the ``nginx-service.yaml`` has the correct external
   IP created before:

   .. code-block:: yaml

     ...
     spec:
       type: LoadBalancer
       loadBalancerIP: 34.76.151.30
     ...

4. Create k8s deployments and services

   The following commands create deployments (pods) and services. After each
   create command, you can verify its status with
   ``kubectl get pod <pod_name>`` or ``kubectl get service <service_name>``.
   Read the next step for more details on how to diagnose problems.

   .. code-block:: console


    $ kubectl create -f k8s/rabbitmq-deployment.yaml
    $ kubectl create -f k8s/rabbitmq-service.yaml

    $ kubectl create -f k8s/db-deployment.yaml
    $ kubectl create -f k8s/db-service.yaml

    $ kubectl create -f k8s/web-deployment.yaml
    $ kubectl create -f k8s/web-service.yaml

    $ kubectl create -f k8s/worker-deployment.yaml

    $ kubectl create -f k8s/nginx-deployment.yaml
    $ kubectl create -f k8s/nginx-service.yaml

5. Verify that everything is running

   You can check that all pods are running with:

   .. code-block:: console

    $ kubectl get pods
    NAME                                   READY     STATUS    RESTARTS   AGE
    db-deployment-5595d68bf9-jmnqd         1/1       Running   0          3m
    nginx-deployment-f4b44b586-7v5mg       1/1       Running   0          12s
    rabbitmq-deployment-7fb8d675c4-58654   1/1       Running   0          3m
    web-deployment-7dcc756c9d-78n5w        1/1       Running   0          2m
    web-deployment-7dcc756c9d-7rsmc        1/1       Running   0          2m
    web-deployment-7dcc756c9d-cjf2k        1/1       Running   0          2m
    worker-deployment-6c57d9d7c-98htm      1/1       Running   0          25s

   Similarly, you can do the same with the services:

   .. code-block:: console

    $ kubectl get services
    NAME         TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)                      AGE
    db           ClusterIP      10.27.247.154   <none>         5432/TCP                     5m
    kubernetes   ClusterIP      10.27.240.1     <none>         443/TCP                      33m
    nginx        LoadBalancer   10.27.249.146   34.76.151.30   80:31842/TCP,443:30919/TCP   2m
    rabbitmq     ClusterIP      10.27.255.80    <none>         5672/TCP,15672/TCP           5m
    web          ClusterIP      10.27.240.128   <none>         5000/TCP                     2m

   If a pod fails to start correctly, examine it with:

   .. code-block:: console

    $ kubectl describe pod web-deployment-7dcc756c9d-78n5w
    ... many details that can help determine the problem ...

6. Initialize the application.

   If this is the first time the application is deployed, you need to
   initialize its database, buckets and users. Connect to a web pod (like
   ``web-deployment-7dcc756c9d-78n5w``, as listed above, but this will be
   specific to your deployment) as:

   .. code-block:: console

    $ kubectl exec -it web-deployment-7dcc756c9d-78n5w /bin/bash

   and then run the initialization script:

   .. code-block:: console

    $ ./init.sh

   which will ask for an administrator password. You can add new users at
   this point with:

   .. code-block:: console

    $ flask quetzal user create alice alice.smith@example.com
    $ flask quetzal role add alice public_read public_write


7. That's all, you can now explore the documentation at
   https://stage.quetz.al/redoc. Or wherever your configuration points to.

.. _gcloud: https://cloud.google.com/sdk/gcloud/
.. _n1-standard-1: https://cloud.google.com/compute/docs/machine-types
.. _k8s secrets: https://kubernetes.io/docs/concepts/configuration/secret/
