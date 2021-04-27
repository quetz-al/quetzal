## Quetzal deployment instructions on GCP

1. create a dedicated GCP project
2. enable the GKE api on the project   
3. Create a GKE cluster with the following specs: 
    * zonal on europe-west-1-c
    * 3 n1-standard-1 nodes
4. install nginx ingress controller: 
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/cloud/deploy.yaml
```
5. find the external IP of the ingress Load Balancer.
```
k get service -n ingress-nginx
```   
Add a DNS A record to that IP for the domain you plan to use.

5. install cert manager
```
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.2.0/cert-manager.yaml
```
```
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
 name: letsencrypt-issuer
spec:
 acme:
   server:  https://acme-v02.api.letsencrypt.org/directory
   email: florent@omind.me
   privateKeySecretRef:
     name: letsencrypt-certificate-secrets
   solvers:
   - http01:
       ingress:
         class:  nginx
EOF
```


6. create a quetzal GCP role with the following permissions:
   * storage.buckets.create
   * storage.buckets.delete
   * storage.buckets.get
   * storage.objects.create
   * storage.objects.delete
   * storage.objects.list

7. create a quetzal GCP service account
   
   a. bind it to the previously created role
   b. create a GCP JSON key for this service account
   c. in https://www.google.com/webmasters/verification/home, add this service account as an owner of the domain you plan to use (omind.me ?)
   
8. rename the gcp token key "credentials.json" and create a secret with it: 
```
kubectl create secret generic production-credentials-secrets --from-file /path/to/file/credentials.json
```

9. give the compute service account ( <projectId>-compute@developer.gserviceaccount.com) from the newly created project rights to pull docker images from quetzal-omind project: 

* go to iam and admin and add this service account with role "Container Registry Service Agent"

10. Setup a cloudsql database: 
* PostgreSQL 11
* only private IP database
* same VPC as your kubernetes cluster
* same zone as your kubernetes cluster
* highly available if needed (for prod for example)
* Enable backups

12. edit the helm chart in this repo to make sure the params are set up correctly:

a. ./helm/quetzal/values-<your-env>.yaml


13. Install the helm chart
```
helm upgrade quetzal quetzal --values ./quetzal/values.yaml --values ./quetzal/values--<your-env>.yaml
```

14. Init database, buckets etc...

  a. exec into the quetzal-app pod : ```kubectl exec -ti quetzal-app-xxxxx -- bash```
  b. run ```./init.sh```
  c. add an api key and associate is with an admin ```flask quetzal keys add admin```
  d. to add users, run the following commands : 
```
flask quetzal user create ${USERNAME} ${USER_EMAIL}
flask quetzal role add ${USERNAME} public_read public_write public_commit
```


15. Optional : Backup data bucket
1- create a backup bucket (for example data-backups.myenv.quetzal.omind.me)
2- Use the Data Transfer cloud service to sync your data bucket with the backup data bucket