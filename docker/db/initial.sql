-- Default timezone
SET TIME ZONE 'UTC';

-- Create initial database
CREATE DATABASE quetzal;

-- TODO: manage permissions

-- Creation of readonly user
-- CREATE ROLE readonly_user WITH LOGIN PASSWORD 'readonly_password'
-- NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE NOREPLICATION VALID UNTIL 'infinity';

-- -- connect to the django_db to correctly configure its permissions
-- \connect django_db;
-- -- do not permit the public role to create tables
-- REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- -- do permit everything to the django user
-- GRANT ALL PRIVILEGES ON SCHEMA public TO django_dbuser;
--
-- -- TODO: after django creates its tables, change its permissions so that only
-- -- django_dbuser can read them. This is important for the auth table, for
-- -- example.
