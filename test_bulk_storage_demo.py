#!/usr/bin/env python3
"""
Demo script showing bulk storage with metadata tracking.
"""

import asyncio
import logging
from datetime import datetime

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.models.core import Pool, Token, OHLCVRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_bulk_storage():
    """Demonstrate bulk storage with automatic metadata tracking."""
    
    # Create test database configuration
    db_config = DatabaseConfig(
        url=f"sqlite:///bulk_demo_{int(datetime.utcnow().timestamp())}.db",
        pool_size=5,
        max_overflow=10,
        timeout=30
    )
    
    # Initialize enhanced database manager
    logger.info("Initializing enhanced database manager...")
    db_manager = EnhancedDatabaseManager(db_config)
    await db_manager.initialize()
    
    try:
        # Demo 1: Bulk store pools with metadata tracking
        logger.info("Demo 1: Bulk storing pools with metadata tracking...")
        test_pools = [
            Pool(
                id=f"solana_pool_{i}",
                address=f"pool_address_{i}",
                name=f"Test Pool {i}",
                dex_id="test_dex",
                base_token_id="base_token",
                quote_token_id="quote_token",
                reserve_usd=float(1000 * (i + 1)),
                created_at=datetime.utcnow()
            )
            for i in range(50)  # Test with 50 pools
        ]
        
        pool_result = await db_manager.bulk_store_with_metadata(
            data=test_pools,
            collector_type="pool_collector",
            store_method="store_pools"
        )
        
        logger.info(f"✓ Stored {pool_result.records_collected} pools in {pool_result.execution_time:.2f}s")
        logger.info(f"  Status: {pool_result.status}")
        logger.info(f"  Execution ID: {pool_result.execution_id}")
        
        # Demo 2: Bulk store tokens with metadata tracking
        logger.info("Demo 2: Bulk storing tokens with metadata tracking...")
        test_tokens = [
            Token(
                id=f"solana_token_{i}",
                address=f"token_address_{i}",
                name=f"Test Token {i}",
                symbol=f"TT{i}",
                decimals=9,
                network="solana"
            )
            for i in range(30)  # Test with 30 tokens
        ]
        
        token_result = await db_manager.bulk_store_with_metadata(
            data=test_tokens,
            collector_type="token_collector",
            store_method="store_tokens"
        )
        
        logger.info(f"✓ Stored {token_result.records_collected} tokens in {token_result.execution_time:.2f}s")
        
        # Demo 3: Bulk store OHLCV data with metadata tracking
        logger.info("Demo 3: Bulk storing OHLCV data with metadata tracking...")
        base_timestamp = int(datetime.utcnow().timestamp())
        test_ohlcv = [
            OHLCVRecord(
                pool_id="solana_pool_0",
                timeframe="1h",
                timestamp=base_timestamp + (i * 3600),  # 1 hour intervals
                open_price=100.0 + i,
                high_price=105.0 + i,
                low_price=95.0 + i,
                close_price=102.0 + i,
                volume_usd=1000.0 + (i * 100),
                datetime=datetime.fromtimestamp(base_timestamp + (i * 3600))
            )
            for i in range(24)  # 24 hours of data
        ]
        
        ohlcv_result = await db_manager.bulk_store_with_metadata(
            data=test_ohlcv,
            collector_type="ohlcv_collector",
            store_method="store_ohlcv_data"
        )
        
        logger.info(f"✓ Stored {ohlcv_result.records_collected} OHLCV records in {ohlcv_result.execution_time:.2f}s")
        
        # Demo 4: Get comprehensive statistics
        logger.info("Demo 4: Getting comprehensive collection statistics...")
        stats = await db_manager.get_collection_statistics()
        
        logger.info(f"Collection Statistics for {len(stats)} collectors:")
        for collector_type, collector_stats in stats.items():
            logger.info(f"\n{collector_type.upper()}:")
            logger.info(f"  Total runs: {collector_stats['run_count']}")
            logger.info(f"  Success rate: {collector_stats['success_rate']:.1f}%")
            logger.info(f"  Health score: {collector_stats['health_score']:.1f}")
            logger.info(f"  Total records collected: {collector_stats['total_records_collected']}")
            logger.info(f"  Average execution time: {collector_stats['average_execution_time']:.3f}s")
            logger.info(f"  Recent executions: {len(collector_stats['recent_executions'])}")
            logger.info(f"  Active alerts: {len(collector_stats['active_alerts'])}")
        
        # Demo 5: Performance metrics analysis
        logger.info("\nDemo 5: Performance metrics analysis...")
        for collector_type in stats.keys():
            metrics = await db_manager.get_performance_metrics(collector_type, limit=5)
            logger.info(f"\nTop 5 metrics for {collector_type}:")
            for metric in metrics:
                logger.info(f"  {metric['metric_name']}: {metric['metric_value']} ({metric['timestamp']})")
        
        # Demo 6: Cleanup old metadata (demo only - using 0 days to show functionality)
        logger.info("\nDemo 6: Metadata cleanup capabilities...")
        # Note: Using 0 days would delete everything, so we'll just show the method exists
        logger.info("Cleanup method available: cleanup_old_metadata(days_to_keep=90)")
        
        logger.info("\n✓ All bulk storage demos completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(demo_bulk_storage())