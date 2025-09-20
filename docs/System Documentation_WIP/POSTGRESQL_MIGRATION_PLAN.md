# PostgreSQL Migration Plan

## Overview

This document outlines the complete migration process from SQLite to PostgreSQL for the Gecko Terminal Collector system.

## Prerequisites

- [x] Local PostgreSQL instance running
- [x] Database lock optimizations implemented
- [X] PostgreSQL database created
- [ ] Migration scripts prepared
- [ ] Data validation tools ready

## Phase 1: PostgreSQL Setup and Configuration

### 1.1 Database Creation

```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE gecko_terminal_collector;
CREATE USER gecko_collector WITH PASSWORD '12345678!';
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
```

### 1.2 PostgreSQL Optimizations

```sql
-- Performance optimizations for the gecko_terminal_collector database
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
```

## Phase 2: Schema Migration

### 2.1 Create PostgreSQL-Optimized Schema

The schema will be created with PostgreSQL-specific optimizations:
- Proper indexing strategy
- Partitioning for large tables (trades, ohlcv_data)
- Constraints and foreign keys
- Optimized data types


# Tables do not exist yet.

### 2.2 Index Strategy

```sql
-- Primary indexes (created automatically with primary keys)
-- Additional performance indexes:

-- Pools table
CREATE INDEX CONCURRENTLY idx_pools_dex_id ON pools(dex_id);
CREATE INDEX CONCURRENTLY idx_pools_discovery_source ON pools(discovery_source);
CREATE INDEX CONCURRENTLY idx_pools_collection_priority ON pools(collection_priority);
CREATE INDEX CONCURRENTLY idx_pools_activity_score ON pools(activity_score DESC) WHERE activity_score IS NOT NULL;

-- Trades table (will be partitioned)
CREATE INDEX CONCURRENTLY idx_trades_pool_id ON trades(pool_id);
CREATE INDEX CONCURRENTLY idx_trades_block_timestamp ON trades(block_timestamp DESC);
CREATE INDEX CONCURRENTLY idx_trades_volume_usd ON trades(volume_usd DESC) WHERE volume_usd > 0;

-- OHLCV data table (will be partitioned)
CREATE INDEX CONCURRENTLY idx_ohlcv_pool_timeframe ON ohlcv_data(pool_id, timeframe);
CREATE INDEX CONCURRENTLY idx_ohlcv_datetime ON ohlcv_data(datetime DESC);

-- Tokens table
CREATE INDEX CONCURRENTLY idx_tokens_network ON tokens(network);
CREATE INDEX CONCURRENTLY idx_tokens_symbol ON tokens(symbol);
```

## Phase 3: Data Migration Strategy

### 3.1 Migration Approach

1. **Parallel Migration**: Migrate data in chunks to minimize downtime
2. **Validation**: Verify data integrity at each step
3. **Rollback Plan**: Maintain SQLite as backup during transition
4. **Zero-Downtime**: Use dual-write pattern during migration

### 3.2 Migration Order

1. Reference data (DEXes, Tokens)
2. Pools (with dependencies)
3. Watchlist entries
4. Historical data (OHLCV, Trades) - in chunks
5. Metadata and configuration

## Phase 4: Application Configuration

### 4.1 Database Configuration Updates

Update configuration to support both SQLite (backup) and PostgreSQL (primary):

```yaml
database:
  primary:
    type: postgresql
    host: localhost
    port: 5432
    database: gecko_terminal_collector
    username: gecko_collector
    password: ${POSTGRES_PASSWORD}
    pool_size: 20
    max_overflow: 30
    pool_timeout: 30
    pool_recycle: 3600
  
  backup:
    type: sqlite
    url: sqlite:///gecko_data.db
    enabled: true  # Keep during migration
```

### 4.2 Environment Variables

```bash
# Add to your environment
export POSTGRES_PASSWORD="your_secure_password"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="gecko_terminal_collector"
export POSTGRES_USER="gecko_collector"
```

## Phase 5: Testing and Validation

### 5.1 Data Integrity Checks

- Row count validation
- Sample data comparison
- Foreign key constraint validation
- Index performance testing

### 5.2 Performance Testing

- Concurrent write performance
- Query performance comparison
- Lock contention testing
- Backup and recovery testing

## Phase 6: Deployment Strategy

### 6.1 Blue-Green Deployment

1. **Blue (Current)**: SQLite system continues running
2. **Green (New)**: PostgreSQL system runs in parallel
3. **Validation**: Compare outputs between systems
4. **Cutover**: Switch traffic to PostgreSQL
5. **Monitoring**: Monitor for issues, rollback if needed

### 6.2 Rollback Plan

- Keep SQLite database as immediate fallback
- Configuration switch to revert to SQLite
- Data synchronization scripts if rollback needed

## Timeline Estimate

- **Phase 1-2 (Setup & Schema)**: 2-4 hours
- **Phase 3 (Data Migration)**: 4-8 hours (depends on data volume)
- **Phase 4 (Configuration)**: 1-2 hours
- **Phase 5 (Testing)**: 2-4 hours
- **Phase 6 (Deployment)**: 1-2 hours

**Total Estimated Time**: 10-20 hours (can be done over multiple days)

## Risk Mitigation

### High Priority Risks

1. **Data Loss**: Multiple backups, validation at each step
2. **Downtime**: Parallel migration, dual-write pattern
3. **Performance Regression**: Extensive testing, rollback plan
4. **Configuration Issues**: Staged deployment, validation scripts

### Monitoring During Migration

- Database connection health
- Query performance metrics
- Error rates and lock contention
- Data consistency checks

## Success Criteria

- [ ] All data migrated successfully with 100% integrity
- [ ] Performance equal or better than SQLite
- [ ] No data loss during migration
- [ ] All collectors working normally
- [ ] Monitoring and alerting functional
- [ ] Backup and recovery procedures tested

## Post-Migration Tasks

1. **Cleanup**: Remove SQLite dependencies (after validation period)
2. **Optimization**: Fine-tune PostgreSQL configuration
3. **Monitoring**: Set up PostgreSQL-specific monitoring
4. **Documentation**: Update operational procedures
5. **Training**: Team training on PostgreSQL operations

## Emergency Procedures

### If Migration Fails

1. **Stop Migration**: Halt all migration processes
2. **Assess Impact**: Determine what data was affected
3. **Rollback**: Switch back to SQLite configuration
4. **Investigate**: Analyze logs and error messages
5. **Fix and Retry**: Address issues and restart migration

### If Performance Issues Occur

1. **Monitor**: Check PostgreSQL performance metrics
2. **Optimize**: Adjust configuration parameters
3. **Index**: Add missing indexes if needed
4. **Scale**: Increase resources if necessary
5. **Rollback**: If issues persist, rollback to SQLite

## Next Steps

1. Review and approve this migration plan
2. Set up PostgreSQL database and user
3. Create and test migration scripts
4. Schedule migration window
5. Execute migration in phases
6. Monitor and validate results