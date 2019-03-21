=========
Changelog
=========

This document lists all important changes to Quetzal.

Quetzal version numbers follow `semantic versioning <http://semver.org>`_.

0.2.0 (not released yet)
------------------------

* Refactored app as a package in ``quetzal.app``.
* Added a file storage backend, an alternative storage that does not use Google
  Cloud Platform.
* Added Let's encrypt SSL certificate management.
* Added deployment on GCP documentation.
* Added Sphinx documentation structure.
* Added file delete endpoint.
* Added file state in base metadata.
* Added a simple/naive workspace commit conflict detection.
* Added global queries.
* Added support for temporary files. They are uploaded on the users' bucket.
* Added path as query parameter when uploading files.

0.1.0 (2019-03-05)
------------------

* Initial release.
* Complete API specification with OASv3.
* Flask server implementation using zalando/connexion.
* Development environment with docker-compose.
* Deployment on Google Cloud Platform with kubernetes.
