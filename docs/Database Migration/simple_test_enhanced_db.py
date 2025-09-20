#!/usr/bin/env python3
"""
Simple test script for enhanced database manager.
"""

import asyncio
import logging
from datetime import datetime

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager, CollectionResult

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def simple_test():
    """Simple test of the enhanced database manager."""
    
    # Create test database configuration
    db_config = DatabaseConfig(
        url=f"sqlite:///simple_test_{int(datetime.utcnow().timestamp())}.db",
        pool_size=5,
        max_overflow=10,
        timeout=30
    )
    
    logger.info("Initializing enhanced database manager...")
    db_manager = EnhancedDatabaseManager(db_config)
    
    try:
        await db_manager.initialize()
        logger.info("Database manager initialized successfully")
        
        # Test storing a simple collection result
        result = CollectionResult(
            collector_type="simple_test",
            execution_id=f"exec_{int(datetime.utcnow().timestamp())}",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="success",
            records_collected=10,
            errors=[],
            warnings=[],
            metadata={"test": True}
        )
        
        logger.info("Storing collection result...")
        await db_manager.store_collection_run(result)
        logger.info("✓ Collection result stored successfully")
        
        # Test getting statistics
        logger.info("Getting collection statistics...")
        stats = await db_manager.get_collection_statistics()
        logger.info(f"✓ Retrieved statistics for {len(stats)} collectors")
        
        for collector_type, collector_stats in stats.items():
            logger.info(f"Collector: {collector_type}, Runs: {collector_stats['run_count']}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()
        logger.info("Database manager closed")


if __name__ == "__main__":
    asyncio.run(simple_test())