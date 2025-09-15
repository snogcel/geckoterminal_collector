"""
Example demonstrating optimized database usage with lock avoidance strategies.
"""

import asyncio
import logging
from datetime import datetime
from typing import List

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.lock_optimized_manager import LockOptimizedDatabaseManager
from gecko_terminal_collector.utils.batch_processor import TradeDataBatchProcessor, PoolDataBatchProcessor
from gecko_terminal_collector.models.core import TradeRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_optimized_trade_storage():
    """Demonstrate optimized trade data storage with lock avoidance."""
    
    # Initialize optimized database manager
    config = DatabaseConfig(
        url="sqlite:///optimized_demo.db",
        echo=False
    )
    
    db_manager = LockOptimizedDatabaseManager(config)
    await db_manager.initialize()
    
    try:
        # Create batch processor for trades
        trade_processor = TradeDataBatchProcessor(
            db_manager,
            config=None  # Use default batch config
        )
        
        # Simulate concurrent trade data collection
        sample_trades = []
        for i in range(1000):
            trade = TradeRecord(
                id=f"solana_trade_{i}_{int(datetime.now().timestamp())}",
                pool_id=f"pool_{i % 10}",  # 10 different pools
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
            sample_trades.append(trade)
        
        # Method 1: Add trades individually (will be batched automatically)
        logger.info("Adding trades individually with automatic batching...")
        start_time = datetime.now()
        
        for trade in sample_trades[:500]:
            await trade_processor.add_trade(trade)
        
        # Flush remaining trades
        await trade_processor.flush_trades()
        
        individual_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Individual addition took {individual_time:.2f} seconds")
        
        # Method 2: Add trades in bulk
        logger.info("Adding trades in bulk...")
        start_time = datetime.now()
        
        await trade_processor.add_trades(sample_trades[500:])
        await trade_processor.flush_trades()
        
        bulk_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Bulk addition took {bulk_time:.2f} seconds")
        
        # Method 3: Direct optimized storage (bypassing batch processor)
        logger.info("Using direct optimized storage...")
        start_time = datetime.now()
        
        # Create new trades for direct storage test
        direct_trades = []
        for i in range(1000, 1200):
            trade = TradeRecord(
                id=f"solana_direct_trade_{i}_{int(datetime.now().timestamp())}",
                pool_id=f"pool_{i % 10}",
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
            direct_trades.append(trade)
        
        stored_count = await db_manager.store_trade_data_optimized(direct_trades)
        
        direct_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Direct optimized storage took {direct_time:.2f} seconds, stored {stored_count} trades")
        
        # Get processing statistics
        stats = trade_processor.get_stats()
        logger.info(f"Batch processor stats: {stats}")
        
        # Get lock contention metrics
        metrics = await db_manager.get_lock_contention_metrics()
        logger.info(f"Lock contention metrics: {metrics}")
        
    finally:
        await db_manager.close()


async def demonstrate_concurrent_access_patterns():
    """Demonstrate handling concurrent database access patterns."""
    
    config = DatabaseConfig(
        url="sqlite:///concurrent_demo.db",
        echo=False
    )
    
    db_manager = LockOptimizedDatabaseManager(config)
    await db_manager.initialize()
    
    try:
        # Simulate multiple concurrent collectors
        async def collector_task(collector_id: int, num_trades: int):
            """Simulate a collector task storing trades."""
            trade_processor = TradeDataBatchProcessor(db_manager)
            
            trades = []
            for i in range(num_trades):
                trade = TradeRecord(
                    id=f"collector_{collector_id}_trade_{i}_{int(datetime.now().timestamp())}",
                    pool_id=f"pool_{i % 5}",
                    block_number=2000000 + collector_id * 1000 + i,
                    tx_hash=f"0x{(collector_id * 1000 + i):064x}",
                    tx_from_address=f"0x{((collector_id * 1000 + i) * 123) % (2**160):040x}",
                    from_token_amount=float(100 + i),
                    to_token_amount=float(200 + i),
                    price_usd=float(1.5 + (i % 100) / 100),
                    volume_usd=float(1000 + i * 10),
                    side="buy" if i % 2 == 0 else "sell",
                    block_timestamp=datetime.now(),
                )
                trades.append(trade)
            
            # Add trades with some delay to simulate real collection
            for trade in trades:
                await trade_processor.add_trade(trade)
                if len(trades) > 50:  # Add small delay for larger batches
                    await asyncio.sleep(0.01)
            
            await trade_processor.flush_trades()
            
            stats = trade_processor.get_stats()
            logger.info(f"Collector {collector_id} completed: {stats}")
        
        # Run multiple collectors concurrently
        logger.info("Starting concurrent collectors...")
        start_time = datetime.now()
        
        tasks = [
            collector_task(1, 100),
            collector_task(2, 150),
            collector_task(3, 200),
            collector_task(4, 75),
        ]
        
        await asyncio.gather(*tasks)
        
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"All concurrent collectors completed in {total_time:.2f} seconds")
        
        # Check final metrics
        metrics = await db_manager.get_lock_contention_metrics()
        logger.info(f"Final lock contention metrics: {metrics}")
        
    finally:
        await db_manager.close()


async def main():
    """Run optimization demonstrations."""
    logger.info("=== Optimized Database Usage Demonstration ===")
    
    logger.info("\n1. Demonstrating optimized trade storage...")
    await demonstrate_optimized_trade_storage()
    
    logger.info("\n2. Demonstrating concurrent access patterns...")
    await demonstrate_concurrent_access_patterns()
    
    logger.info("\n=== Demonstration Complete ===")


if __name__ == "__main__":
    asyncio.run(main())