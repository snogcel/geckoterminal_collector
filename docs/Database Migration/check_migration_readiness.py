#!/usr/bin/env python3
"""
Pre-migration check script to verify system readiness.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg
import sqlite3
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def check_postgresql_connection():
    """Check PostgreSQL connection and setup."""
    try:
        # Test connection
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            database='gecko_terminal_collector',
            user='gecko_collector',
            password='12345678!'
        )
        
        # Test basic query
        result = await conn.fetchval('SELECT version()')
        logger.info(f"✓ PostgreSQL connection successful")
        logger.info(f"  Version: {result}")
        
        # Check database size
        db_size = await conn.fetchval("SELECT pg_size_pretty(pg_database_size('gecko_terminal_collector'))")
        logger.info(f"  Database size: {db_size}")
        
        # Check extensions
        extensions = await conn.fetch("SELECT extname FROM pg_extension")
        ext_names = [row['extname'] for row in extensions]
        logger.info(f"  Extensions: {', '.join(ext_names)}")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False


def check_sqlite_database():
    """Check SQLite database and analyze data."""
    sqlite_path = "gecko_data.db"
    
    if not os.path.exists(sqlite_path):
        logger.error(f"❌ SQLite database not found: {sqlite_path}")
        return False
    
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Get database size
        db_size = os.path.getsize(sqlite_path)
        logger.info(f"✓ SQLite database found: {sqlite_path}")
        logger.info(f"  Size: {db_size / (1024*1024):.1f} MB")
        
        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        logger.info(f"  Tables: {len(tables)}")
        
        # Count records in each table
        total_records = 0
        for (table_name,) in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                total_records += count
                logger.info(f"    {table_name}: {count:,} records")
            except Exception as e:
                logger.warning(f"    {table_name}: Error counting - {e}")
        
        logger.info(f"  Total records: {total_records:,}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ SQLite database check failed: {e}")
        return False


def check_python_dependencies():
    """Check required Python packages."""
    required_packages = [
        ('asyncpg', 'asyncpg'),
        ('sqlalchemy', 'sqlalchemy'),
        ('psycopg2-binary', 'psycopg2')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            logger.info(f"✓ {package_name} is installed")
        except ImportError:
            missing_packages.append(package_name)
            logger.error(f"❌ {package_name} is missing")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Install with: pip install " + " ".join(missing_packages))
        return False
    
    return True


def check_migration_script():
    """Check migration script exists and is ready."""
    script_path = "migrate_to_postgresql.py"
    
    if not os.path.exists(script_path):
        logger.error(f"❌ Migration script not found: {script_path}")
        return False
    
    logger.info(f"✓ Migration script found: {script_path}")
    
    # Check if script is executable
    if os.access(script_path, os.R_OK):
        logger.info("  Script is readable")
    else:
        logger.warning("  Script may not be readable")
    
    return True


async def main():
    """Run all pre-migration checks."""
    logger.info("=== Pre-Migration Readiness Check ===")
    
    checks = [
        ("Python Dependencies", check_python_dependencies()),
        ("SQLite Database", check_sqlite_database()),
        ("Migration Script", check_migration_script()),
        ("PostgreSQL Connection", await check_postgresql_connection()),
    ]
    
    all_passed = True
    
    logger.info("\n=== Check Results ===")
    for check_name, result in checks:
        status = "✓ PASS" if result else "❌ FAIL"
        logger.info(f"{check_name}: {status}")
        if not result:
            all_passed = False
    
    logger.info("\n=== Summary ===")
    if all_passed:
        logger.info("🎉 All checks passed! Ready for migration.")
        logger.info("\nNext steps:")
        logger.info("1. Run: python migrate_to_postgresql.py gecko_data.db postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector")
        logger.info("2. Monitor the migration progress")
        logger.info("3. Verify data integrity after migration")
    else:
        logger.error("❌ Some checks failed. Please fix the issues before migration.")
        logger.info("\nCommon fixes:")
        logger.info("1. Install PostgreSQL: Run install_postgresql.ps1 as Administrator")
        logger.info("2. Setup database: Run setup_database.bat")
        logger.info("3. Install Python packages: pip install asyncpg psycopg2-binary")
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)