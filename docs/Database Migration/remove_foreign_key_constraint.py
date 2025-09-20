#!/usr/bin/env python3
"""
Temporarily remove the foreign key constraint from new_pools_history table.
This allows us to store history records even when pools don't exist yet.
"""

import asyncio
import logging
import asyncpg

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def remove_foreign_key_constraint():
    """Remove the foreign key constraint from new_pools_history table."""
    
    # Get database connection info from config
    db_url = 'postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector'
    
    try:
        # Connect to database
        conn = await asyncpg.connect(db_url)
        logger.info("Connected to PostgreSQL database")
        
        # Check if the constraint exists
        logger.info("Checking for existing foreign key constraint...")
        
        constraint_check = await conn.fetch("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'new_pools_history' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'new_pools_history_pool_id_fkey';
        """)
        
        if constraint_check:
            logger.info("Found foreign key constraint, removing it...")
            
            # Drop the foreign key constraint
            await conn.execute("""
                ALTER TABLE new_pools_history 
                DROP CONSTRAINT IF EXISTS new_pools_history_pool_id_fkey;
            """)
            
            logger.info("✓ Foreign key constraint removed successfully!")
        else:
            logger.info("No foreign key constraint found to remove")
        
        # Verify the constraint is gone
        final_check = await conn.fetch("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'new_pools_history' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'new_pools_history_pool_id_fkey';
        """)
        
        if not final_check:
            logger.info("✓ Confirmed: Foreign key constraint has been removed")
        else:
            logger.error("✗ Foreign key constraint still exists")
        
    except Exception as e:
        logger.error(f"Failed to remove foreign key constraint: {e}")
        raise
    finally:
        if 'conn' in locals():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(remove_foreign_key_constraint())