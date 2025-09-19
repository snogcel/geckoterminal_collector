#!/usr/bin/env python3
"""
Test Data Cleanup Script
========================

This script helps clean up test data from both PostgreSQL and SQLite databases.
It provides options to:
1. Clear test data from PostgreSQL tables
2. Remove test SQLite database files
3. Clean up test output directories
4. Remove test log files

Usage:
    python cleanup_test_data.py [options]

Options:
    --postgresql    Clean test data from PostgreSQL database
    --sqlite        Remove test SQLite database files
    --logs          Remove test log files
    --output        Remove test output directories
    --all           Clean everything (equivalent to all above options)
    --dry-run       Show what would be deleted without actually deleting
    --interactive   Ask for confirmation before each deletion
"""

import os
import sys
import argparse
import glob
import shutil
from pathlib import Path
from typing import List, Optional
import logging

# Database imports
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import sqlite3
    SQLITE3_AVAILABLE = True
except ImportError:
    SQLITE3_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestDataCleaner:
    """Main class for cleaning up test data"""
    
    def __init__(self, dry_run: bool = False, interactive: bool = False):
        self.dry_run = dry_run
        self.interactive = interactive
        self.workspace_root = Path.cwd()
        
    def confirm_action(self, message: str) -> bool:
        """Ask for user confirmation if in interactive mode"""
        if not self.interactive:
            return True
        
        response = input(f"{message} (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def clean_postgresql_test_data(self):
        """Clean test data from PostgreSQL database"""
        if not PSYCOPG2_AVAILABLE:
            logger.error("psycopg2 not available. Cannot clean PostgreSQL data.")
            return
        
        # Database connection string from config
        db_url = "postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector"
        
        try:
            logger.info("Connecting to PostgreSQL database...")
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                logger.info("No tables found in database.")
                return
            
            logger.info(f"Found tables: {', '.join(tables)}")
            
            # Tables that might contain test data
            test_data_patterns = [
                'test_',
                'demo_',
                'temp_',
                '_test',
                '_demo',
                '_temp'
            ]
            
            # Find tables that look like test tables
            test_tables = []
            for table in tables:
                if any(pattern in table.lower() for pattern in test_data_patterns):
                    test_tables.append(table)
            
            if test_tables:
                logger.info(f"Found potential test tables: {', '.join(test_tables)}")
                
                if self.confirm_action(f"Delete all data from test tables: {', '.join(test_tables)}?"):
                    for table in test_tables:
                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would truncate table: {table}")
                        else:
                            cursor.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.Identifier(table)))
                            logger.info(f"Truncated table: {table}")
            
            # Option to clear specific data from main tables
            main_tables = [t for t in tables if t not in test_tables]
            if main_tables:
                logger.info(f"Main tables: {', '.join(main_tables)}")
                
                # Clear test records from main tables (records with 'test' in relevant fields)
                for table in main_tables:
                    try:
                        # Get column names
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = %s
                        """, (table,))
                        columns = [row[0] for row in cursor.fetchall()]
                        
                        # Look for text columns that might contain test data
                        text_columns = []
                        for col in columns:
                            if any(keyword in col.lower() for keyword in ['name', 'symbol', 'address', 'description']):
                                text_columns.append(col)
                        
                        if text_columns:
                            # Build WHERE clause to find test records
                            conditions = []
                            for col in text_columns:
                                conditions.append(f"{col} ILIKE '%test%'")
                                conditions.append(f"{col} ILIKE '%demo%'")
                                conditions.append(f"{col} ILIKE '%temp%'")
                            
                            where_clause = " OR ".join(conditions)
                            
                            # Count test records first
                            count_query = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
                            cursor.execute(count_query)
                            count = cursor.fetchone()[0]
                            
                            if count > 0:
                                if self.confirm_action(f"Delete {count} test records from {table}?"):
                                    if self.dry_run:
                                        logger.info(f"[DRY RUN] Would delete {count} test records from {table}")
                                    else:
                                        delete_query = f"DELETE FROM {table} WHERE {where_clause}"
                                        cursor.execute(delete_query)
                                        logger.info(f"Deleted {count} test records from {table}")
                    
                    except Exception as e:
                        logger.warning(f"Could not clean test data from {table}: {e}")
            
            if not self.dry_run:
                conn.commit()
            
            cursor.close()
            conn.close()
            logger.info("PostgreSQL cleanup completed.")
            
        except Exception as e:
            logger.error(f"Error cleaning PostgreSQL data: {e}")
    
    def clean_sqlite_files(self):
        """Remove test SQLite database files"""
        if not SQLITE3_AVAILABLE:
            logger.error("sqlite3 not available. Cannot clean SQLite files.")
            return
        
        # Patterns for test database files
        test_db_patterns = [
            "test_*.db",
            "*_test.db",
            "demo_*.db",
            "*_demo.db",
            "temp_*.db",
            "*_temp.db",
            "simple_test_*.db",
            "bulk_demo_*.db",
            "*_1757*.db",  # Timestamp-based test files
        ]
        
        # Also include specific known test files
        specific_test_files = [
            "test_simple.db",
            "test_trade_fix.db",
            "test_enhanced_metadata.db",
            "new_pools_demo.db",
            "demo_gecko_data.db",
            "demo_gecko_data_old.db",
            "gecko_data_corrupted_backup.db"
        ]
        
        files_to_remove = []
        
        # Find files matching patterns
        for pattern in test_db_patterns:
            files_to_remove.extend(glob.glob(pattern))
        
        # Add specific files if they exist
        for file in specific_test_files:
            if os.path.exists(file):
                files_to_remove.append(file)
        
        # Remove duplicates and sort
        files_to_remove = sorted(list(set(files_to_remove)))
        
        if not files_to_remove:
            logger.info("No test SQLite files found.")
            return
        
        logger.info(f"Found {len(files_to_remove)} test SQLite files:")
        for file in files_to_remove:
            logger.info(f"  - {file}")
        
        if self.confirm_action(f"Delete {len(files_to_remove)} SQLite test files?"):
            for file in files_to_remove:
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would delete: {file}")
                    else:
                        os.remove(file)
                        logger.info(f"Deleted: {file}")
                except Exception as e:
                    logger.error(f"Error deleting {file}: {e}")
    
    def clean_test_logs(self):
        """Remove test log files"""
        log_patterns = [
            "test_*.log",
            "*_test.log",
            "ohlcv_trade_tests_*.log",
            "cli_test_results_*.json",
            "*_test_report_*.txt"
        ]
        
        files_to_remove = []
        for pattern in log_patterns:
            files_to_remove.extend(glob.glob(pattern))
        
        files_to_remove = sorted(list(set(files_to_remove)))
        
        if not files_to_remove:
            logger.info("No test log files found.")
            return
        
        logger.info(f"Found {len(files_to_remove)} test log files:")
        for file in files_to_remove:
            logger.info(f"  - {file}")
        
        if self.confirm_action(f"Delete {len(files_to_remove)} test log files?"):
            for file in files_to_remove:
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would delete: {file}")
                    else:
                        os.remove(file)
                        logger.info(f"Deleted: {file}")
                except Exception as e:
                    logger.error(f"Error deleting {file}: {e}")
    
    def clean_test_output_dirs(self):
        """Remove test output directories"""
        test_output_patterns = [
            "test_output*",
            "*_test_output",
            "temp_*",
            "*_temp"
        ]
        
        dirs_to_remove = []
        for pattern in test_output_patterns:
            dirs_to_remove.extend(glob.glob(pattern))
        
        # Filter to only include directories
        dirs_to_remove = [d for d in dirs_to_remove if os.path.isdir(d)]
        dirs_to_remove = sorted(list(set(dirs_to_remove)))
        
        if not dirs_to_remove:
            logger.info("No test output directories found.")
            return
        
        logger.info(f"Found {len(dirs_to_remove)} test output directories:")
        for dir_path in dirs_to_remove:
            logger.info(f"  - {dir_path}")
        
        if self.confirm_action(f"Delete {len(dirs_to_remove)} test output directories?"):
            for dir_path in dirs_to_remove:
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would delete directory: {dir_path}")
                    else:
                        shutil.rmtree(dir_path)
                        logger.info(f"Deleted directory: {dir_path}")
                except Exception as e:
                    logger.error(f"Error deleting {dir_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Clean up test data from databases and files")
    parser.add_argument("--postgresql", action="store_true", help="Clean test data from PostgreSQL")
    parser.add_argument("--sqlite", action="store_true", help="Remove test SQLite files")
    parser.add_argument("--logs", action="store_true", help="Remove test log files")
    parser.add_argument("--output", action="store_true", help="Remove test output directories")
    parser.add_argument("--all", action="store_true", help="Clean everything")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--interactive", action="store_true", help="Ask for confirmation before each deletion")
    
    args = parser.parse_args()
    
    # If no specific options, default to interactive mode
    if not any([args.postgresql, args.sqlite, args.logs, args.output, args.all]):
        args.interactive = True
        args.all = True
    
    cleaner = TestDataCleaner(dry_run=args.dry_run, interactive=args.interactive)
    
    logger.info("Starting test data cleanup...")
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will actually be deleted")
    
    try:
        if args.all or args.postgresql:
            logger.info("\n=== Cleaning PostgreSQL Test Data ===")
            cleaner.clean_postgresql_test_data()
        
        if args.all or args.sqlite:
            logger.info("\n=== Cleaning SQLite Test Files ===")
            cleaner.clean_sqlite_files()
        
        if args.all or args.logs:
            logger.info("\n=== Cleaning Test Log Files ===")
            cleaner.clean_test_logs()
        
        if args.all or args.output:
            logger.info("\n=== Cleaning Test Output Directories ===")
            cleaner.clean_test_output_dirs()
        
        logger.info("\nTest data cleanup completed!")
        
    except KeyboardInterrupt:
        logger.info("\nCleanup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()