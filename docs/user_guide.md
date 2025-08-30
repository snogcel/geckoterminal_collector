# User Guide

This guide covers day-to-day operation of the GeckoTerminal Data Collector system.

## Getting Started

### Starting the System

#### Basic Start
```bash
python -m gecko_terminal_collector.cli start
```

#### Start with Custom Configuration
```bash
python -m gecko_terminal_collector.cli start --config custom_config.yaml
```

#### Start in Background (Linux/macOS)
```bash
nohup python -m gecko_terminal_collector.cli start > collector.log 2>&1 &
```

#### Start with Docker
```bash
docker run -d \
  --name gecko-collector \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/data:/app/data \
  gecko-terminal-collector
```

### Stopping the System

#### Graceful Stop
```bash
python -m gecko_terminal_collector.cli stop
```

#### Force Stop
```bash
python -m gecko_terminal_collector.cli stop --force
```

#### Stop Docker Container
```bash
docker stop gecko-collector
```

## Command Line Interface

### System Commands

#### Check System Status
```bash
python -m gecko_terminal_collector.cli status
```

#### Health Check
```bash
python -m gecko_terminal_collector.cli health-check
```

#### Show Configuration
```bash
python -m gecko_terminal_collector.cli show-config
```

#### Validate Configuration
```bash
python -m gecko_terminal_collector.cli validate-config
```

### Database Commands

#### Initialize Database
```bash
python -m gecko_terminal_collector.cli init-db
```

#### Test Database Connection
```bash
python -m gecko_terminal_collector.cli test-db
```

#### Database Statistics
```bash
python -m gecko_terminal_collector.cli db-stats
```

#### Backup Database
```bash
python -m gecko_terminal_collector.cli backup-db --output backup_20240830.sql
```

#### Restore Database
```bash
python -m gecko_terminal_collector.cli restore-db --input backup_20240830.sql
```

### Collection Commands

#### Manual Collection
```bash
# Collect DEX information
python -m gecko_terminal_collector.cli collect --type dex-monitoring

# Collect top pools
python -m gecko_terminal_collector.cli collect --type top-pools

# Collect OHLCV data
python -m gecko_terminal_collector.cli collect --type ohlcv

# Collect trade data
python -m gecko_terminal_collector.cli collect --type trades

# Process watchlist
python -m gecko_terminal_collector.cli collect --type watchlist
```

#### Historical Data Collection
```bash
# Backfill OHLCV data for specific pool
python -m gecko_terminal_collector.cli backfill-ohlcv \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --timeframe 1h \
  --days 30

# Backfill all watchlist tokens
python -m gecko_terminal_collector.cli backfill-watchlist \
  --timeframe 1h \
  --days 7
```

#### Collection Status
```bash
# Show collection statistics
python -m gecko_terminal_collector.cli collection-stats

# Show last collection times
python -m gecko_terminal_collector.cli last-collections

# Show collection errors
python -m gecko_terminal_collector.cli collection-errors
```

### Data Export Commands

#### Export to QLib Format
```bash
# Export all data
python -m gecko_terminal_collector.cli export-qlib --output qlib_data/

# Export specific symbols
python -m gecko_terminal_collector.cli export-qlib \
  --symbols BONK,SOL \
  --start-date 2024-01-01 \
  --end-date 2024-08-30 \
  --output qlib_data/
```

#### Export to CSV
```bash
# Export OHLCV data
python -m gecko_terminal_collector.cli export-csv \
  --type ohlcv \
  --output ohlcv_export.csv

# Export trade data
python -m gecko_terminal_collector.cli export-csv \
  --type trades \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --output trades_export.csv
```

## Watchlist Management

### Watchlist File Format

The watchlist is a CSV file with the following format:

```csv
pool_id,token_symbol,token_name,network_address,notes
solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP,BONK,Bonk,DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263,Popular meme token
solana_8sLbNZoA1cfnvMJLPfp98ZLAnFSYCFApfJKMbiXNLwxj,SOL,Solana,So11111111111111111111111111111111111111112,Native SOL
```

**Columns:**
- `pool_id`: GeckoTerminal pool identifier (required)
- `token_symbol`: Token symbol for display (optional)
- `token_name`: Full token name (optional)
- `network_address`: Token contract address (optional)
- `notes`: Additional notes (optional)

### Managing the Watchlist

#### Add Tokens to Watchlist
```bash
# Add single token
python -m gecko_terminal_collector.cli add-watchlist \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --symbol BONK

# Add from file
python -m gecko_terminal_collector.cli import-watchlist \
  --file new_tokens.csv
```

#### Remove Tokens from Watchlist
```bash
# Remove single token
python -m gecko_terminal_collector.cli remove-watchlist \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP

# Remove by symbol
python -m gecko_terminal_collector.cli remove-watchlist \
  --symbol BONK
```

#### View Watchlist
```bash
# Show current watchlist
python -m gecko_terminal_collector.cli show-watchlist

# Show watchlist statistics
python -m gecko_terminal_collector.cli watchlist-stats
```

#### Validate Watchlist
```bash
# Check watchlist for invalid entries
python -m gecko_terminal_collector.cli validate-watchlist

# Fix common issues automatically
python -m gecko_terminal_collector.cli fix-watchlist
```

## Monitoring and Logs

### Log Files

#### Default Log Locations
- Application logs: `logs/gecko_collector.log`
- Error logs: `logs/error.log`
- Collection logs: `logs/collection.log`
- API logs: `logs/api.log`

#### View Logs
```bash
# View recent logs
tail -f logs/gecko_collector.log

# View error logs only
grep ERROR logs/gecko_collector.log

# View collection statistics
grep "Collection completed" logs/collection.log
```

### System Monitoring

#### Real-time Status
```bash
# Watch system status
watch -n 30 'python -m gecko_terminal_collector.cli status'

# Monitor collection progress
python -m gecko_terminal_collector.cli monitor
```

#### Performance Metrics
```bash
# Show performance statistics
python -m gecko_terminal_collector.cli performance-stats

# Show API usage statistics
python -m gecko_terminal_collector.cli api-stats

# Show database performance
python -m gecko_terminal_collector.cli db-performance
```

### Alerts and Notifications

#### Configure Alerts
```yaml
# config.yaml
alerts:
  enabled: true
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "alerts@example.com"
    password: "${EMAIL_PASSWORD}"
    recipients: ["admin@example.com"]
  
  conditions:
    collection_failure_threshold: 3
    api_error_threshold: 10
    database_error_threshold: 5
```

#### Test Alerts
```bash
python -m gecko_terminal_collector.cli test-alerts
```

## Data Analysis

### Query Data

#### Basic Queries
```bash
# Show available pools
python -m gecko_terminal_collector.cli query pools

# Show OHLCV data for specific pool
python -m gecko_terminal_collector.cli query ohlcv \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --timeframe 1h \
  --limit 100

# Show recent trades
python -m gecko_terminal_collector.cli query trades \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --limit 50
```

#### Data Quality Checks
```bash
# Check for data gaps
python -m gecko_terminal_collector.cli check-gaps \
  --pool-id solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP \
  --timeframe 1h

# Validate data integrity
python -m gecko_terminal_collector.cli validate-data

# Show duplicate records
python -m gecko_terminal_collector.cli find-duplicates
```

### Data Statistics

#### Collection Statistics
```bash
# Show overall statistics
python -m gecko_terminal_collector.cli stats

# Show statistics by pool
python -m gecko_terminal_collector.cli stats --by-pool

# Show statistics by timeframe
python -m gecko_terminal_collector.cli stats --by-timeframe
```

#### Data Coverage
```bash
# Show data coverage report
python -m gecko_terminal_collector.cli coverage-report

# Show missing data periods
python -m gecko_terminal_collector.cli missing-data
```

## Maintenance Tasks

### Regular Maintenance

#### Daily Tasks
```bash
# Check system health
python -m gecko_terminal_collector.cli health-check

# Validate data integrity
python -m gecko_terminal_collector.cli validate-data

# Clean up old logs
python -m gecko_terminal_collector.cli cleanup-logs --days 30
```

#### Weekly Tasks
```bash
# Backup database
python -m gecko_terminal_collector.cli backup-db

# Optimize database
python -m gecko_terminal_collector.cli optimize-db

# Generate performance report
python -m gecko_terminal_collector.cli performance-report
```

#### Monthly Tasks
```bash
# Archive old data
python -m gecko_terminal_collector.cli archive-data --months 6

# Update system statistics
python -m gecko_terminal_collector.cli update-stats

# Review and clean watchlist
python -m gecko_terminal_collector.cli cleanup-watchlist
```

### Database Maintenance

#### Optimize Performance
```bash
# Analyze database performance
python -m gecko_terminal_collector.cli analyze-db

# Rebuild indexes
python -m gecko_terminal_collector.cli rebuild-indexes

# Update table statistics
python -m gecko_terminal_collector.cli update-db-stats
```

#### Clean Up Data
```bash
# Remove duplicate records
python -m gecko_terminal_collector.cli remove-duplicates

# Clean up orphaned records
python -m gecko_terminal_collector.cli cleanup-orphans

# Compress old data
python -m gecko_terminal_collector.cli compress-data --months 3
```

## Troubleshooting

### Common Issues

#### Collection Not Running
```bash
# Check if scheduler is active
python -m gecko_terminal_collector.cli status

# Check for configuration errors
python -m gecko_terminal_collector.cli validate-config

# Check logs for errors
tail -f logs/gecko_collector.log | grep ERROR
```

#### API Connection Issues
```bash
# Test API connectivity
python -m gecko_terminal_collector.cli test-api

# Check API rate limits
python -m gecko_terminal_collector.cli api-stats

# Reset API client
python -m gecko_terminal_collector.cli reset-api-client
```

#### Database Issues
```bash
# Test database connection
python -m gecko_terminal_collector.cli test-db

# Check database locks
python -m gecko_terminal_collector.cli check-db-locks

# Repair database (SQLite)
python -m gecko_terminal_collector.cli repair-db
```

### Performance Issues

#### Slow Collection
```bash
# Check system resources
python -m gecko_terminal_collector.cli system-info

# Analyze collection performance
python -m gecko_terminal_collector.cli collection-performance

# Optimize collection intervals
python -m gecko_terminal_collector.cli suggest-intervals
```

#### High Memory Usage
```bash
# Check memory usage
python -m gecko_terminal_collector.cli memory-stats

# Enable memory profiling
python -m gecko_terminal_collector.cli start --profile-memory

# Optimize memory settings
python -m gecko_terminal_collector.cli optimize-memory
```

## Best Practices

### Operational Best Practices

1. **Regular Monitoring**
   - Check system status daily
   - Monitor log files for errors
   - Validate data integrity weekly

2. **Backup Strategy**
   - Daily database backups
   - Keep configuration backups
   - Test restore procedures

3. **Performance Optimization**
   - Monitor API rate limits
   - Optimize collection intervals
   - Regular database maintenance

4. **Security**
   - Use environment variables for secrets
   - Secure file permissions
   - Regular security updates

### Data Quality

1. **Validation**
   - Regular data integrity checks
   - Monitor for gaps and duplicates
   - Validate watchlist entries

2. **Monitoring**
   - Track collection success rates
   - Monitor API response times
   - Alert on data quality issues

3. **Maintenance**
   - Clean up old data regularly
   - Optimize database performance
   - Update system statistics

## Next Steps

- Review [API Documentation](api_documentation.md) for integration details
- Check [Developer Guide](developer_guide.md) for customization
- See [Troubleshooting](troubleshooting.md) for detailed problem resolution
- Read [Operational Best Practices](operational_best_practices.md) for production deployment