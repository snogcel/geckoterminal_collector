"""
Integrated Symbol Mapper that works with EnhancedDatabaseManager.

This module provides an enhanced symbol mapper that integrates with the
enhanced database manager for comprehensive symbol mapping with database
fallback and caching capabilities.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

from gecko_terminal_collector.qlib.symbol_mapper import SymbolMapper, PoolLookupResult, SymbolMetadata
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.models.core import Pool


logger = logging.getLogger(__name__)


@dataclass
class IntegratedSymbolMetadata(SymbolMetadata):
    """Extended symbol metadata with database integration info."""
    database_cached: bool = False
    cache_hit_count: int = 0
    last_database_lookup: Optional[datetime] = None


class IntegratedSymbolMapper(SymbolMapper):
    """
    Enhanced symbol mapper that integrates with EnhancedDatabaseManager.
    
    This class extends the base SymbolMapper with:
    - Database fallback for symbol lookups with caching
    - Integration with enhanced database manager
    - Performance tracking and metrics
    - Bulk symbol population from database
    """
    
    def __init__(self, db_manager: EnhancedDatabaseManager):
        """
        Initialize the integrated symbol mapper.
        
        Args:
            db_manager: Enhanced database manager instance
        """
        super().__init__(db_manager)
        self.enhanced_db_manager = db_manager
        
        # Extended metadata tracking
        self._integrated_metadata: Dict[str, IntegratedSymbolMetadata] = {}
        
        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._database_lookups = 0
        
        logger.info("IntegratedSymbolMapper initialized with enhanced database manager")
    
    async def populate_cache_from_database(self, limit: Optional[int] = None) -> int:
        """
        Populate symbol cache from existing database records.
        
        Args:
            limit: Optional limit on number of pools to load
            
        Returns:
            Number of symbols loaded into cache
        """
        try:
            logger.info("Populating symbol cache from database...")
            
            # Get all pools from database
            pools = await self.enhanced_db_manager.get_all_pools(limit=limit)
            
            symbols_loaded = 0
            for pool in pools:
                try:
                    # Generate symbol and add to cache with database_cached=True
                    symbol = super().generate_symbol(pool)
                    self._add_to_cache(symbol, pool, database_cached=True)
                    
                    symbols_loaded += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing pool {pool.id}: {e}")
                    continue
            
            logger.info(f"Loaded {symbols_loaded} symbols into cache from database")
            return symbols_loaded
            
        except Exception as e:
            logger.error(f"Error populating cache from database: {e}")
            return 0
    
    async def lookup_pool_with_fallback(self, symbol: str) -> Optional[Pool]:
        """
        Enhanced lookup with database fallback and caching.
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            Pool object if found, None otherwise
        """
        if not symbol:
            return None
        
        # Update access time
        self._update_access_time(symbol)
        
        # Try cache first (exact match)
        if symbol in self._symbol_to_pool_cache:
            self._cache_hits += 1
            self._update_cache_hit_count(symbol)
            logger.debug(f"Cache hit for symbol '{symbol}'")
            return self._symbol_to_pool_cache[symbol]
        
        # Try case-insensitive cache match
        normalized = self.normalize_symbol(symbol)
        if normalized in self._normalized_to_symbol_cache:
            original_symbol = self._normalized_to_symbol_cache[normalized]
            pool = self._symbol_to_pool_cache.get(original_symbol)
            if pool:
                self._cache_hits += 1
                self._update_cache_hit_count(original_symbol)
                logger.debug(f"Case-insensitive cache hit for symbol '{symbol}' -> '{original_symbol}'")
                return pool
        
        # Database fallback
        self._cache_misses += 1
        pool = await self._enhanced_database_lookup(symbol)
        
        if pool:
            # Add to cache for future lookups
            generated_symbol = self.generate_symbol(pool)
            
            # Update metadata to reflect database lookup
            if generated_symbol in self._integrated_metadata:
                self._integrated_metadata[generated_symbol].last_database_lookup = datetime.utcnow()
            
            logger.debug(f"Database lookup successful for symbol '{symbol}' -> pool {pool.id}")
            return pool
        
        logger.debug(f"No match found for symbol '{symbol}'")
        return None
    
    async def lookup_pool_detailed_enhanced(self, symbol: str) -> PoolLookupResult:
        """
        Enhanced detailed lookup with database integration metrics.
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            PoolLookupResult with enhanced metadata
        """
        if not symbol:
            return PoolLookupResult(
                pool=None,
                matched_symbol=symbol,
                lookup_method="none",
                confidence=0.0
            )
        
        # Try exact match first
        if symbol in self._symbol_to_pool_cache:
            self._cache_hits += 1
            return PoolLookupResult(
                pool=self._symbol_to_pool_cache[symbol],
                matched_symbol=symbol,
                lookup_method="exact_cache",
                confidence=1.0
            )
        
        # Try case-insensitive match
        normalized = self.normalize_symbol(symbol)
        if normalized in self._normalized_to_symbol_cache:
            original_symbol = self._normalized_to_symbol_cache[normalized]
            pool = self._symbol_to_pool_cache.get(original_symbol)
            if pool:
                self._cache_hits += 1
                return PoolLookupResult(
                    pool=pool,
                    matched_symbol=original_symbol,
                    lookup_method="case_insensitive_cache",
                    confidence=0.9
                )
        
        # Try database lookup
        self._cache_misses += 1
        pool = await self._enhanced_database_lookup(symbol)
        if pool:
            return PoolLookupResult(
                pool=pool,
                matched_symbol=self.generate_symbol(pool),
                lookup_method="database_fallback",
                confidence=0.8
            )
        
        return PoolLookupResult(
            pool=None,
            matched_symbol=symbol,
            lookup_method="not_found",
            confidence=0.0
        )
    
    async def _enhanced_database_lookup(self, symbol: str) -> Optional[Pool]:
        """
        Enhanced database lookup with multiple strategies.
        
        Args:
            symbol: Symbol to look up in database
            
        Returns:
            Pool object if found, None otherwise
        """
        self._database_lookups += 1
        
        try:
            # Strategy 1: Direct pool ID lookup (symbol should match pool ID)
            pool = await self.enhanced_db_manager.get_pool(symbol)
            if pool:
                # Add to cache
                generated_symbol = super().generate_symbol(pool)
                self._add_to_cache(generated_symbol, pool, database_cached=True)
                return pool
            
            # Strategy 2: Search by pool address (in case symbol is an address)
            pool = await self.enhanced_db_manager.get_pool_by_address(symbol)
            if pool:
                # Add to cache
                generated_symbol = super().generate_symbol(pool)
                self._add_to_cache(generated_symbol, pool, database_cached=True)
                return pool
            
            # Strategy 3: Fuzzy search through all pools (expensive, use sparingly)
            pools = await self.enhanced_db_manager.search_pools_by_name_or_id(symbol, limit=10)
            for pool in pools:
                generated_symbol = super().generate_symbol(pool)
                if generated_symbol.lower() == symbol.lower():
                    # Add to cache
                    self._add_to_cache(generated_symbol, pool, database_cached=True)
                    return pool
            
            return None
            
        except Exception as e:
            logger.error(f"Enhanced database lookup failed for symbol '{symbol}': {e}")
            return None
    
    def _add_to_cache(self, symbol: str, pool: Pool, database_cached: bool = False) -> None:
        """
        Enhanced cache addition with integrated metadata.
        
        Args:
            symbol: Symbol to cache
            pool: Pool object to associate
            database_cached: Whether this symbol was loaded from database
        """
        # Call parent method
        super()._add_to_cache(symbol, pool)
        
        # Add integrated metadata
        self._integrated_metadata[symbol] = IntegratedSymbolMetadata(
            original_symbol=symbol,
            normalized_symbol=self.normalize_symbol(symbol),
            pool_id=pool.id,
            case_sensitive=True,
            database_cached=database_cached,
            cache_hit_count=0,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow()
        )
        
        logger.debug(f"Added symbol '{symbol}' to integrated cache for pool {pool.id} (database_cached={database_cached})")
    
    def _update_cache_hit_count(self, symbol: str) -> None:
        """
        Update cache hit count for performance tracking.
        
        Args:
            symbol: Symbol to update hit count for
        """
        if symbol in self._integrated_metadata:
            self._integrated_metadata[symbol].cache_hit_count += 1
    
    def _update_access_time(self, symbol: str) -> None:
        """
        Update last access time for symbol metadata.
        
        Args:
            symbol: Symbol to update access time for
        """
        # Call parent method
        super()._update_access_time(symbol)
        
        # Update integrated metadata
        if symbol in self._integrated_metadata:
            self._integrated_metadata[symbol].last_accessed = datetime.utcnow()
    
    async def bulk_populate_symbols(self, pool_ids: List[str]) -> Dict[str, str]:
        """
        Bulk populate symbols for a list of pool IDs.
        
        Args:
            pool_ids: List of pool IDs to generate symbols for
            
        Returns:
            Dictionary mapping pool_id -> symbol
        """
        symbol_mapping = {}
        
        try:
            for pool_id in pool_ids:
                try:
                    pool = await self.enhanced_db_manager.get_pool(pool_id)
                    if pool:
                        symbol = self.generate_symbol(pool)
                        symbol_mapping[pool_id] = symbol
                        
                        # Mark as database cached
                        if symbol in self._integrated_metadata:
                            self._integrated_metadata[symbol].database_cached = True
                        
                except Exception as e:
                    logger.warning(f"Error processing pool {pool_id}: {e}")
                    continue
            
            logger.info(f"Bulk populated {len(symbol_mapping)} symbols")
            return symbol_mapping
            
        except Exception as e:
            logger.error(f"Error in bulk symbol population: {e}")
            return symbol_mapping
    
    async def refresh_symbol_cache(self, max_age_hours: int = 24) -> int:
        """
        Refresh symbol cache by removing old entries and reloading from database.
        
        Args:
            max_age_hours: Maximum age of cache entries in hours
            
        Returns:
            Number of symbols refreshed
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            symbols_to_refresh = []
            
            # Find old symbols
            for symbol, metadata in self._integrated_metadata.items():
                if metadata.last_accessed < cutoff_time:
                    symbols_to_refresh.append(symbol)
            
            # Remove old symbols from cache
            for symbol in symbols_to_refresh:
                if symbol in self._symbol_to_pool_cache:
                    del self._symbol_to_pool_cache[symbol]
                
                normalized = self.normalize_symbol(symbol)
                if normalized in self._normalized_to_symbol_cache:
                    del self._normalized_to_symbol_cache[normalized]
                
                if symbol in self._integrated_metadata:
                    del self._integrated_metadata[symbol]
            
            logger.info(f"Removed {len(symbols_to_refresh)} old symbols from cache")
            
            # Repopulate from database
            refreshed_count = await self.populate_cache_from_database()
            
            return refreshed_count
            
        except Exception as e:
            logger.error(f"Error refreshing symbol cache: {e}")
            return 0
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the integrated symbol mapper.
        
        Returns:
            Dictionary with performance metrics
        """
        total_lookups = self._cache_hits + self._cache_misses
        cache_hit_rate = (self._cache_hits / total_lookups) if total_lookups > 0 else 0.0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'database_lookups': self._database_lookups,
            'cache_hit_rate': cache_hit_rate,
            'total_cached_symbols': len(self._symbol_to_pool_cache),
            'database_cached_symbols': sum(
                1 for metadata in self._integrated_metadata.values() 
                if metadata.database_cached
            ),
            'most_accessed_symbols': self._get_most_accessed_symbols(5)
        }
    
    def _get_most_accessed_symbols(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most frequently accessed symbols.
        
        Args:
            limit: Maximum number of symbols to return
            
        Returns:
            List of symbol access information
        """
        sorted_symbols = sorted(
            self._integrated_metadata.items(),
            key=lambda x: x[1].cache_hit_count,
            reverse=True
        )
        
        return [
            {
                'symbol': symbol,
                'hit_count': metadata.cache_hit_count,
                'last_accessed': metadata.last_accessed.isoformat() if metadata.last_accessed else None
            }
            for symbol, metadata in sorted_symbols[:limit]
        ]
    
    def get_integrated_metadata(self, symbol: str) -> Optional[IntegratedSymbolMetadata]:
        """
        Get integrated metadata for a symbol.
        
        Args:
            symbol: Symbol to get metadata for
            
        Returns:
            IntegratedSymbolMetadata object if found, None otherwise
        """
        return self._integrated_metadata.get(symbol)
    
    def clear_cache(self) -> None:
        """Clear all cached symbol mappings including integrated metadata."""
        super().clear_cache()
        self._integrated_metadata.clear()
        
        # Reset performance counters
        self._cache_hits = 0
        self._cache_misses = 0
        self._database_lookups = 0
        
        logger.info("Integrated symbol mapper cache cleared")
    
    async def validate_cache_consistency(self) -> Dict[str, Any]:
        """
        Validate cache consistency with database.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'is_consistent': True,
            'inconsistencies': [],
            'total_symbols_checked': 0,
            'database_mismatches': 0
        }
        
        try:
            for symbol, pool in self._symbol_to_pool_cache.items():
                validation_results['total_symbols_checked'] += 1
                
                # Check if pool still exists in database
                db_pool = await self.enhanced_db_manager.get_pool(pool.id)
                
                if not db_pool:
                    validation_results['is_consistent'] = False
                    validation_results['database_mismatches'] += 1
                    validation_results['inconsistencies'].append({
                        'symbol': symbol,
                        'issue': 'Pool no longer exists in database',
                        'pool_id': pool.id
                    })
                elif db_pool.id != pool.id:
                    validation_results['is_consistent'] = False
                    validation_results['database_mismatches'] += 1
                    validation_results['inconsistencies'].append({
                        'symbol': symbol,
                        'issue': 'Pool ID mismatch',
                        'cached_pool_id': pool.id,
                        'database_pool_id': db_pool.id
                    })
            
            logger.info(f"Cache validation completed: {validation_results['total_symbols_checked']} symbols checked, "
                       f"{validation_results['database_mismatches']} inconsistencies found")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating cache consistency: {e}")
            validation_results['error'] = str(e)
            return validation_results