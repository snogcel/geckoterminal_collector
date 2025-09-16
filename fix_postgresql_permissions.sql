-- Fix PostgreSQL permissions for gecko_collector user
-- Run this as the postgres superuser

-- Connect to the gecko_terminal_collector database
\c gecko_terminal_collector;

-- Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE gecko_terminal_collector TO gecko_collector;

-- Grant usage and create on public schema
GRANT USAGE ON SCHEMA public TO gecko_collector;
GRANT CREATE ON SCHEMA public TO gecko_collector;

-- Grant all privileges on all existing tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gecko_collector;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gecko_collector;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO gecko_collector;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO gecko_collector;

-- Make gecko_collector owner of the database (optional but recommended)
ALTER DATABASE gecko_terminal_collector OWNER TO gecko_collector;

-- Verify permissions
SELECT 
    schemaname,
    tablename,
    tableowner,
    hasinsert,
    hasselect,
    hasupdate,
    hasdelete
FROM pg_tables 
WHERE schemaname = 'public';

-- Show current user privileges
\du gecko_collector

SELECT 'Permissions fixed successfully!' as status;