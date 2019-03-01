Deploying on GCP
================

The following instructions create a cluster with a Quetzal server running
on the *staging* configuration. Change the *stage-* references to *prod-* to
create a production server.

Part 1: Requisites
------------------

1. Install gcloud_.

2. Configure gcloud.

   .. code-block:: console

    $ gcloud config set project <your project id>
    $ gcloud config set compute/zone europe-west1-c # or some other region

   Where ``<your project id>`` is the project ID on your Google Cloud Platform.

   Also, configure the gcloud and Docker configuration:

   .. code-block:: console

    $ gcloud auth configure-docker

   Finally, install the kubernetes client:

   .. code-block:: console

     $ gcloud components install kubectl

3. Reserve an external IP **if you have not reserved one yet.**.

   .. code-block:: console

    $ gcloud compute addresses create quetzal-stage-server-ip \
      --description="Quetzal stage server external IP" \
      --global --network-tier=PREMIUM

   Write down this IP address for later.

3. Build and upload the Docker container images to Google Container Registry.

   .. code-block:: console

    $ flask quetzal deploy create-images \
      --registry gcr.io/<your project id>

4. Create database disk.

   We need a persistent disk for the database, but I don't know how to do this
   automatically with kubernetes, volume claims and persistent volume claims.
   For the moment, we need to do this manually.

   First, create a Google Compute Engine Disk

   .. code-block:: console

    $ gcloud compute disks create --size=200GB quetzal-stage-db-volume

   Then, start a temporary virtual machine to format it:

   .. code-block:: console

    $ gcloud compute instances create formatter-instance \
      --machine-type "n1-standard-1" \
      --disk "name=quetzal-stage-db-volume,device-name=quetzal-stage-db-volume,mode=rw,boot=no" \
      --image "ubuntu-1604-xenial-v20170811" --image-project "ubuntu-os-cloud" \
      --boot-disk-size "10" --boot-disk-type "pd-standard" \
      --boot-disk-device-name "formatter-instance-boot-disk"

   You can safely ignore any warnings concerning the disk size, they concern
   the virtual machine boot disk, not the database disk.

   Now, connect to the formatter instance with:

   .. code-block:: console

    $ gcloud compute ssh formatter-instance

   And run the following commands **inside that virtual machine**:

   .. code-block:: console

    # Find out where the disks are attached
    $ sudo lsblk
    NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
    sdb      8:16   0  200G  0 disk             ## << this is our disk
    sda      8:0    0   10G  0 disk
    `-sda1   8:1    0   10G  0 part /

    # Then this command to format the disk:
    # sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/[DEVICE_ID]
    # In this example:
    $ sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb

    # We are done
    logout

   Finally, delete the instance to detach the disk and delete that temporary
   virtual machine:

   .. code-block:: console

    $ gcloud compute instances delete formatter-instance

Part 2: Deployment
------------------

1. Create kubernetes cluster

   .. code-block:: console

    $ gcloud container clusters create quetzal-stage-cluster --num-nodes=4

2. Create kubernetes secrets

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

   * Proxy (nginx) ssl secrets

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
   https://staging.quetz.al/redoc. Or wherever your configuration points to.

.. _gcloud: https://cloud.google.com/sdk/gcloud/
