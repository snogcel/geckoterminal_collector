#!/usr/bin/env python3
"""
Test script to verify database lock optimizations are working correctly.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.models.core import TradeRecord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_optimized_trade_storage():
    """Test the optimized trade storage functionality."""
    
    # Initialize database manager
    config = DatabaseConfig(
        url="sqlite:///test_optimization.db",
        echo=False
    )
    
    db_manager = SQLAlchemyDatabaseManager(config)
    await db_manager.initialize()
    
    try:
        # Create test trade data
        test_trades = []
        for i in range(100):
            trade = TradeRecord(
                id=f"test_trade_{i}_{int(time.time())}",
                pool_id=f"pool_{i % 5}",  # 5 different pools
                block_number=1000000 + i,
                tx_hash=f"0x{i:064x}",
                tx_from_address=f"0x{(i * 123) % (2**160):040x}",
                from_token_amount=float(100 + i),
                to_token_amount=float(200 + i),
                price_usd=float(1.5 + (i % 100) / 100),
                volume_usd=float(1000 + i * 10),
                side="buy" if i % 2 == 0 else "sell",
                block_timestamp=datetime.now(),
            )
            test_trades.append(trade)
        
        # Test standard storage
        logger.info("Testing standard trade storage...")
        start_time = time.time()
        
        try:
            standard_count = await db_manager.store_trade_data(test_trades[:50])
            standard_time = time.time() - start_time
            logger.info(f"Standard storage: {standard_count} trades in {standard_time:.2f}s")
        except Exception as e:
            logger.error(f"Standard storage failed: {e}")
            standard_time = float('inf')
        
        # Test optimized storage
        logger.info("Testing optimized trade storage...")
        start_time = time.time()
        
        try:
            optimized_count = await db_manager.store_trade_data_optimized(test_trades[50:])
            optimized_time = time.time() - start_time
            logger.info(f"Optimized storage: {optimized_count} trades in {optimized_time:.2f}s")
            
            if standard_time != float('inf') and optimized_time < standard_time:
                improvement = ((standard_time - optimized_time) / standard_time) * 100
                logger.info(f"Performance improvement: {improvement:.1f}%")
            
        except Exception as e:
            logger.error(f"Optimized storage failed: {e}")
        
        # Test database health metrics
        logger.info("Checking database health metrics...")
        health_metrics = await db_manager.get_database_health_metrics()
        
        logger.info("Database Health Metrics:")
        for key, value in health_metrics.items():
            logger.info(f"  {key}: {value}")
        
        # Verify optimizations are applied
        if health_metrics.get('wal_mode_enabled'):
            logger.info("✓ WAL mode is enabled")
        else:
            logger.warning("✗ WAL mode is not enabled")
        
        if health_metrics.get('busy_timeout_ms', 0) > 0:
            logger.info(f"✓ Busy timeout is configured: {health_metrics['busy_timeout_ms']}ms")
        else:
            logger.warning("✗ Busy timeout is not configured")
        
        if health_metrics.get('optimization_status') == 'optimized':
            logger.info("✓ Database is optimized for concurrency")
        else:
            logger.warning("✗ Database needs optimization")
        
    finally:
        await db_manager.close()


async def test_concurrent_access():
    """Test concurrent database access to verify lock avoidance."""
    
    config = DatabaseConfig(
        url="sqlite:///test_concurrent.db",
        echo=False
    )
    
    async def worker_task(worker_id: int, num_trades: int):
        """Simulate a worker storing trades concurrently."""
        db_manager = SQLAlchemyDatabaseManager(config)
        await db_manager.initialize()
        
        try:
            trades = []
            for i in range(num_trades):
                trade = TradeRecord(
                    id=f"worker_{worker_id}_trade_{i}_{int(time.time())}",
                    pool_id=f"pool_{i % 3}",
                    block_number=2000000 + worker_id * 1000 + i,
                    tx_hash=f"0x{(worker_id * 1000 + i):064x}",
                    tx_from_address=f"0x{((worker_id * 1000 + i) * 456) % (2**160):040x}",
                    from_token_amount=float(50 + i),
                    to_token_amount=float(100 + i),
                    price_usd=float(2.0 + (i % 50) / 50),
                    volume_usd=float(500 + i * 5),
                    side="buy" if i % 2 == 0 else "sell",
                    block_timestamp=datetime.now(),
                )
                trades.append(trade)
            
            # Use optimized storage
            start_time = time.time()
            stored_count = await db_manager.store_trade_data_optimized(trades)
            duration = time.time() - start_time
            
            logger.info(f"Worker {worker_id}: stored {stored_count} trades in {duration:.2f}s")
            return stored_count
            
        finally:
            await db_manager.close()
    
    # Run multiple workers concurrently
    logger.info("Testing concurrent database access...")
    start_time = time.time()
    
    tasks = [
        worker_task(1, 50),
        worker_task(2, 75),
        worker_task(3, 60),
        worker_task(4, 40),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time
    
    successful_workers = 0
    total_stored = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Worker {i+1} failed: {result}")
        else:
            successful_workers += 1
            total_stored += result
    
    logger.info(f"Concurrent test completed: {successful_workers}/4 workers successful")
    logger.info(f"Total trades stored: {total_stored} in {total_time:.2f}s")
    
    if successful_workers == 4:
        logger.info("✓ All workers completed successfully - no lock contention detected")
    else:
        logger.warning(f"✗ {4 - successful_workers} workers failed - possible lock contention")


async def main():
    """Run all optimization tests."""
    logger.info("=== Database Lock Optimization Tests ===")
    
    logger.info("\n1. Testing optimized trade storage...")
    await test_optimized_trade_storage()
    
    logger.info("\n2. Testing concurrent access...")
    await test_concurrent_access()
    
    logger.info("\n=== Tests Complete ===")


if __name__ == "__main__":
    asyncio.run(main())