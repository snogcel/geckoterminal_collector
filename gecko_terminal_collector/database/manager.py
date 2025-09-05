"""
Database manager and data access layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from gecko_terminal_collector.models.core import (
    Pool, Token, OHLCVRecord, TradeRecord, Gap, ContinuityReport
)
from gecko_terminal_collector.config.models import DatabaseConfig


class DatabaseManager(ABC):
    """
    Abstract database manager interface.
    
    Defines the contract for database operations across different
    storage backends (SQLite, PostgreSQL, etc.).
    """
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database manager with configuration.
        
        Args:
            config: Database configuration settings
        """
        self.config = config
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and schema."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        pass
    
    # Pool operations
    @abstractmethod
    async def store_pools(self, pools: List[Pool]) -> int:
        """
        Store pool data with upsert logic.
        
        Args:
            pools: List of pool records to store
            
        Returns:
            Number of records stored/updated
        """
        pass
    
    @abstractmethod
    async def get_pool(self, pool_id: str) -> Optional[Pool]:
        """Get a pool by ID."""
        pass
    
    @abstractmethod
    async def get_pools_by_dex(self, dex_id: str) -> List[Pool]:
        """Get all pools for a specific DEX."""
        pass
    
    # Token operations
    @abstractmethod
    async def store_tokens(self, tokens: List[Token]) -> int:
        """Store token data with upsert logic."""
        pass
    
    @abstractmethod
    async def get_token(self, pool_id: str, token_id: str) -> Optional[Token]:
        """Get a token by ID."""        
        pass
    
    # OHLCV operations
    @abstractmethod
    async def store_ohlcv_data(self, data: List[OHLCVRecord]) -> int:
        """
        Store OHLCV data with duplicate prevention.
        
        Args:
            data: List of OHLCV records to store
            
        Returns:
            Number of new records stored (excluding duplicates)
        """
        pass
    
    @abstractmethod
    async def get_ohlcv_data(
        self, 
        pool_id: str, 
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[OHLCVRecord]:
        """Get OHLCV data for a pool and timeframe."""
        pass
    
    @abstractmethod
    async def get_data_gaps(
        self, 
        pool_id: str, 
        timeframe: str,
        start: datetime, 
        end: datetime
    ) -> List[Gap]:
        """
        Identify gaps in OHLCV data for a pool/timeframe.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe (e.g., '1h', '1d')
            start: Start of time range to check
            end: End of time range to check
            
        Returns:
            List of identified gaps
        """
        pass
    
    # Trade operations
    @abstractmethod
    async def store_trade_data(self, data: List[TradeRecord]) -> int:
        """Store trade data with duplicate prevention."""
        pass
    
    @abstractmethod
    async def get_trade_data(
        self,
        pool_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_volume_usd: Optional[float] = None
    ) -> List[TradeRecord]:
        """Get trade data for a pool with optional filtering."""
        pass
    
    # Watchlist operations
    @abstractmethod
    async def store_watchlist_entry(self, pool_id: str, metadata: Dict[str, Any]) -> None:
        """Add or update a watchlist entry."""
        pass
    
    @abstractmethod
    async def add_watchlist_entry(self, entry: Any) -> None:
        """Add a new watchlist entry."""
        pass
    
    @abstractmethod
    async def get_watchlist_entry_by_pool_id(self, pool_id: str) -> Optional[Any]:
        """Get a watchlist entry by pool ID."""        
        pass
    
    @abstractmethod
    async def update_watchlist_entry_status(self, pool_id: str, is_active: bool) -> None:
        """Update the active status of a watchlist entry."""
        pass

    @abstractmethod
    async def update_watchlist_entry(self, entry: Any) -> None:
        """Update an existing watchlist entry."""
        pass

    @abstractmethod
    async def get_watchlist_pools(self) -> List[str]:
        """Get all active watchlist pool IDs."""
        pass
    
    @abstractmethod
    async def remove_watchlist_entry(self, pool_id: str) -> None:
        """Remove a pool from the watchlist."""
        pass
    
    # DEX operations
    @abstractmethod
    async def store_dex_data(self, dexes: List[Any]) -> int:
        """
        Store DEX data with upsert logic.
        
        Args:
            dexes: List of DEX records to store
            
        Returns:
            Number of records stored/updated
        """
        pass
    
    @abstractmethod
    async def get_dex_by_id(self, dex_id: str) -> Optional[Any]:
        """Get a DEX by ID."""
        pass
    
    @abstractmethod
    async def get_dexes_by_network(self, network: str) -> List[Any]:
        """Get all DEXes for a specific network."""
        pass

    # Collection metadata operations
    @abstractmethod
    async def update_collection_metadata(
        self,
        collector_type: str,
        last_run: datetime,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """Update collection run metadata."""
        pass
    
    @abstractmethod
    async def get_collection_metadata(self, collector_type: str) -> Optional[Dict[str, Any]]:
        """Get collection metadata for a collector type."""
        pass
    
    # Data quality and continuity
    async def check_data_continuity(
        self, 
        pool_id: str, 
        timeframe: str
    ) -> ContinuityReport:
        """
        Check data continuity for a pool/timeframe combination.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            Continuity report with gaps and quality metrics
        """
        # Default implementation - can be overridden
        now = datetime.utcnow()
        start_time = datetime(now.year, now.month, 1)  # Start of current month
        
        gaps = await self.get_data_gaps(pool_id, timeframe, start_time, now)
        
        # Calculate data quality score (simple metric)
        total_expected_intervals = self._calculate_expected_intervals(
            start_time, now, timeframe
        )
        gap_intervals = sum(
            self._calculate_expected_intervals(gap.start_time, gap.end_time, timeframe)
            for gap in gaps
        )
        
        quality_score = max(0.0, 1.0 - (gap_intervals / total_expected_intervals))
        
        return ContinuityReport(
            pool_id=pool_id,
            timeframe=timeframe,
            total_gaps=len(gaps),
            gaps=gaps,
            data_quality_score=quality_score
        )
    
    # Enhanced data integrity methods
    @abstractmethod
    async def check_data_integrity(self, pool_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive data integrity checks for a pool.
        
        Args:
            pool_id: Pool identifier
            
        Returns:
            Dictionary containing integrity check results
        """
        pass
    
    @abstractmethod
    async def get_data_statistics(self, pool_id: str) -> Dict[str, Any]:
        """
        Get comprehensive data statistics for a pool.
        
        Args:
            pool_id: Pool identifier
            
        Returns:
            Dictionary containing data statistics
        """
        pass
    
    @abstractmethod
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old data beyond the retention period.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Dictionary with cleanup statistics
        """
        pass

    @abstractmethod
    async def get_table_names(self) -> List[Any]:
        """Get list of existing table names in the database."""
        pass

    @abstractmethod
    async def count_records(self, table_name: str) -> int:
        """Count records in a specific table."""
        pass

    def _calculate_expected_intervals(
        self, 
        start: datetime, 
        end: datetime, 
        timeframe: str
    ) -> int:
        """Calculate expected number of intervals between two timestamps."""
        # Simplified calculation - would need proper implementation
        # based on timeframe parsing
        delta = end - start
        
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            return int(delta.total_seconds() / (minutes * 60))
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            return int(delta.total_seconds() / (hours * 3600))
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            return int(delta.days / days)
        
        return 0