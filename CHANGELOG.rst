=========
Changelog
=========

This document lists all important changes to Quetzal.

Quetzal version numbers follow `semantic versioning <http://semver.org>`_.

X.Y.Z (unreleased)
------------------

Planned:

* Better commit detection with a 3-way merge detection


0.5.0 (2019-10-17)
------------------

* Added API key authentication security scheme.
* Fixed incorrect model update on file delete.
* Added a new query dialect, ``postgresql_json``, for a Postgres SQL view where
  each family is represented as a JSONB column.


0.4.0 (2019-08-26)
------------------

* Added k8s deployment through helm.
* Removed k8s nginx in favor of ingress.
* Added certificate management through certbot's k8s application.
* Added automatic database backups using k8s cronjobs.
* Minor security issue fixed on werkzeug dependency [CVE-2019-14806]

0.3.0 (2019-07-02)
------------------

* Added GCP cluster auto-scaling.
* Added k8s horizontal scaler for web and worker.
* Added certbot for certificate management.
* Started rewrite and restructuring of documentation.
* Changed upload to systematically save into the workspace data directory.
* Changed commit to copy from workspace data directory to the data directory.
* Implemented file delete.

0.2.0 (2019-03-21)
------------------

* Refactored app as a package in ``quetzal.app``.
* Added a file storage backend, an alternative storage that does not use Google
  Cloud Platform.
* Added Let's encrypt SSL certificate management.
* Added deployment on GCP documentation.
* Added Sphinx documentation structure.
* Added file delete endpoint.
* Added file state in base metadata.
* Added a simple.naive implementation to file delete.
* Added a simple/naive workspace commit conflict detection.
* Added global queries.
* Added support for temporary files. They are uploaded on the users' bucket.
* Added path as query parameter when uploading files.
* Fixes unit tests that failed since introduction of roles.

0.1.0 (2019-03-05)
------------------

* Initial release.
* Complete API specification with OASv3.
* Flask server implementation using zalando/connexion.
* Development environment with docker-compose.
* Deployment on Google Cloud Platform with kubernetes.
