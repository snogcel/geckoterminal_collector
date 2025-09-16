-- PostgreSQL Database Setup for Gecko Terminal Collector
-- Run this script as the postgres superuser

-- Create the database
CREATE DATABASE gecko_terminal_collector;

-- Create the user
CREATE USER gecko_collector WITH PASSWORD '12345678!';

-- Grant privileges on the database
GRANT ALL PRIVILEGES ON DATABASE gecko_terminal_collector TO gecko_collector;

-- Connect to the new database
\c gecko_terminal_collector;

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO gecko_collector;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gecko_collector;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gecko_collector;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO gecko_collector;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO gecko_collector;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Performance optimizations
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- Reload configuration
SELECT pg_reload_conf();

-- Show database info
SELECT 'Database created successfully!' as status;
SELECT current_database() as database_name;
SELECT current_user as current_user;