FROM postgres:11

COPY initial.sql /docker-entrypoint-initdb.d/initial.sql
COPY postgresql.conf /etc/postgresql
