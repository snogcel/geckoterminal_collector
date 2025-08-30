-- Database initialization script for PostgreSQL
-- This script sets up the initial database schema and configuration

-- Create database if it doesn't exist (this is handled by Docker)
-- CREATE DATABASE gecko_data;

-- Connect to the database
\c gecko_data;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS gecko;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Set default schema
SET search_path TO gecko, public;

-- Create custom types
DO $$ BEGIN
    CREATE TYPE collection_status AS ENUM ('pending', 'running', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for performance
-- These will be created by the application's migration system
-- but we can prepare some basic ones

-- Function to create indexes if they don't exist
CREATE OR REPLACE FUNCTION create_index_if_not_exists(index_name text, table_name text, columns text)
RETURNS void AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = index_name
    ) THEN
        EXECUTE format('CREATE INDEX %I ON %I (%s)', index_name, table_name, columns);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create monitoring tables
CREATE TABLE IF NOT EXISTS monitoring.system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    labels JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monitoring.collection_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collector_type VARCHAR(50) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    status collection_status DEFAULT 'pending',
    records_collected INTEGER DEFAULT 0,
    errors TEXT[],
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create performance indexes
SELECT create_index_if_not_exists('idx_system_metrics_timestamp', 'monitoring.system_metrics', 'timestamp DESC');
SELECT create_index_if_not_exists('idx_system_metrics_name', 'monitoring.system_metrics', 'metric_name');
SELECT create_index_if_not_exists('idx_collection_runs_type', 'monitoring.collection_runs', 'collector_type');
SELECT create_index_if_not_exists('idx_collection_runs_start_time', 'monitoring.collection_runs', 'start_time DESC');
SELECT create_index_if_not_exists('idx_collection_runs_status', 'monitoring.collection_runs', 'status');

-- Create maintenance functions
CREATE OR REPLACE FUNCTION monitoring.cleanup_old_metrics(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM monitoring.system_metrics 
    WHERE timestamp < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION monitoring.cleanup_old_collection_runs(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM monitoring.collection_runs 
    WHERE start_time < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create user for application (if not exists)
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gecko_app') THEN
        CREATE ROLE gecko_app WITH LOGIN PASSWORD 'gecko_app_password';
    END IF;
END $$;

-- Grant permissions
GRANT USAGE ON SCHEMA gecko TO gecko_app;
GRANT USAGE ON SCHEMA monitoring TO gecko_app;
GRANT CREATE ON SCHEMA gecko TO gecko_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gecko TO gecko_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA monitoring TO gecko_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gecko TO gecko_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA monitoring TO gecko_app;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA gecko GRANT ALL ON TABLES TO gecko_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA monitoring GRANT ALL ON TABLES TO gecko_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA gecko GRANT ALL ON SEQUENCES TO gecko_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA monitoring GRANT ALL ON SEQUENCES TO gecko_app;

-- Create maintenance schedule (requires pg_cron extension)
-- This is optional and requires the pg_cron extension to be installed
-- SELECT cron.schedule('cleanup-metrics', '0 2 * * *', 'SELECT monitoring.cleanup_old_metrics(30);');
-- SELECT cron.schedule('cleanup-collection-runs', '0 3 * * *', 'SELECT monitoring.cleanup_old_collection_runs(90);');

-- Log initialization
INSERT INTO monitoring.system_metrics (metric_name, metric_value, labels)
VALUES ('database_initialized', 1, '{"component": "database", "action": "initialization"}');

-- Display initialization summary
\echo 'Database initialization completed successfully'
\echo 'Schemas created: gecko, monitoring'
\echo 'User created: gecko_app'
\echo 'Monitoring tables created'
\echo 'Maintenance functions created'