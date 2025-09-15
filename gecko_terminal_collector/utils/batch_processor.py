"""
Batch processing utilities for optimized database operations.
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    max_batch_size: int = 100
    max_wait_time: float = 5.0  # seconds
    max_retries: int = 3
    retry_delay: float = 0.5  # seconds


class BatchProcessor(Generic[T]):
    """
    Generic batch processor for optimizing database operations.
    
    Collects items and processes them in batches to reduce database
    lock contention and improve throughput.
    """
    
    def __init__(
        self,
        processor_func: Callable[[List[T]], int],
        config: Optional[BatchConfig] = None
    ):
        """
        Initialize batch processor.
        
        Args:
            processor_func: Function to process batches of items
            config: Batch processing configuration
        """
        self.processor_func = processor_func
        self.config = config or BatchConfig()
        
        self.pending_items: List[T] = []
        self.last_flush_time = datetime.now()
        self.total_processed = 0
        self.total_batches = 0
        
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
    
    async def add_item(self, item: T) -> None:
        """Add item to batch for processing."""
        async with self._lock:
            self.pending_items.append(item)
            
            # Check if we should flush immediately
            if len(self.pending_items) >= self.config.max_batch_size:
                await self._flush_batch()
            elif not self._flush_task:
                # Schedule delayed flush
                self._flush_task = asyncio.create_task(self._delayed_flush())
    
    async def add_items(self, items: List[T]) -> None:
        """Add multiple items to batch for processing."""
        if not items:
            return
        
        async with self._lock:
            self.pending_items.extend(items)
            
            # Process in chunks if we have too many items
            while len(self.pending_items) >= self.config.max_batch_size:
                batch = self.pending_items[:self.config.max_batch_size]
                self.pending_items = self.pending_items[self.config.max_batch_size:]
                
                await self._process_batch(batch)
            
            # Schedule flush for remaining items
            if self.pending_items and not self._flush_task:
                self._flush_task = asyncio.create_task(self._delayed_flush())
    
    async def flush(self) -> int:
        """Flush all pending items immediately."""
        async with self._lock:
            if self._flush_task:
                self._flush_task.cancel()
                self._flush_task = None
            
            return await self._flush_batch()
    
    async def _delayed_flush(self) -> None:
        """Flush batch after configured wait time."""
        try:
            await asyncio.sleep(self.config.max_wait_time)
            
            async with self._lock:
                await self._flush_batch()
                self._flush_task = None
                
        except asyncio.CancelledError:
            pass
    
    async def _flush_batch(self) -> int:
        """Flush current batch of items."""
        if not self.pending_items:
            return 0
        
        batch = self.pending_items.copy()
        self.pending_items.clear()
        self.last_flush_time = datetime.now()
        
        return await self._process_batch(batch)
    
    async def _process_batch(self, batch: List[T]) -> int:
        """Process a batch of items with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                processed_count = await self.processor_func(batch)
                
                self.total_processed += processed_count
                self.total_batches += 1
                
                logger.debug(f"Processed batch of {len(batch)} items, {processed_count} stored")
                return processed_count
                
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Batch processing failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Batch processing failed after {self.config.max_retries} attempts: {e}")
                    raise
        
        return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        return {
            'total_processed': self.total_processed,
            'total_batches': self.total_batches,
            'pending_items': len(self.pending_items),
            'avg_batch_size': self.total_processed / max(self.total_batches, 1),
            'last_flush_time': self.last_flush_time.isoformat(),
        }


class TradeDataBatchProcessor:
    """Specialized batch processor for trade data."""
    
    def __init__(self, database_manager, config: Optional[BatchConfig] = None):
        """Initialize trade data batch processor."""
        self.database_manager = database_manager
        self.config = config or BatchConfig(max_batch_size=200, max_wait_time=3.0)
        
        self.processor = BatchProcessor(
            self._process_trade_batch,
            self.config
        )
    
    async def add_trade(self, trade_record) -> None:
        """Add single trade record for batch processing."""
        await self.processor.add_item(trade_record)
    
    async def add_trades(self, trade_records: List) -> None:
        """Add multiple trade records for batch processing."""
        await self.processor.add_items(trade_records)
    
    async def flush_trades(self) -> int:
        """Flush all pending trades immediately."""
        return await self.processor.flush()
    
    async def _process_trade_batch(self, trades: List) -> int:
        """Process batch of trade records."""
        if hasattr(self.database_manager, 'store_trade_data_optimized'):
            return await self.database_manager.store_trade_data_optimized(trades)
        else:
            return await self.database_manager.store_trade_data(trades)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trade batch processing statistics."""
        return self.processor.get_stats()


class PoolDataBatchProcessor:
    """Specialized batch processor for pool data."""
    
    def __init__(self, database_manager, config: Optional[BatchConfig] = None):
        """Initialize pool data batch processor."""
        self.database_manager = database_manager
        self.config = config or BatchConfig(max_batch_size=50, max_wait_time=2.0)
        
        self.processor = BatchProcessor(
            self._process_pool_batch,
            self.config
        )
    
    async def add_pool(self, pool_record) -> None:
        """Add single pool record for batch processing."""
        await self.processor.add_item(pool_record)
    
    async def add_pools(self, pool_records: List) -> None:
        """Add multiple pool records for batch processing."""
        await self.processor.add_items(pool_records)
    
    async def flush_pools(self) -> int:
        """Flush all pending pools immediately."""
        return await self.processor.flush()
    
    async def _process_pool_batch(self, pools: List) -> int:
        """Process batch of pool records."""
        if hasattr(self.database_manager, 'store_pools_lock_optimized'):
            return await self.database_manager.store_pools_lock_optimized(pools)
        else:
            return await self.database_manager.store_pools(pools)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool batch processing statistics."""
        return self.processor.get_stats()