#!/usr/bin/env python3
"""
PostgreSQL Test Data Cleanup with Foreign Key Handling
======================================================

This script properly handles foreign key constraints when cleaning test data.
"""

import psycopg2
from psycopg2 import sql
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_postgresql_test_data():
    """Clean test data from PostgreSQL with proper foreign key handling"""
    
    db_url = "postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector"
    
    try:
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor()
        
        # Delete in proper order to respect foreign key constraints
        deletion_order = [
            # Child tables first (tables that reference others)
            ("watchlist", "pool_id LIKE '%test%' OR pool_id LIKE '%demo%' OR pool_id LIKE '%temp%'"),
            ("trades", "pool_id LIKE '%test%' OR pool_id LIKE '%demo%' OR pool_id LIKE '%temp%'"),
            ("ohlcv_data", "pool_id LIKE '%test%' OR pool_id LIKE '%demo%' OR pool_id LIKE '%temp%'"),
            ("new_pools_history", "pool_id LIKE '%test%' OR pool_id LIKE '%demo%' OR pool_id LIKE '%temp%'"),
            
            # Parent tables last
            ("pools", "id LIKE '%test%' OR id LIKE '%demo%' OR id LIKE '%temp%' OR name ILIKE '%test%' OR name ILIKE '%demo%' OR name ILIKE '%temp%'"),
            ("tokens", "id LIKE '%test%' OR id LIKE '%demo%' OR id LIKE '%temp%' OR name ILIKE '%test%' OR name ILIKE '%demo%' OR name ILIKE '%temp%' OR symbol ILIKE '%test%' OR symbol ILIKE '%demo%' OR symbol ILIKE '%temp%'"),
            ("dexes", "id LIKE '%test%' OR id LIKE '%demo%' OR id LIKE '%temp%' OR name ILIKE '%test%' OR name ILIKE '%demo%' OR name ILIKE '%temp%'"),
        ]
        
        total_deleted = 0
        
        for table_name, where_condition in deletion_order:
            try:
                # Count records first
                count_query = f"SELECT COUNT(*) FROM {table_name} WHERE {where_condition}"
                cursor.execute(count_query)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    logger.info(f"Deleting {count} test records from {table_name}...")
                    
                    # Delete the records
                    delete_query = f"DELETE FROM {table_name} WHERE {where_condition}"
                    cursor.execute(delete_query)
                    
                    deleted_count = cursor.rowcount
                    total_deleted += deleted_count
                    logger.info(f"Deleted {deleted_count} records from {table_name}")
                else:
                    logger.info(f"No test records found in {table_name}")
                    
            except Exception as e:
                logger.error(f"Error cleaning {table_name}: {e}")
                conn.rollback()
                return False
        
        # Commit all changes
        conn.commit()
        logger.info(f"Successfully deleted {total_deleted} total test records from PostgreSQL")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        return False

if __name__ == "__main__":
    success = cleanup_postgresql_test_data()
    if success:
        logger.info("PostgreSQL test data cleanup completed successfully!")
    else:
        logger.error("PostgreSQL test data cleanup failed!")