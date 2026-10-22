#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<'SQL'
\getenv live_password LIVE_DB_PASSWORD
\getenv test_password TEST_DB_PASSWORD
\getenv root_password POSTGRES_PASSWORD
SELECT 'CREATE ROLE attendance_live LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='attendance_live') \gexec
SELECT 'CREATE ROLE attendance_test LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='attendance_test') \gexec
ALTER ROLE attendance_live PASSWORD :'live_password';
ALTER ROLE attendance_test PASSWORD :'test_password';
ALTER ROLE postgres PASSWORD :'root_password';
SELECT 'CREATE DATABASE attendance_live OWNER attendance_live' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='attendance_live') \gexec
SELECT 'CREATE DATABASE attendance_test OWNER attendance_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='attendance_test') \gexec
REVOKE ALL ON DATABASE attendance_live FROM PUBLIC;
REVOKE ALL ON DATABASE attendance_test FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE attendance_live TO attendance_live;
GRANT CONNECT, TEMPORARY ON DATABASE attendance_test TO attendance_test;
SQL
