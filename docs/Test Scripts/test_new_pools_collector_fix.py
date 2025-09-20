#!/usr/bin/env python3
"""
Test the new pools collector after schema fix.
"""

import asyncio
import logging
from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_new_pools_collector():
    """Test the new pools collector with the fixed schema."""
    
    try:
        # Initialize config manager
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        logger.info("Database manager initialized")
        
        # Create new pools collector for Solana
        collector = NewPoolsCollector(
            config=config,
            db_manager=db_manager,
            network='solana'
        )
        
        logger.info("Starting new pools collection test...")
        
        # Run collection
        result = await collector.collect()
        
        if result.success:
            logger.info(f"✓ Collection successful!")
            logger.info(f"  Records collected: {result.records_collected}")
            logger.info(f"  Metadata: {result.metadata}")
            if result.errors:
                logger.warning(f"  Errors encountered: {result.errors}")
        else:
            logger.error(f"✗ Collection failed!")
            logger.error(f"  Errors: {result.errors}")
        
        return result.success
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    finally:
        if 'db_manager' in locals():
            await db_manager.close()


if __name__ == "__main__":
    success = asyncio.run(test_new_pools_collector())
    if success:
        print("\n✓ New pools collector test PASSED")
    else:
        print("\n✗ New pools collector test FAILED")