# Database Backup & Restore Guide

## Overview

This guide covers the comprehensive database backup and restore system for the GeckoTerminal Collector. The system supports both PostgreSQL and SQLite databases with full schema and data backup capabilities.

## 🗄️ Backup System Features

### Comprehensive Backup
- **Full Schema Backup**: Complete database structure
- **Table-by-Table Data**: Individual table data files
- **Compressed Storage**: Automatic gzip compression
- **Metadata Tracking**: Backup information and statistics
- **Configuration Snapshot**: System settings at backup time

### Multiple Backup Methods
1. **CLI Integration**: Built into the existing CLI system
2. **Standalone Scripts**: Independent backup/restore scripts
3. **Quick Backup**: One-command timestamped backups

## 🚀 Creating Backups

### Method 1: CLI Command (Recommended)

```bash
# Create a comprehensive backup
gecko-cli backup /path/to/backup/directory

# Create backup with custom name
gecko-cli backup ./backups/my_backup_name

# Create uncompressed backup
gecko-cli backup ./backups/uncompressed_backup --no-compress

# List available backups
gecko-cli list-backups

# List backups in JSON format
gecko-cli list-backups --format json
```

### Method 2: Standalone Backup Script

```bash
# Create backup with automatic timestamped name
python create_database_backup.py

# Create backup with custom name
python create_database_backup.py --name my_custom_backup

# Create uncompressed backup
python create_database_backup.py --no-compress

# List existing backups
python create_database_backup.py --list
```

### Method 3: Quick Backup Script

```bash
# One-command timestamped backup
python quick_backup.py
```

This creates a backup named `quick_backup_YYYYMMDD_HHMMSS` in the `backups/` directory.

## 📦 Backup Structure

Each backup creates a directory with the following structure:

```
backup_directory/
├── backup_metadata.json          # Backup information and statistics
├── schema.sql.gz                 # Database schema (compressed)
├── full_backup.sql.gz            # Complete database dump (compressed)
├── dexes_data.sql.gz             # DEXes table data
├── tokens_data.sql.gz            # Tokens table data
├── pools_data.sql.gz             # Pools table data
├── trades_data.sql.gz            # Trades table data
├── ohlcv_data_data.sql.gz        # OHLCV data table
├── watchlist_data.sql.gz         # Watchlist table data
├── new_pools_history_data.sql.gz # New pools history data
└── ...                           # Other table data files
```

### Backup Metadata

The `backup_metadata.json` file contains:

```json
{
  "backup_info": {
    "created_at": "2025-09-16T10:30:00",
    "backup_type": "full_database",
    "database_type": "postgresql",
    "database_name": "gecko_terminal_collector",
    "host": "localhost",
    "port": 5432
  },
  "system_info": {
    "python_version": "3.11.0",
    "platform": "win32",
    "backup_script_version": "1.0.0"
  },
  "table_statistics": {
    "pools": {"row_count": 1250},
    "trades": {"row_count": 45000},
    "ohlcv_data": {"row_count": 12000},
    "new_pools_history": {"row_count": 3500}
  },
  "config_snapshot": {
    "collection_intervals": {...},
    "new_pools_config": {...}
  }
}
```

## 🔄 Restoring Backups

### Method 1: CLI Command

```bash
# Restore from backup (with confirmation prompt)
gecko-cli restore /path/to/backup/directory

# Restore with overwrite (no confirmation)
gecko-cli restore /path/to/backup/directory --overwrite

# Restore specific data types only
gecko-cli restore /path/to/backup/directory --data-types pools tokens watchlist

# Verify backup before restoring
gecko-cli restore /path/to/backup/directory --verify
```

### Method 2: Standalone Restore Script

```bash
# Restore with verification and confirmation
python restore_database_backup.py /path/to/backup/directory

# Restore with overwrite (no confirmation)
python restore_database_backup.py /path/to/backup/directory --overwrite

# Skip backup verification
python restore_database_backup.py /path/to/backup/directory --no-verify
```

## 📋 Backup Management

### List Available Backups

```bash
# Table format (default)
gecko-cli list-backups

# JSON format for scripting
gecko-cli list-backups --format json
```

Example output:
```
📋 Available Database Backups
============================================================
Name                      Created              Size       Type        
----------------------------------------------------------------------
quick_backup_20250916_103 2025-09-16 10:30     45.2 MB    postgresql  
signal_analysis_backup    2025-09-16 09:15     42.8 MB    postgresql  
pre_migration_backup      2025-09-15 18:45     38.1 MB    postgresql  

Total backups: 3
```

### Backup Best Practices

1. **Regular Backups**: Create backups before major changes
2. **Pre-Migration Backups**: Always backup before database migrations
3. **Timestamped Names**: Use descriptive, timestamped backup names
4. **Verification**: Verify backups periodically
5. **Storage**: Store backups in multiple locations for safety

## 🛠️ Advanced Usage

### Automated Backup Scripts

Create a scheduled backup script:

```bash
#!/bin/bash
# automated_backup.sh

# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="automated_backup_$TIMESTAMP"

echo "Creating automated backup: $BACKUP_NAME"
python create_database_backup.py --name "$BACKUP_NAME"

# Keep only last 10 backups (optional cleanup)
# Add cleanup logic here if needed
```

### Pre-Migration Backup

Before running database migrations:

```bash
# Create pre-migration backup
python create_database_backup.py --name "pre_signal_analysis_migration"

# Run migration
python migrations/add_signal_fields_to_new_pools_history.py

# Verify migration success
gecko-cli db-health --test-connectivity
```

### Backup Verification

Verify backup integrity:

```bash
# Verify specific backup
python restore_database_backup.py /path/to/backup --no-verify --overwrite

# Or use the verification flag during restore
python restore_database_backup.py /path/to/backup --verify
```

## 🔧 Troubleshooting

### Common Issues

1. **Permission Errors**
   ```bash
   # Ensure proper database permissions
   # For PostgreSQL, ensure user has CREATE/DROP privileges
   ```

2. **Disk Space**
   ```bash
   # Check available disk space before backup
   df -h
   
   # Use compression to reduce backup size
   python create_database_backup.py --compress
   ```

3. **Connection Issues**
   ```bash
   # Test database connectivity
   gecko-cli db-health --test-connectivity
   
   # Check configuration
   gecko-cli validate --check-db
   ```

4. **Large Database Backups**
   ```bash
   # For very large databases, consider:
   # - Using table-specific backups
   # - Implementing incremental backups
   # - Using database-specific tools (pg_dump, etc.)
   ```

### Recovery Scenarios

#### Scenario 1: Corrupted Database
```bash
# 1. Stop the collector
gecko-cli stop

# 2. Restore from latest backup
python restore_database_backup.py ./backups/latest_backup --overwrite

# 3. Restart the collector
gecko-cli start
```

#### Scenario 2: Failed Migration
```bash
# 1. Stop the collector
gecko-cli stop

# 2. Restore pre-migration backup
python restore_database_backup.py ./backups/pre_migration_backup --overwrite

# 3. Fix migration script and retry
# 4. Restart the collector
```

#### Scenario 3: Data Loss
```bash
# 1. Identify the last known good backup
gecko-cli list-backups

# 2. Restore from that backup
python restore_database_backup.py ./backups/good_backup --overwrite

# 3. Resume collection from restore point
```

## 📊 Backup Monitoring

### Backup Size Monitoring

```bash
# Check backup sizes
du -sh backups/*

# Monitor backup growth over time
ls -lah backups/ | grep backup
```

### Automated Backup Health Checks

Create a backup health check script:

```python
#!/usr/bin/env python3
import asyncio
from create_database_backup import DatabaseBackupManager

async def check_backup_health():
    manager = DatabaseBackupManager()
    backups = await manager.list_backups()
    
    if not backups:
        print("❌ No backups found!")
        return False
    
    latest_backup = backups[0]  # Sorted by date, newest first
    
    # Check if latest backup is recent (within 24 hours)
    from datetime import datetime, timedelta
    created_at = datetime.fromisoformat(latest_backup['created_at'])
    if datetime.now() - created_at > timedelta(hours=24):
        print("⚠️  Latest backup is older than 24 hours")
        return False
    
    print("✅ Backup health check passed")
    return True

if __name__ == "__main__":
    asyncio.run(check_backup_health())
```

## 🔐 Security Considerations

1. **Backup Encryption**: Consider encrypting sensitive backups
2. **Access Control**: Restrict access to backup directories
3. **Network Security**: Use secure connections for remote backups
4. **Credential Management**: Avoid storing passwords in backup scripts

## 📚 Integration with Existing System

The backup system integrates seamlessly with:

- **CLI Commands**: All backup operations available via CLI
- **Configuration System**: Uses existing config.yaml settings
- **Database Managers**: Works with SQLAlchemy and other managers
- **Logging System**: Comprehensive logging and error reporting
- **Signal Analysis**: Backup before/after signal system changes

## 🎯 Quick Reference

### Essential Commands

```bash
# Create backup
python quick_backup.py

# List backups
gecko-cli list-backups

# Restore backup
python restore_database_backup.py /path/to/backup

# Verify system after restore
gecko-cli db-health --test-connectivity --test-performance
```

### Before Major Changes

```bash
# 1. Create backup
python create_database_backup.py --name "pre_change_backup"

# 2. Make changes
# ... your changes here ...

# 3. Verify system
gecko-cli db-health

# 4. If issues, restore
# python restore_database_backup.py ./backups/pre_change_backup --overwrite
```

---

**Your data is now protected with comprehensive backup and restore capabilities!** 🛡️

The backup system ensures you can safely implement the new signal analysis features while maintaining the ability to recover from any issues.