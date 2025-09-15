"""
Enhanced SQLAlchemy database manager with improved concurrency handling and retry logic.
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any
from decimal import Decimal
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import sessionmaker

from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Pool as PoolModel

logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is in OPEN state."""
    pass


class DatabaseCircuitBreaker:
    """Circuit breaker pattern for database operations."""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
            else:
                raise CircuitBreakerError("Database circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful operation."""
        if self.failure_count > 0:
            logger.info(f"Circuit breaker recovered after {self.failure_count} failures")
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self, error):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(f"Circuit breaker failure {self.failure_count}/{self.failure_threshold}: {error}")
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")


class EnhancedSQLAlchemyDatabaseManager(SQLAlchemyDatabaseManager):
    """
    Enhanced database manager with improved concurrency handling, retry logic, and circuit breaker.
    """
    
    def __init__(self, config):
        """Initialize enhanced database manager."""
        super().__init__(config)
        
        # Initialize circuit breaker
        self.circuit_breaker = DatabaseCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60
        )
        
        # Retry configuration
        self.max_retries = 3
        self.base_retry_delay = 0.5  # seconds
        
        # Enable WAL mode for better concurrency
        self._enable_wal_mode()
        
    def _enable_wal_mode(self):
        """Enable WAL mode for SQLite to improve concurrency."""
        try:
            if "sqlite" in str(self.engine.url):
                with self.engine.connect() as conn:
                    conn.execute(text("PRAGMA journal_mode=WAL"))
                    conn.execute(text("PRAGMA synchronous=NORMAL"))
                    conn.execute(text("PRAGMA cache_size=10000"))
                    conn.execute(text("PRAGMA temp_store=memory"))
                    conn.commit()
                logger.info("Enabled SQLite WAL mode for improved concurrency")
        except Exception as e:
            logger.warning(f"Failed to enable WAL mode: {e}")
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except OperationalError as e:
                last_exception = e
                
                # Check if it's a database lock error
                if "database is locked" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = self.base_retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Database locked, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                
                # Re-raise if not a lock error or max retries exceeded
                raise
            except Exception as e:
                # Don't retry non-database errors
                raise
        
        # If we get here, all retries failed
        raise last_exception
    
    @asynccontextmanager
    async def get_session_with_retry(self):
        """Get database session with retry logic and proper error handling."""
        session = None
        try:
            session = self.connection.get_session()
            yield session
        except Exception as e:
            if session:
                session.rollback()
            raise
        finally:
            if session:
                session.close()
    
    async def store_pools_enhanced(self, pool_records: List[PoolModel]) -> int:
        """
        Enhanced pool storage with retry logic, circuit breaker, and optimized session management.
        
        Args:
            pool_records: List of pool model instances to store
            
        Returns:
            Number of pools successfully stored
        """
        return await self.circuit_breaker.call(self._store_pools_with_retry, pool_records)
    
    async def _store_pools_with_retry(self, pool_records: List[PoolModel]) -> int:
        """Internal method to store pools with retry logic."""
        return await self._retry_with_backoff(self._store_pools_optimized, pool_records)
    
    async def _store_pools_optimized(self, pool_records: List[PoolModel]) -> int:
        """
        Optimized pool storage with proper session management and batch operations.
        """
        if not pool_records:
            return 0
        
        stored_count = 0
        
        async with self.get_session_with_retry() as session:
            try:
                # Disable autoflush for read operations to prevent premature commits
                with session.no_autoflush:
                    # Get existing pool IDs in batch
                    pool_ids = [pool.id for pool in pool_records]
                    existing_pools = session.query(PoolModel.id).filter(
                        PoolModel.id.in_(pool_ids)
                    ).all()
                    existing_ids = {pool.id for pool in existing_pools}
                
                # Separate new pools from updates
                new_pools = []
                update_pools = []
                
                for pool in pool_records:
                    if pool.id in existing_ids:
                        update_pools.append(pool)
                    else:
                        new_pools.append(pool)
                
                # Batch insert new pools
                if new_pools:
                    try:
                        session.bulk_insert_mappings(
                            PoolModel,
                            [self._pool_to_dict(pool) for pool in new_pools]
                        )
                        stored_count += len(new_pools)
                        logger.debug(f"Bulk inserted {len(new_pools)} new pools")
                    except IntegrityError as e:
                        # Handle race conditions where pools were created between check and insert
                        logger.warning(f"Integrity error during bulk insert, falling back to individual inserts: {e}")
                        session.rollback()
                        
                        # Fall back to individual inserts for new pools
                        for pool in new_pools:
                            try:
                                session.merge(pool)
                                stored_count += 1
                            except IntegrityError:
                                # Pool was created by another process, skip
                                logger.debug(f"Pool {pool.id} already exists, skipping")
                
                # Batch update existing pools
                if update_pools:
                    session.bulk_update_mappings(
                        PoolModel,
                        [self._pool_to_dict(pool) for pool in update_pools]
                    )
                    stored_count += len(update_pools)
                    logger.debug(f"Bulk updated {len(update_pools)} existing pools")
                
                # Commit all changes
                session.commit()
                
                logger.info(f"Successfully stored {stored_count} pools ({len(new_pools)} new, {len(update_pools)} updated)")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error in optimized pool storage: {e}")
                raise
        
        return stored_count
    
    def _pool_to_dict(self, pool: PoolModel) -> Dict[str, Any]:
        """Convert pool model to dictionary for bulk operations."""
        return {
            'id': pool.id,
            'address': pool.address,
            'name': pool.name,
            'dex_id': pool.dex_id,
            'base_token_id': pool.base_token_id,
            'quote_token_id': pool.quote_token_id,
            'reserve_usd': pool.reserve_usd,
            'created_at': pool.created_at,
            'last_updated': pool.last_updated,
            'activity_score': pool.activity_score,
            'discovery_source': pool.discovery_source,
            'collection_priority': pool.collection_priority,
            'auto_discovered_at': pool.auto_discovered_at,
            'last_activity_check': pool.last_activity_check
        }
    
    async def get_database_health_metrics(self) -> Dict[str, Any]:
        """Get comprehensive database health metrics."""
        metrics = {
            'circuit_breaker_state': self.circuit_breaker.state,
            'circuit_breaker_failures': self.circuit_breaker.failure_count,
            'connection_pool_size': 0,
            'active_connections': 0,
            'wal_mode_enabled': False,
            'lock_wait_time_ms': 0
        }
        
        try:
            # Check WAL mode
            async with self.get_session_with_retry() as session:
                result = session.execute(text("PRAGMA journal_mode")).fetchone()
                if result and result[0].upper() == 'WAL':
                    metrics['wal_mode_enabled'] = True
                
                # Measure simple query performance
                start_time = time.time()
                session.execute(text("SELECT 1")).fetchone()
                metrics['lock_wait_time_ms'] = (time.time() - start_time) * 1000
                
        except Exception as e:
            logger.warning(f"Error collecting database health metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    async def test_database_connectivity(self) -> bool:
        """Test database connectivity with circuit breaker protection."""
        try:
            return await self.circuit_breaker.call(self._test_connectivity_internal)
        except CircuitBreakerError:
            logger.error("Database connectivity test failed: Circuit breaker is OPEN")
            return False
        except Exception as e:
            logger.error(f"Database connectivity test failed: {e}")
            return False
    
    async def _test_connectivity_internal(self) -> bool:
        """Internal connectivity test."""
        async with self.get_session_with_retry() as session:
            session.execute(text("SELECT 1")).fetchone()
            return True
    
    # Override the original store_pools method to use enhanced version
    async def store_pools(self, pool_records: List[PoolModel]) -> int:
        """Store pools using enhanced method with retry logic and circuit breaker."""
        return await self.store_pools_enhanced(pool_records)