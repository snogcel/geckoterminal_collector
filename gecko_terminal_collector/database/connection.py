"""
Database connection management with connection pooling.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.models import Base

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Database connection manager with connection pooling support.
    
    Supports both synchronous and asynchronous database operations
    with proper connection pooling and resource management.
    """
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database connection manager.
        
        Args:
            config: Database configuration settings
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self.async_engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.async_session_factory: Optional[async_sessionmaker] = None
        self._is_initialized = False
    
    def initialize(self) -> None:
        """Initialize database engines and session factories."""
        if self._is_initialized:
            return
        
        # Create synchronous engine
        self.engine = self._create_sync_engine()
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False
        )
        
        # Create asynchronous engine if async URL is provided
        if self.config.async_url:
            self.async_engine = self._create_async_engine()
            self.async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        
        self._is_initialized = True
        logger.info("Database connection initialized")
    
    def _create_sync_engine(self) -> Engine:
        """Create synchronous SQLAlchemy engine with connection pooling."""
        engine_kwargs = {
            "echo": self.config.echo,
            "future": True,
        }
        
        # Configure connection pooling
        if self.config.url.startswith("sqlite"):
            # SQLite-specific configuration optimized for concurrency
            engine_kwargs.update({
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30,
                    # Additional SQLite optimizations
                    "isolation_level": None,  # Enable autocommit mode
                },
                # Limit connections for SQLite to reduce lock contention
                "pool_size": 1,
                "max_overflow": 0,
            })
        else:
            # PostgreSQL/MySQL configuration
            engine_kwargs.update({
                "poolclass": QueuePool,
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,  # Recycle connections every hour
            })
        
        engine = create_engine(self.config.url, **engine_kwargs)
        
        # Add connection event listeners
        self._add_connection_listeners(engine)
        
        return engine
    
    def _create_async_engine(self) -> Engine:
        """Create asynchronous SQLAlchemy engine with connection pooling."""
        engine_kwargs = {
            "echo": self.config.echo,
            "future": True,
        }
        
        # Configure connection pooling for async engine
        if not self.config.async_url.startswith("sqlite"):
            engine_kwargs.update({
                "poolclass": QueuePool,
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            })
        
        return create_async_engine(self.config.async_url, **engine_kwargs)
    
    def _add_connection_listeners(self, engine: Engine) -> None:
        """Add connection event listeners for monitoring and optimization."""
        
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for better performance and reliability."""
            if engine.url.drivername == "sqlite":
                cursor = dbapi_connection.cursor()
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys=ON")
                # Set synchronous mode for better performance
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Set cache size (negative value = KB)
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                cursor.close()
        
        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkout for monitoring."""
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkin for monitoring."""
            logger.debug("Connection returned to pool")
    
    def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")
    
    async def create_tables_async(self) -> None:
        """Create all database tables asynchronously."""
        if not self.async_engine:
            raise RuntimeError("Async database not initialized")
        
        logger.info("Creating database tables (async)")
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully (async)")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        return self.session_factory()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a new async database session as context manager."""
        if not self.async_session_factory:
            raise RuntimeError("Async database not initialized")
        
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            logger.info("Synchronous database engine disposed")
        
        if self.async_engine:
            # Note: async engine disposal should be done in async context
            logger.info("Async database engine marked for disposal")
        
        self._is_initialized = False
    
    async def close_async(self) -> None:
        """Close async database connections and cleanup resources."""
        if self.async_engine:
            await self.async_engine.dispose()
            logger.info("Async database engine disposed")
    
    def health_check(self) -> bool:
        """
        Perform a health check on the database connection.
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            from sqlalchemy import text
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def health_check_async(self) -> bool:
        """
        Perform an async health check on the database connection.
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            from sqlalchemy import text
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Async database health check failed: {e}")
            return False