#!/usr/bin/env python3
"""
Fix new_pools_history table schema by adding missing columns.

This script adds all the missing columns that the NewPoolsCollector expects
but are not present in the current PostgreSQL table schema.
"""

import asyncio
import logging
from sqlalchemy import text
from gecko_terminal_collector.database.postgresql_manager import PostgreSQLDatabaseManager
from gecko_terminal_collector.config.models import DatabaseConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_new_pools_history_schema():
    """Add missing columns to new_pools_history table."""
    
    # Initialize database manager
    config = DatabaseConfig()
    db_manager = PostgreSQLDatabaseManager(config)
    
    try:
        # Initialize database manager
        await db_manager.initialize()
        logger.info("Connected to PostgreSQL database")
        
        # Check current table structure
        logger.info("Checking current new_pools_history table structure...")
        
        async with db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'new_pools_history' 
                ORDER BY ordinal_position;
            """))
            columns_info = result.fetchall()
        
        current_columns = {row[0] for row in columns_info}
        logger.info(f"Current columns: {sorted(current_columns)}")
        
        # Define all required columns with their SQL definitions
        required_columns = {
            'type': "ALTER TABLE new_pools_history ADD COLUMN type VARCHAR(20) DEFAULT 'pool';",
            'name': "ALTER TABLE new_pools_history ADD COLUMN name VARCHAR(255);",
            'base_token_price_usd': "ALTER TABLE new_pools_history ADD COLUMN base_token_price_usd NUMERIC(20, 10);",
            'base_token_price_native_currency': "ALTER TABLE new_pools_history ADD COLUMN base_token_price_native_currency NUMERIC(20, 10);",
            'quote_token_price_usd': "ALTER TABLE new_pools_history ADD COLUMN quote_token_price_usd NUMERIC(20, 10);",
            'quote_token_price_native_currency': "ALTER TABLE new_pools_history ADD COLUMN quote_token_price_native_currency NUMERIC(20, 10);",
            'address': "ALTER TABLE new_pools_history ADD COLUMN address VARCHAR(255);",
            'reserve_in_usd': "ALTER TABLE new_pools_history ADD COLUMN reserve_in_usd NUMERIC(20, 4);",
            'pool_created_at': "ALTER TABLE new_pools_history ADD COLUMN pool_created_at TIMESTAMP WITH TIME ZONE;",
            'fdv_usd': "ALTER TABLE new_pools_history ADD COLUMN fdv_usd NUMERIC(20, 4);",
            'market_cap_usd': "ALTER TABLE new_pools_history ADD COLUMN market_cap_usd NUMERIC(20, 4);",
            'price_change_percentage_h1': "ALTER TABLE new_pools_history ADD COLUMN price_change_percentage_h1 NUMERIC(10, 4);",
            'price_change_percentage_h24': "ALTER TABLE new_pools_history ADD COLUMN price_change_percentage_h24 NUMERIC(10, 4);",
            'transactions_h1_buys': "ALTER TABLE new_pools_history ADD COLUMN transactions_h1_buys INTEGER;",
            'transactions_h1_sells': "ALTER TABLE new_pools_history ADD COLUMN transactions_h1_sells INTEGER;",
            'transactions_h24_buys': "ALTER TABLE new_pools_history ADD COLUMN transactions_h24_buys INTEGER;",
            'transactions_h24_sells': "ALTER TABLE new_pools_history ADD COLUMN transactions_h24_sells INTEGER;",
            'volume_usd_h24': "ALTER TABLE new_pools_history ADD COLUMN volume_usd_h24 NUMERIC(20, 4);",
            'dex_id': "ALTER TABLE new_pools_history ADD COLUMN dex_id VARCHAR(100);",
            'base_token_id': "ALTER TABLE new_pools_history ADD COLUMN base_token_id VARCHAR(255);",
            'quote_token_id': "ALTER TABLE new_pools_history ADD COLUMN quote_token_id VARCHAR(255);",
            'network_id': "ALTER TABLE new_pools_history ADD COLUMN network_id VARCHAR(50);"
        }
        
        # Find missing columns
        missing_columns = set(required_columns.keys()) - current_columns
        
        if not missing_columns:
            logger.info("All required columns already exist!")
            return
        
        logger.info(f"Missing columns: {sorted(missing_columns)}")
        
        # Add missing columns
        for column_name in sorted(missing_columns):
            try:
                logger.info(f"Adding column: {column_name}")
                async with db_manager.get_async_session() as session:
                    await session.execute(text(required_columns[column_name]))
                    await session.commit()
                logger.info(f"✓ Added column: {column_name}")
            except Exception as e:
                logger.error(f"✗ Failed to add column {column_name}: {e}")
                raise
        
        # Add additional indexes for performance
        logger.info("Adding performance indexes...")
        
        indexes_to_add = [
            "CREATE INDEX IF NOT EXISTS idx_new_pools_history_network_id ON new_pools_history(network_id);",
            "CREATE INDEX IF NOT EXISTS idx_new_pools_history_dex_id ON new_pools_history(dex_id);",
            "CREATE INDEX IF NOT EXISTS idx_new_pools_history_type ON new_pools_history(type);",
        ]
        
        for index_sql in indexes_to_add:
            try:
                async with db_manager.get_async_session() as session:
                    await session.execute(text(index_sql))
                    await session.commit()
                logger.info(f"✓ Added index")
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {e}")
        
        # Verify the final structure
        logger.info("Verifying updated table structure...")
        async with db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'new_pools_history' 
                ORDER BY ordinal_position;
            """))
            final_columns_info = result.fetchall()
        
        final_columns = {row[0] for row in final_columns_info}
        logger.info(f"Final columns: {sorted(final_columns)}")
        
        # Check if all required columns are now present
        still_missing = set(required_columns.keys()) - final_columns
        if still_missing:
            logger.error(f"Still missing columns: {sorted(still_missing)}")
            raise Exception("Schema update incomplete")
        
        logger.info("✓ Schema update completed successfully!")
        
    except Exception as e:
        logger.error(f"Schema update failed: {e}")
        raise
    finally:
        if hasattr(db_manager, 'async_engine') and db_manager.async_engine:
            await db_manager.async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_new_pools_history_schema())