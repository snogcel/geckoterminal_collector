"""
Lock-optimized database manager with advanced SQLite concurrency handling.
"""

import asyncio
import logging
import time
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Set
from decimal import Decimal
from datetime import datetime

from sqlalchemy import create_engine, text, and_
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Pool as PoolModel, Trade as TradeModel
from gecko_terminal_collector.models.core import TradeRecord

logger = logging.getLogger(__name__)


class LockOptimizedDatabaseManager(EnhancedSQLAlchemyDatabaseManager):
    """
    Database manager optimized for SQLite lock avoidance with advanced batching strategies.
    """
    
    def __init__(self, config):
        """Initialize lock-optimized database manager."""
        super().__init__(config)
        
        # Batch processing configuration
        self.batch_size = 100
        self.batch_timeout = 5.0  # seconds
        self.pending_batches = {}
        
        # Lock avoidance settings
        self.max_lock_wait = 30.0  # seconds
        self.lock_retry_delay = 0.1  # seconds
        
        # Configure SQLite for optimal concurrency
        self._configure_sqlite_optimizations()
    
    def _configure_sqlite_optimizations(self):
        """Configure SQLite for maximum concurrency and minimal lock contention."""
        try:
            if "sqlite" in str(self.connection.engine.url):
                with self.connection.engine.connect() as conn:
                    # WAL mode for better concurrency
                    conn.execute(text("PRAGMA journal_mode=WAL"))
                    
                    # Optimize for concurrent access
                    conn.execute(text("PRAGMA synchronous=NORMAL"))
                    conn.execute(text("PRAGMA cache_size=20000"))  # 20MB cache
                    conn.execute(text("PRAGMA temp_store=memory"))
                    conn.execute(text("PRAGMA mmap_size=268435456"))  # 256MB mmap
                    
                    # Reduce lock contention
                    conn.execute(text("PRAGMA busy_timeout=30000"))  # 30 second timeout
                    conn.execute(text("PRAGMA wal_autocheckpoint=1000"))
                    
                    # Optimize page size for better performance
                    conn.execute(text("PRAGMA page_size=4096"))
                    
                    conn.commit()
                logger.info("Applied SQLite concurrency optimizations")
        except Exception as e:
            logger.warning(f"Failed to apply SQLite optimizations: {e}")
    
    @contextmanager
    def optimized_session(self, read_only=False):
        """
        Get database session with optimized settings for lock avoidance.
        
        Args:
            read_only: If True, optimize for read operations
        """
        session = self.connection.get_session()
        try:
            if read_only:
                # For read operations, use shared cache and shorter timeout
                session.execute(text("PRAGMA query_only=1"))
            else:
                # For write operations, use immediate transaction
                session.execute(text("BEGIN IMMEDIATE"))
            
            yield session
            
            if not read_only:
                session.commit()
                
        except OperationalError as e:
            if "database is locked" in str(e).lower():
                logger.warning(f"Database lock detected, implementing backoff strategy")
                session.rollback()
                raise
            else:
                session.rollback()
                raise
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    async def store_trade_data_optimized(self, data: List[TradeRecord]) -> int:
        """
        Optimized trade data storage with advanced lock avoidance and batching.
        
        Key optimizations:
        1. Pre-filter existing records in memory when possible
        2. Use bulk operations with conflict resolution
        3. Implement intelligent retry with exponential backoff
        4. Minimize transaction time
        """
        if not data:
            return 0
        
        return await self._retry_with_intelligent_backoff(
            self._store_trades_batch_optimized, 
            data
        )
    
    async def _store_trades_batch_optimized(self, data: List[TradeRecord]) -> int:
        """Internal optimized batch storage for trades."""
        stored_count = 0
        
        # Step 1: Pre-process and validate data
        validated_records = []
        ids_to_check = []
        
        for record in data:
            validation_errors = self._validate_trade_record(record)
            if validation_errors:
                logger.warning(f"Skipping invalid trade record {record.id}: {validation_errors}")
                continue
            
            validated_records.append(record)
            ids_to_check.append(record.id)
        
        if not validated_records:
            return 0
        
        # Step 2: Quick existence check with minimal lock time
        existing_ids = await self._get_existing_trade_ids_fast(ids_to_check)
        
        # Step 3: Filter to only new records
        new_records = [
            record for record in validated_records 
            if record.id not in existing_ids
        ]
        
        if not new_records:
            logger.info(f"All {len(validated_records)} trade records already exist, skipping")
            return 0
        
        # Step 4: Bulk insert with conflict handling
        stored_count = await self._bulk_insert_trades_with_conflict_resolution(new_records)
        
        logger.info(f"Stored {stored_count} new trades, skipped {len(existing_ids)} duplicates")
        return stored_count
    
    async def _get_existing_trade_ids_fast(self, ids_to_check: List[str]) -> Set[str]:
        """Fast existence check with minimal lock time."""
        if not ids_to_check:
            return set()
        
        existing_ids = set()
        
        # Process in smaller batches to minimize lock time
        batch_size = 500
        for i in range(0, len(ids_to_check), batch_size):
            batch_ids = ids_to_check[i:i + batch_size]
            
            with self.optimized_session(read_only=True) as session:
                try:
                    # Use efficient query with index
                    result = session.query(TradeModel.id).filter(
                        TradeModel.id.in_(batch_ids)
                    ).all()
                    
                    batch_existing = {row.id for row in result}
                    existing_ids.update(batch_existing)
                    
                except Exception as e:
                    logger.warning(f"Error checking existing trade IDs: {e}")
                    # If we can't check, assume they don't exist and let conflict resolution handle it
                    pass
        
        return existing_ids
    
    async def _bulk_insert_trades_with_conflict_resolution(self, records: List[TradeRecord]) -> int:
        """
        Bulk insert trades with intelligent conflict resolution.
        
        Uses SQLite's INSERT OR IGNORE for atomic conflict handling.
        """
        if not records:
            return 0
        
        stored_count = 0
        
        with self.optimized_session() as session:
            try:
                # Prepare bulk insert data
                trade_data = []
                for record in records:
                    # Apply network prefix to pool_id
                    prefix, _, _ = record.id.partition('_')
                    pool_id_with_prefix = prefix + '_' + record.pool_id
                    
                    trade_data.append({
                        'id': record.id,
                        'pool_id': pool_id_with_prefix,
                        'block_number': record.block_number,
                        'tx_hash': record.tx_hash,
                        'tx_from_address': record.tx_from_address,
                        'from_token_amount': record.from_token_amount,
                        'to_token_amount': record.to_token_amount,
                        'price_usd': record.price_usd,
                        'volume_usd': record.volume_usd,
                        'side': record.side,
                        'block_timestamp': record.block_timestamp,
                    })
                
                # Use SQLite's INSERT OR IGNORE for atomic conflict handling
                stmt = sqlite_insert(TradeModel).values(trade_data)
                stmt = stmt.on_conflict_do_nothing()
                
                result = session.execute(stmt)
                stored_count = result.rowcount
                
                logger.debug(f"Bulk inserted {stored_count} trades using conflict resolution")
                
            except Exception as e:
                logger.error(f"Error in bulk trade insert: {e}")
                raise
        
        return stored_count
    
    async def _retry_with_intelligent_backoff(self, func, *args, **kwargs):
        """
        Intelligent retry with exponential backoff and jitter for lock contention.
        """
        max_retries = 5
        base_delay = 0.1
        max_delay = 5.0
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
                
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
                    total_delay = delay + jitter
                    
                    logger.warning(
                        f"Database locked, retrying in {total_delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    
                    await asyncio.sleep(total_delay)
                    continue
                else:
                    raise
            except Exception as e:
                # Don't retry non-lock errors
                raise
        
        raise OperationalError("Max retries exceeded for database lock", None, None)
    
    def _validate_trade_record(self, record: TradeRecord) -> List[str]:
        """Validate trade record for data integrity."""
        errors = []
        
        if not record.id:
            errors.append("Trade ID is required")
        
        if not record.pool_id:
            errors.append("Pool ID is required")
        
        if record.volume_usd is not None and record.volume_usd < 0:
            errors.append("Volume USD cannot be negative")
        
        if record.price_usd is not None and record.price_usd < 0:
            errors.append("Price USD cannot be negative")
        
        return errors
    
    async def store_pools_lock_optimized(self, pools: List[PoolModel]) -> int:
        """
        Lock-optimized pool storage with minimal transaction time.
        """
        if not pools:
            return 0
        
        return await self._retry_with_intelligent_backoff(
            self._store_pools_batch_optimized,
            pools
        )
    
    async def _store_pools_batch_optimized(self, pools: List[PoolModel]) -> int:
        """Internal optimized batch storage for pools."""
        stored_count = 0
        
        # Pre-filter existing pools
        pool_ids = [pool.id for pool in pools]
        existing_ids = await self._get_existing_pool_ids_fast(pool_ids)
        
        new_pools = [pool for pool in pools if pool.id not in existing_ids]
        update_pools = [pool for pool in pools if pool.id in existing_ids]
        
        if new_pools:
            with self.optimized_session() as session:
                try:
                    # Use bulk_insert_mappings for new pools
                    pool_dicts = [self._pool_to_dict(pool) for pool in new_pools]
                    session.bulk_insert_mappings(PoolModel, pool_dicts)
                    stored_count += len(new_pools)
                    
                except IntegrityError:
                    # Handle race condition - some pools were created between check and insert
                    session.rollback()
                    
                    # Fall back to individual upserts
                    for pool in new_pools:
                        try:
                            session.merge(pool)
                            stored_count += 1
                        except IntegrityError:
                            logger.debug(f"Pool {pool.id} created by another process")
        
        if update_pools:
            with self.optimized_session() as session:
                try:
                    # Use bulk_update_mappings for existing pools
                    pool_dicts = [self._pool_to_dict(pool) for pool in update_pools]
                    session.bulk_update_mappings(PoolModel, pool_dicts)
                    
                except Exception as e:
                    logger.warning(f"Bulk update failed, falling back to individual updates: {e}")
                    session.rollback()
                    
                    # Fall back to individual updates
                    for pool in update_pools:
                        session.merge(pool)
        
        logger.info(f"Stored {len(new_pools)} new pools, updated {len(update_pools)} existing pools")
        return stored_count
    
    async def _get_existing_pool_ids_fast(self, pool_ids: List[str]) -> Set[str]:
        """Fast pool existence check."""
        if not pool_ids:
            return set()
        
        existing_ids = set()
        
        with self.optimized_session(read_only=True) as session:
            try:
                result = session.query(PoolModel.id).filter(
                    PoolModel.id.in_(pool_ids)
                ).all()
                existing_ids = {row.id for row in result}
            except Exception as e:
                logger.warning(f"Error checking existing pool IDs: {e}")
        
        return existing_ids
    
    async def get_lock_contention_metrics(self) -> Dict[str, Any]:
        """Get metrics about database lock contention."""
        metrics = {}
        
        try:
            with self.optimized_session(read_only=True) as session:
                # Check WAL mode status
                wal_result = session.execute(text("PRAGMA journal_mode")).fetchone()
                metrics['journal_mode'] = wal_result[0] if wal_result else 'unknown'
                
                # Check busy timeout
                timeout_result = session.execute(text("PRAGMA busy_timeout")).fetchone()
                metrics['busy_timeout_ms'] = timeout_result[0] if timeout_result else 0
                
                # Check cache size
                cache_result = session.execute(text("PRAGMA cache_size")).fetchone()
                metrics['cache_size'] = cache_result[0] if cache_result else 0
                
                # Simple performance test
                start_time = time.time()
                session.execute(text("SELECT COUNT(*) FROM pools")).fetchone()
                metrics['query_latency_ms'] = (time.time() - start_time) * 1000
                
        except Exception as e:
            logger.warning(f"Error collecting lock contention metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics