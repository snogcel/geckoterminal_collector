"""
Example showing how to integrate lock optimization into existing collectors.
"""

import asyncio
import logging
from typing import List

from gecko_terminal_collector.config.models import DatabaseConfig, CollectionConfig
from gecko_terminal_collector.database.lock_optimized_manager import LockOptimizedDatabaseManager
from gecko_terminal_collector.utils.batch_processor import TradeDataBatchProcessor
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.models.core import TradeRecord

logger = logging.getLogger(__name__)


class OptimizedTradeCollector(TradeCollector):
    """
    Enhanced trade collector with lock optimization and batch processing.
    """
    
    def __init__(self, config: CollectionConfig, db_manager: LockOptimizedDatabaseManager, **kwargs):
        """Initialize optimized trade collector."""
        super().__init__(config, db_manager, **kwargs)
        
        # Initialize batch processor for trades
        self.trade_batch_processor = TradeDataBatchProcessor(
            db_manager,
            config=None  # Use default batch config
        )
        
        # Track optimization metrics
        self.optimization_stats = {
            'batches_processed': 0,
            'total_trades_stored': 0,
            'lock_retries': 0,
        }
    
    async def store_trade_data_optimized(self, trades: List[TradeRecord]) -> int:
        """
        Store trade data using optimized batch processing.
        
        This method replaces direct database calls with batch processing
        to minimize lock contention.
        """
        if not trades:
            return 0
        
        try:
            # Use batch processor instead of direct database calls
            await self.trade_batch_processor.add_trades(trades)
            
            # For immediate processing, flush the batch
            stored_count = await self.trade_batch_processor.flush_trades()
            
            self.optimization_stats['batches_processed'] += 1
            self.optimization_stats['total_trades_stored'] += stored_count
            
            logger.info(f"Stored {stored_count} trades using optimized batch processing")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error in optimized trade storage: {e}")
            # Fall back to original method if optimization fails
            return await self.db_manager.store_trade_data(trades)
    
    async def collect_and_store_optimized(self, pool_addresses: List[str]) -> dict:
        """
        Collect and store trade data with optimization.
        
        This demonstrates the full optimized collection workflow.
        """
        results = {
            'pools_processed': 0,
            'trades_collected': 0,
            'trades_stored': 0,
            'errors': [],
        }
        
        for pool_address in pool_addresses:
            try:
                # Collect trades for this pool (using existing collection logic)
                trades = await self._collect_trades_for_pool(pool_address)
                
                if trades:
                    # Store using optimized method
                    stored_count = await self.store_trade_data_optimized(trades)
                    
                    results['trades_collected'] += len(trades)
                    results['trades_stored'] += stored_count
                
                results['pools_processed'] += 1
                
            except Exception as e:
                error_msg = f"Error processing pool {pool_address}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Flush any remaining batched trades
        await self.trade_batch_processor.flush_trades()
        
        return results
    
    async def _collect_trades_for_pool(self, pool_address: str) -> List[TradeRecord]:
        """
        Collect trades for a specific pool.
        
        This is a placeholder - replace with your actual collection logic.
        """
        # This would contain your actual API calls and data processing
        # For demonstration, return empty list
        return []
    
    def get_optimization_stats(self) -> dict:
        """Get optimization statistics."""
        batch_stats = self.trade_batch_processor.get_stats()
        
        return {
            **self.optimization_stats,
            'batch_processor_stats': batch_stats,
        }


async def demonstrate_integration():
    """Demonstrate integration of lock optimization with existing collectors."""
    
    # Initialize optimized database manager
    db_config = DatabaseConfig(
        url="sqlite:///integration_demo.db",
        echo=False
    )
    
    db_manager = LockOptimizedDatabaseManager(db_config)
    await db_manager.initialize()
    
    try:
        # Initialize collection config
        collection_config = CollectionConfig(
            # Add your collection configuration here
        )
        
        # Create optimized collector
        collector = OptimizedTradeCollector(
            config=collection_config,
            db_manager=db_manager
        )
        
        # Simulate trade collection and storage
        sample_pools = [
            "solana_pool_1",
            "solana_pool_2", 
            "solana_pool_3",
        ]
        
        logger.info("Starting optimized trade collection...")
        
        # Method 1: Collect and store with optimization
        results = await collector.collect_and_store_optimized(sample_pools)
        logger.info(f"Collection results: {results}")
        
        # Method 2: Direct optimized storage of sample data
        sample_trades = []
        for i in range(100):
            trade = TradeRecord(
                id=f"integration_demo_trade_{i}",
                pool_id=f"pool_{i % 3}",
                block_number=3000000 + i,
                tx_hash=f"0x{i:064x}",
                tx_from_address=f"0x{(i * 456) % (2**160):040x}",
                from_token_amount=float(50 + i),
                to_token_amount=float(100 + i),
                price_usd=float(2.0 + (i % 50) / 50),
                volume_usd=float(500 + i * 5),
                side="buy" if i % 2 == 0 else "sell",
                block_timestamp=datetime.now(),
            )
            sample_trades.append(trade)
        
        stored_count = await collector.store_trade_data_optimized(sample_trades)
        logger.info(f"Stored {stored_count} sample trades")
        
        # Get optimization statistics
        stats = collector.get_optimization_stats()
        logger.info(f"Optimization stats: {stats}")
        
        # Get database health metrics
        health_metrics = await db_manager.get_lock_contention_metrics()
        logger.info(f"Database health: {health_metrics}")
        
    finally:
        await db_manager.close()


async def compare_performance():
    """Compare performance between standard and optimized approaches."""
    
    from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
    
    # Test data
    test_trades = []
    for i in range(500):
        trade = TradeRecord(
            id=f"perf_test_trade_{i}",
            pool_id=f"pool_{i % 5}",
            block_number=4000000 + i,
            tx_hash=f"0x{i:064x}",
            tx_from_address=f"0x{(i * 789) % (2**160):040x}",
            from_token_amount=float(25 + i),
            to_token_amount=float(50 + i),
            price_usd=float(1.0 + (i % 25) / 25),
            volume_usd=float(250 + i * 2.5),
            side="buy" if i % 2 == 0 else "sell",
            block_timestamp=datetime.now(),
        )
        test_trades.append(trade)
    
    # Test standard approach
    db_config = DatabaseConfig(url="sqlite:///standard_perf.db", echo=False)
    standard_manager = SQLAlchemyDatabaseManager(db_config)
    await standard_manager.initialize()
    
    try:
        start_time = datetime.now()
        await standard_manager.store_trade_data(test_trades)
        standard_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Standard approach took {standard_time:.2f} seconds")
    finally:
        await standard_manager.close()
    
    # Test optimized approach
    db_config = DatabaseConfig(url="sqlite:///optimized_perf.db", echo=False)
    optimized_manager = LockOptimizedDatabaseManager(db_config)
    await optimized_manager.initialize()
    
    try:
        start_time = datetime.now()
        await optimized_manager.store_trade_data_optimized(test_trades)
        optimized_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Optimized approach took {optimized_time:.2f} seconds")
        
        improvement = ((standard_time - optimized_time) / standard_time) * 100
        logger.info(f"Performance improvement: {improvement:.1f}%")
        
    finally:
        await optimized_manager.close()


async def main():
    """Run integration demonstrations."""
    logging.basicConfig(level=logging.INFO)
    
    logger.info("=== Lock Optimization Integration Demo ===")
    
    logger.info("\n1. Demonstrating integration with existing collectors...")
    await demonstrate_integration()
    
    logger.info("\n2. Comparing performance...")
    await compare_performance()
    
    logger.info("\n=== Integration Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())