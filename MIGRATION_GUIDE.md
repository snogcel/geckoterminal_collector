# PostgreSQL Migration Guide

This guide will walk you through migrating your Gecko Terminal Collector from SQLite to PostgreSQL.

## Prerequisites

- Windows 10/11
- Python 3.8+
- Administrator access (for PostgreSQL installation)
- Current SQLite database (`gecko_data.db`)

## Step 1: Install PostgreSQL

### Option A: Using the provided script (Recommended)
```cmd
# Run as Administrator
powershell -ExecutionPolicy Bypass -File install_postgresql.ps1
```

### Option B: Manual installation
1. Download PostgreSQL 15 from https://www.postgresql.org/download/windows/
2. Run the installer with these settings:
   - Password for postgres user: `12345678!`
   - Port: `5432`
   - Locale: Default
3. Add PostgreSQL to your PATH: `C:\Program Files\PostgreSQL\15\bin`

## Step 2: Setup Database

After PostgreSQL is installed and running:

```cmd
# Setup the database and user
setup_database.bat
```

This will:
- Create the `gecko_terminal_collector` database
- Create the `gecko_collector` user
- Set up permissions and optimizations

## Step 3: Install Python Dependencies

```cmd
pip install asyncpg psycopg2-binary
```

## Step 4: Pre-Migration Check

Run the readiness check to ensure everything is set up correctly:

```cmd
python check_migration_readiness.py
```

This will verify:
- PostgreSQL connection
- SQLite database accessibility
- Required Python packages
- Migration script availability

## Step 5: Run Migration

Once all checks pass, run the migration:

```cmd
python migrate_to_postgresql.py gecko_data.db postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector
```

### Migration Process

The migration will:
1. **Initialize** both database connections
2. **Verify** PostgreSQL setup
3. **Analyze** SQLite data volume
4. **Migrate** data in this order:
   - DEXes (reference data)
   - Tokens (reference data)
   - Pools (with dependencies)
   - Watchlist entries
   - Trades (large dataset, batched)
   - OHLCV data (time-series data, batched)
5. **Verify** data integrity
6. **Report** migration results

### Expected Timeline

Based on your current database size (~32MB):
- **Setup & Schema**: 2-5 minutes
- **Data Migration**: 10-30 minutes
- **Verification**: 2-5 minutes
- **Total**: 15-40 minutes

## Step 6: Update Configuration

After successful migration, update your configuration:

### Update config.yaml
```yaml
database:
  url: "postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector"
  pool_size: 20
  echo: false
  timeout: 30
```

### Update environment variables
```bash
# Add to your environment
GECKO_DB_URL=postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector
```

## Step 7: Test the Migration

Test your collectors with the new database:

```cmd
# Test basic functionality
python -m gecko_terminal_collector.cli --help

# Test database connection
python -c "from gecko_terminal_collector.database.postgresql_manager import PostgreSQLDatabaseManager; import asyncio; print('Testing...'); asyncio.run(PostgreSQLDatabaseManager({'url': 'postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector'}).get_database_health_metrics())"
```

## Troubleshooting

### PostgreSQL Connection Issues

1. **Service not running**:
   ```cmd
   net start postgresql-x64-15
   ```

2. **Authentication failed**:
   - Verify password: `12345678!`
   - Check pg_hba.conf for authentication method

3. **Port conflicts**:
   - Check if port 5432 is available
   - Modify connection string if using different port

### Migration Issues

1. **Permission errors**:
   ```sql
   -- Connect as postgres user and run:
   GRANT ALL PRIVILEGES ON DATABASE gecko_terminal_collector TO gecko_collector;
   ```

2. **Memory issues during migration**:
   - Reduce batch size in migration script
   - Close other applications to free memory

3. **Data integrity issues**:
   - Check migration logs for specific errors
   - Verify foreign key constraints
   - Run verification queries manually

### Performance Issues

1. **Slow queries after migration**:
   ```sql
   -- Update table statistics
   ANALYZE;
   
   -- Check for missing indexes
   SELECT * FROM pg_stat_user_tables WHERE n_tup_ins > 0 AND n_tup_upd > 0;
   ```

2. **Connection pool exhaustion**:
   - Increase `pool_size` in configuration
   - Monitor active connections

## Rollback Plan

If migration fails or issues occur:

1. **Stop collectors**
2. **Revert configuration** to SQLite:
   ```yaml
   database:
     url: "sqlite:///gecko_data.db"
   ```
3. **Restart collectors**
4. **Investigate issues** before retrying

## Post-Migration Optimization

After successful migration:

1. **Monitor performance** for 24-48 hours
2. **Tune PostgreSQL settings** based on usage patterns
3. **Set up regular maintenance**:
   ```sql
   -- Weekly maintenance
   VACUUM ANALYZE;
   REINDEX DATABASE gecko_terminal_collector;
   ```
4. **Configure backups**:
   ```cmd
   pg_dump -U gecko_collector -h localhost gecko_terminal_collector > backup.sql
   ```

## Success Criteria

Migration is successful when:
- ✅ All data migrated with 100% record count match
- ✅ All collectors start and run normally
- ✅ Query performance is equal or better than SQLite
- ✅ No data corruption or integrity issues
- ✅ Monitoring and health checks pass

## Support

If you encounter issues:
1. Check the migration logs for specific error messages
2. Verify all prerequisites are met
3. Run the pre-migration check again
4. Check PostgreSQL logs: `C:\Program Files\PostgreSQL\15\data\log\`

## Next Steps After Migration

1. **Remove SQLite dependencies** (after validation period)
2. **Set up PostgreSQL monitoring**
3. **Configure automated backups**
4. **Optimize PostgreSQL configuration** for your workload
5. **Update documentation** and operational procedures