#!/usr/bin/env python3
"""
Test script for enhanced database manager with metadata population.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager, CollectionResult
from gecko_terminal_collector.database.migrations import MigrationManager
from gecko_terminal_collector.models.core import Pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_enhanced_database():
    """Test the enhanced database manager functionality."""
    
    # Create test database configuration
    db_config = DatabaseConfig(
        url=f"sqlite:///test_enhanced_metadata_{int(datetime.utcnow().timestamp())}.db",
        pool_size=5,
        max_overflow=10,
        timeout=30
    )
    
    # Run migrations
    logger.info("Running database migrations...")
    migration_manager = MigrationManager(db_config)
    try:
        migration_manager.run_migrations()
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return
    
    # Initialize enhanced database manager
    logger.info("Initializing enhanced database manager...")
    db_manager = EnhancedDatabaseManager(db_config)
    await db_manager.initialize()
    
    try:
        # Test 1: Store a successful collection run
        logger.info("Testing successful collection run...")
        success_result = CollectionResult(
            collector_type="test_collector",
            execution_id=f"test_exec_{int(datetime.utcnow().timestamp())}_001",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="success",
            records_collected=100,
            errors=[],
            warnings=["Minor warning about data quality"],
            metadata={
                "api_calls": 5,
                "processing_time": 2.5,
                "memory_usage": 1024000
            }
        )
        
        await db_manager.store_collection_run(success_result)
        logger.info("✓ Successfully stored collection run metadata")
        
        # Test 2: Store a failed collection run
        logger.info("Testing failed collection run...")
        failure_result = CollectionResult(
            collector_type="test_collector",
            execution_id=f"test_exec_{int(datetime.utcnow().timestamp())}_002",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="failure",
            records_collected=0,
            errors=["Rate limit exceeded", "Connection timeout"],
            warnings=[],
            metadata={
                "api_calls": 10,
                "processing_time": 0.1
            }
        )
        
        await db_manager.store_collection_run(failure_result)
        logger.info("✓ Successfully stored failed collection run metadata")
        
        # Test 3: Test bulk storage with metadata
        logger.info("Testing bulk storage with metadata...")
        test_pools = [
            Pool(
                id=f"test_pool_{i}",
                address=f"test_address_{i}",
                name=f"Test Pool {i}",
                dex_id="test_dex",
                base_token_id="base_token",
                quote_token_id="quote_token",
                reserve_usd=1000.0,
                created_at=datetime.utcnow()
            )
            for i in range(5)
        ]
        
        bulk_result = await db_manager.bulk_store_with_metadata(
            data=test_pools,
            collector_type="pool_collector",
            store_method="store_pools"
        )
        
        logger.info(f"✓ Bulk storage completed: {bulk_result.records_collected} records stored")
        
        # Test 4: Get collection statistics
        logger.info("Testing collection statistics...")
        stats = await db_manager.get_collection_statistics()
        
        for collector_type, collector_stats in stats.items():
            logger.info(f"Collector: {collector_type}")
            logger.info(f"  Run count: {collector_stats['run_count']}")
            logger.info(f"  Success rate: {collector_stats['success_rate']:.1f}%")
            logger.info(f"  Health score: {collector_stats['health_score']:.1f}")
            logger.info(f"  Total records: {collector_stats['total_records_collected']}")
            logger.info(f"  Active alerts: {len(collector_stats['active_alerts'])}")
        
        # Test 5: Get performance metrics
        logger.info("Testing performance metrics...")
        metrics = await db_manager.get_performance_metrics("test_collector")
        
        logger.info(f"Retrieved {len(metrics)} performance metrics")
        for metric in metrics[:3]:  # Show first 3
            logger.info(f"  {metric['metric_name']}: {metric['metric_value']} at {metric['timestamp']}")
        
        # Test 6: Test alert resolution
        logger.info("Testing alert resolution...")
        # Get an alert ID from the statistics
        test_collector_stats = stats.get("test_collector", {})
        active_alerts = test_collector_stats.get("active_alerts", [])
        
        if active_alerts:
            alert_id = active_alerts[0]["alert_id"]
            resolved = await db_manager.resolve_system_alert(alert_id, "test_user")
            if resolved:
                logger.info(f"✓ Successfully resolved alert: {alert_id}")
            else:
                logger.warning(f"Failed to resolve alert: {alert_id}")
        
        logger.info("✓ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_enhanced_database())