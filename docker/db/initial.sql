-- Default timezone
SET TIME ZONE 'UTC';

-- Create initial database
CREATE DATABASE quetzal;

-- Create unit testing database
CREATE DATABASE unittests;

-- Create a user for the application
CREATE ROLE db_user WITH LOGIN PASSWORD 'db_password';
GRANT ALL PRIVILEGES ON DATABASE quetzal TO db_user;
GRANT ALL PRIVILEGES ON DATABASE unittests TO db_user;

-- Create a readonly user for the workspace views
CREATE ROLE db_ro_user WITH LOGIN PASSWORD 'db_ro_password';

-- readonly_user permissions: only grant connect; anything else will be
-- disallowed. This is based on https://stackoverflow.com/a/762649/227103
GRANT CONNECT ON DATABASE quetzal TO db_ro_user;
GRANT CONNECT ON DATABASE unittests TO db_ro_user;
