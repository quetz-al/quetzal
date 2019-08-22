================
Deploying on GCP
================

The following instructions create a Kubernetes (k8s) cluster with a Quetzal
server running on the *staging* configuration.
Change the *sandbox-* references to *prod-* to create a production server.

We need to do perform install several components: a k8s cluster, helm, ingress, certbot
and the quetzal application.

Docker images
-------------

1. Follow the :ref:`Local development server` instructions and make sure that
   you are able to run and launch a development environment. You will need to
   activate your virtual environment.

2. Read and follow the :ref:`GCP preparations`. You will
   need to have a gcloud correctly configured, a JSON credentials file,
   and a reserved external IP address.

3. Build and upload the Docker container images to Google Container Registry.

   .. code-block:: console

    $ flask quetzal deploy create-images \
      --registry eu.gcr.io/<your-project-id>


Kubernetes cluster
------------------

1. Create a kubernetes cluster using gcloud:

   .. code-block:: console

    gcloud container clusters create quetzal-cluster \
      --num-nodes=1 \
      --enable-autoscaling --min-nodes=1 --max-nodes=4

2. Verify that the cluster is up and running:

   .. code-block:: console

    gcloud container clusters list
    NAME             LOCATION        MASTER_VERSION  MASTER_IP      MACHINE_TYPE   NODE_VERSION  NUM_NODES  STATUS
    quetzal-cluster  europe-west1-c  1.11.7-gke.4    x.x.x.x        n1-standard-1  1.11.7-gke.4  2          RUNNING

   If you need more resources, you can change the number of nodes with:

   .. code-block:: console

    gcloud container clusters resize quetzal-cluster --size N

   or change the type of VM instance type for another machine type that uses
   more CPU or memory. This procedure is out of scope of this guide, but you
   can read more at the
   `node pools documentation <https://cloud.google.com/kubernetes-engine/docs/concepts/node-pools>`_.

3. Verify that ``kubectl`` is using the correct cluster:

   .. code-block:: console

    kubectl create -f helm/rbac-config.yaml

Part 2: Helm
------------

1. Install helm. In general, follow the `installing helm guide <https://helm.sh/docs/using_helm/#installing-helm>`_.
   For the particular case of OSX (with homebrew), this can be done with:

   .. code-block:: console

    brew install kubernetes-helm

2. Install helm k8s service account. This is explained in the
   `helm installation guide <https://helm.sh/docs/using_helm/#tiller-and-role-based-access-control>`_:

   .. code-block:: console

    kubectl create -f helm/rbac-config.yaml

3. Install helm k8s resources (also known as tiller) with a service account:

   .. code-block:: console

    helm init --service-account tiller --wait

4. Verify that helm was correctly installed:

   .. code-block:: console

    helm version

    Client: &version.Version{SemVer:"v2.14.3", GitCommit:"0e7f3b6637f7af8fcfddb3d2941fcc7cbebb0085", GitTreeState:"clean"}
    Server: &version.Version{SemVer:"v2.14.3", GitCommit:"0e7f3b6637f7af8fcfddb3d2941fcc7cbebb0085", GitTreeState:"clean"}


Part 3: Ingress
---------------


1. Install ingress resources. This is a prerequisite described in
   the `ingress installation guide <https://kubernetes.github.io/ingress-nginx/deploy/#prerequisite-generic-deployment-command>`_.

   .. code-block:: console

    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/static/mandatory.yaml

2 Install ingress. If you have a static IP reserved for the Quetzal
   application, you must set it here. Otherwise, remove the
   ``--set controller.service.loadBalancerIP`` flag:

   .. code-block:: console

    helm install stable/nginx-ingress --set controller.service.loadBalancerIP=X.X.X.X --name nginx-ingress


Certbot
-------

**This part is optional.** You only need it if you want to have a signed
certificate.

1. Install certbot. This part was inspired from the
   `certbot acme nginx installation tutorial <https://docs.cert-manager.io/en/latest/tutorials/acme/quick-start/index.html>`_.

   .. code-block:: console

    # Install the cert-manager CRDs. We must do this before installing the Helm
    # chart in the next step for `release-0.9` of cert-manager:
    $ kubectl apply -f https://raw.githubusercontent.com/jetstack/cert-manager/release-0.9/deploy/manifests/00-crds.yaml

    # Create the namespace for cert-manager
    $ kubectl create namespace cert-manager

    # Label the cert-manager namespace to disable resource validation
    $ kubectl label namespace cert-manager certmanager.k8s.io/disable-validation=true

    ## Add the Jetstack Helm repository
    $ helm repo add jetstack https://charts.jetstack.io

    ## Updating the repo just incase it already existed
    $ helm repo update

    ## Install the cert-manager helm chart
    $ helm install \
      --name cert-manager \
      --namespace cert-manager \
      --version v0.9.1 \
      jetstack/cert-manager

2. Install certbot issuer

   .. code-block:: console

    kubectl create -f helm/acme-issuer.yaml


Quetzal
-------

1. Create the TLS secret that will be used for the nginx proxy.

   .. code-block:: console

    kubectl create secret tls sandbox-tls-secret \
      --cert=./conf/ssl/mysite.crt \
      --key=./conf/ssl/mysite.key

2. Create GCP credentials secret that will be used by the app to communicate
   with the GCP resources (e.g. the data buckets).

   .. code-block:: console

    kubectl create secret generic sandbox-credentials-secrets \
      --from-file=./conf/credentials.json

3. Install quetzal using helm. Give it a name (like *foo*).

   .. code-block:: console

    helm install \
      --set db.username=... \
      --set db.password=... \
      --set app.flaskSecretKey=... \
      --name foo ./helm/quetzal

4. Verify that everything is running.

   You can check that all pods are running with:

   .. code-block:: console

    kubectl get pods
    NAME                                             READY   STATUS    RESTARTS   AGE
    foo-quetzal-app-86669c8bc6-8vt9c                 0/1     Pending   0          100s
    foo-quetzal-app-86669c8bc6-dhwj6                 1/1     Running   0          10m
    foo-quetzal-app-86669c8bc6-s56wl                 0/1     Pending   0          115s
    foo-quetzal-app-86669c8bc6-w2ppm                 0/1     Pending   0          115s
    foo-quetzal-app-86669c8bc6-x5gvk                 0/1     Pending   0          115s
    foo-quetzal-db-cd68d97bc-tdj8l                   1/1     Running   0          15m
    foo-quetzal-rabbitmq-85bf9dddfd-kkvr7            1/1     Running   0          15m
    foo-quetzal-worker-5dbb8c4dfd-fg8ct              1/1     Running   0          9m41s
    foo-quetzal-worker-5dbb8c4dfd-fv6bj              1/1     Running   0          10m
    nginx-ingress-controller-84df6c4c54-2v8n4        1/1     Running   0          22m
    nginx-ingress-default-backend-7d5dd85c4c-mc89t   1/1     Running   0          22m


   Similarly, you can do the same with the services:

   .. code-block:: console

    kubectl get services
    NAME                            TYPE           CLUSTER-IP    EXTERNAL-IP     PORT(S)                      AGE
    app                             ClusterIP      10.0.11.94    <none>          5000/TCP                     16m
    db                              ClusterIP      10.0.13.162   <none>          5432/TCP                     16m
    kubernetes                      ClusterIP      10.0.0.1      <none>          443/TCP                      26m
    nginx-ingress-controller        LoadBalancer   10.0.3.187    x.x.x.x.        80:31388/TCP,443:32725/TCP   23m
    nginx-ingress-default-backend   ClusterIP      10.0.11.182   <none>          80/TCP                       23m
    rabbitmq                        ClusterIP      10.0.10.159   <none>          5672/TCP,15672/TCP           16m

   If a pod fails to start correctly, examine it with:

   .. code-block:: console

    kubectl describe pod foo-quetzal-app-7dcc756c9d-78n5w
    ... many details that can help determine the problem ...

5. Initialize the application.

   If this is the first time the application is deployed, you need to
   initialize its database, buckets and users. Connect to a web pod (like
   ``foo-quetzal-app-7dcc756c9d-78n5w``, as listed above, but this will be
   specific to your deployment) as:

   .. code-block:: console

    kubectl exec -it foo-quetzal-app-7dcc756c9d-78n5w /bin/bash

   and then run the initialization script:

   .. code-block:: console

    ./init.sh

   which will ask for an administrator password. You can add new users at
   this point with:

   .. code-block:: console

    flask quetzal user create alice alice.smith@example.com
    flask quetzal role add alice public_read public_write

6. If you installed certbot, you should verify that the certificate was
   correctly generated with:

   .. code-block:: console

    kubectl get certificates
    NAME                 READY   SECRET               AGE
    sandbox-tls-secret   True    sandbox-tls-secret   1m


   And also, the following curl command should work without any errors:

   .. code-block:: console

    curl -vL https://sandbox.quetz.al/healthz


-----

That's all, you can now explore the documentation at
https://sandbox.quetz.al/redoc, or wherever your configuration points to.
