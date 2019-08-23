=======
Backups
=======

Database
--------

When deploying Quetzal as a kubernetes application (in GCP, for example), there
is a CronJob configured to save database dumps on a bucket dedicated to backups,
once a week.

Manual backup
^^^^^^^^^^^^^

You can trigger a manual backup with kubernetes as follows:

.. code-block:: console

    # use this first command to determine CRONJOB_NAME
    kubectl get cronjobs -l app.kubernetes.io/component=database
    # then, create the job with:
    kubectl create job --from=cronjob/CRONJOB_NAME CRONJOB_NAME-manual-001


Restoring a backup
^^^^^^^^^^^^^^^^^^

The following procedure can restore one of these backups:

1. Connect to the database pod:

   .. code-block:: console

    # use this first command to determine DB_POD_NAME
    kubectl get pods -l app.kubernetes.io/component=database
    # then, connect with:
    kubectl exec -it DB_POD_NAME bash


2. Download and uncompress the backup file:

   .. code-block:: console

    gsutil cp gs://BACKUP_BUCKET/db/BACKUP_NAME.bak.gz
    gunzip BACKUP_NAME.bak


3. Make the following modifications on the ``BACKUP_NAME.bak`` file. You will
   need an editor on the pod so install one with:

   .. code-block:: console

    apt-get update && apt-get install --no-install-recommends --yes vim
    vim BACKUP_NAME.bak

   Then, comment (by adding ``--`` at the beginning of each line) the following
   lines:

   .. code-block:: sql

    CREATE ROLE dbuser;
    ALTER ROLE dbuser;
    ...
    CREATE DATABASE dbuser;

   where ``dbuser`` is the username that you had set for the database when you
   deployed quetzal to kubernetes using helm.

4. Put quetzal on maintenance mode.

   Not sure how to do this yet.

.. DANGER::

  On the following steps, you will erase your current database. Handle with care,
  because you may lose your data.

  You may want to do a `Manual backup`_ first.


5. Connect to postgres, disconnect any connection and drop the database:

   .. code-block:: console

    # First, connect to postgres but not to the quetzal database:
    psql -U$POSTGRES_USER $POSTGRES_USER

   .. code-block:: sql

    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = 'quetzak' -- change this if you changed the quetzal database name
      AND pid <> pg_backend_pid();

   .. code-block:: sql

    DROP DATABASE quetzal;  -- change this if you change the quetzal database name
    DROP DATABASE unittests;
    DROP ROLE db_user;
    DROP ROLE db_ro_user;
    exit;


6. Restore the database from the backup:

   .. code-block:: console

    psql -U$POSTGRES_USER --set ON_ERROR_STOP=on -f ./BACKUP_NAME.bak
