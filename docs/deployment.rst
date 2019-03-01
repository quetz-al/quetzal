Deploying on GCP
================

General instructions

1. Install gcloud
2. Configure gcloud
3. Build and upload images
4. Create database disk
5. Create kubernetes cluster
6. Create kubernetes secrets

   * database secrets

   .. code-block:: console

     # Generate a random password for the database user.
     # Note it down. Keep it secret, keep it safe.
     $ flask deploy generate-secret-key 8
     YRADKSrPzlM

     # Use <your db password> on the following command:
     $ kubectl create secret generic dev-db-secrets \
       --from-literal=username=postgres \
       --from-literal=password=<your db password>

   * nginx ssl secrets

   .. code-block::

      # Create nginx secrets with the following command:
      $ kubectl create secret generic dev-nginx-secrets \
        --from-file=./conf/ssl/dhparam.pem \
        --from-file=./conf/ssl/mysite.crt \
        --from-file=./conf/ssl/mysite.key

   * application secrets

   .. code-block:: console

     # Generate a secret key for the Flask application.
     # Note it down. Keep it secret, keep it safe.
     $ flask deploy generate-secret-key
     sB-YgPO8ZVCmZyV5XKH0rg

     # Use <your secret key> and <your db password> on the following command:
     $ kubectl create secret generic dev-app-secrets \
       --from-file=./conf/credentials.json \
       --from-literal=SECRET_KEY=<your secret key> \
       --from-literal=DB_USERNAME=postgres \
       --from-literal=DB_PASSWORD=<your db password>

7. Create k8s deployments and services

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
