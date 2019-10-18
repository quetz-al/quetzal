FROM postgres:11

COPY initial.sql /docker-entrypoint-initdb.d/initial.sql
COPY postgresql.conf /etc/postgresql

# Install gcloud to manage backups
RUN apt-get update && \
  apt-get install -y apt-transport-https gnupg curl lsb-release && \
  export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" && \
  echo "cloud SDK repo: $CLOUD_SDK_REPO" && \
  echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
  curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
  apt-get update -y && \
  apt-get install google-cloud-sdk -y && \
  rm -rf /var/lib/apt/lists/*

ADD backup.sh /backup.sh
RUN chmod 0755 /backup.sh

# Add the log directory and set the correct permissions
RUN mkdir -p /var/log/postgres && \
  chmod 0700 /var/log/postgres && \
  chown postgres:postgres /var/log/postgres

