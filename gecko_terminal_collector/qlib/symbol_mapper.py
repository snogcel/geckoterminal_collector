"""
Symbol mapping utilities for QLib integration with case-insensitive lookup support.

This module provides robust symbol-to-pool mapping that preserves cryptocurrency
address case while enabling case-insensitive lookups for external system compatibility.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from gecko_terminal_collector.models.core import Pool
from gecko_terminal_collector.database.manager import DatabaseManager


logger = logging.getLogger(__name__)


@dataclass
class PoolLookupResult:
    """Result of a pool lookup operation with metadata."""
    pool: Optional[Pool]
    matched_symbol: str
    lookup_method: str  # "exact", "case_insensitive", "database"
    confidence: float


@dataclass
class SymbolMetadata:
    """Metadata for symbol tracking."""
    original_symbol: str
    normalized_symbol: str
    pool_id: str
    case_sensitive: bool = True
    created_at: datetime = None
    last_accessed: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.last_accessed is None:
            self.last_accessed = datetime.utcnow()


class SymbolMapper:
    """
    Provides robust symbol-to-pool mapping with case-insensitive lookup capabilities.
    
    This class implements a dual caching strategy:
    1. Case-sensitive cache for exact symbol matches
    2. Normalized (lowercase) cache for case-insensitive lookups
    
    The mapper preserves original case in symbol generation while providing
    fallback lookup capabilities for external systems that normalize case.
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize the symbol mapper.
        
        Args:
            db_manager: Optional database manager for fallback lookups
        """
        self.db_manager = db_manager
        
        # Case-sensitive symbol -> Pool mapping
        self._symbol_to_pool_cache: Dict[str, Pool] = {}
        
        # Normalized (lowercase) symbol -> original symbol mapping
        self._normalized_to_symbol_cache: Dict[str, str] = {}
        
        # Symbol metadata tracking
        self._symbol_metadata: Dict[str, SymbolMetadata] = {}
        
        logger.debug("SymbolMapper initialized")
    
    def generate_symbol(self, pool: Pool) -> str:
        """
        Generate QLib-compatible symbol name from pool information.
        
        This method preserves the original case from the pool ID to maintain
        exact mapping capabilities while ensuring the symbol is valid for QLib.
        
        Args:
            pool: Pool object to generate symbol for
            
        Returns:
            Case-preserving symbol name string
            
        Requirements: 1.1, 1.4, 2.1
        """
        if not pool or not pool.id:
            raise ValueError("Pool and pool.id are required")
        
        # Use the full pool ID as the symbol to ensure uniqueness and reversibility
        # Keep original case to maintain exact mapping (Requirement 1.1)
        symbol = pool.id
        
        # Ensure valid symbol format (alphanumeric + underscore)
        # Replace invalid characters with underscores
        symbol = ''.join(c if c.isalnum() or c == '_' else '_' for c in symbol)
        
        # Remove duplicate underscores
        while '__' in symbol:
            symbol = symbol.replace('__', '_')
        
        # Remove leading/trailing underscores
        symbol = symbol.strip('_')
        
        # Cache the symbol mapping
        self._add_to_cache(symbol, pool)
        
        logger.debug(f"Generated symbol '{symbol}' for pool {pool.id}")
        return symbol
    
    def lookup_pool(self, symbol: str) -> Optional[Pool]:
        """
        Look up pool by symbol with case-insensitive fallback.
        
        This method implements a three-tier lookup strategy:
        1. Exact case match from cache
        2. Case-insensitive match from cache
        3. Database fallback lookup
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            Pool object if found, None otherwise
            
        Requirements: 1.2, 2.1, 2.2
        """
        if not symbol:
            return None
        
        # Update access time for metadata
        self._update_access_time(symbol)
        
        # Try exact match first (Requirement 2.2 - exact match priority)
        if symbol in self._symbol_to_pool_cache:
            logger.debug(f"Found exact match for symbol '{symbol}'")
            return self._symbol_to_pool_cache[symbol]
        
        # Try case-insensitive match (Requirement 2.1)
        normalized = self.normalize_symbol(symbol)
        if normalized in self._normalized_to_symbol_cache:
            original_symbol = self._normalized_to_symbol_cache[normalized]
            pool = self._symbol_to_pool_cache.get(original_symbol)
            if pool:
                logger.debug(f"Found case-insensitive match for symbol '{symbol}' -> '{original_symbol}'")
                return pool
        
        # Fallback to database lookup if available (Requirement 1.2)
        if self.db_manager:
            pool = self._database_lookup(symbol)
            if pool:
                # Add to cache for future lookups
                generated_symbol = self.generate_symbol(pool)
                logger.debug(f"Found database match for symbol '{symbol}' -> pool {pool.id}")
                return pool
        
        logger.debug(f"No match found for symbol '{symbol}'")
        return None
    
    def lookup_pool_detailed(self, symbol: str) -> PoolLookupResult:
        """
        Look up pool with detailed result information.
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            PoolLookupResult with lookup metadata
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
            return PoolLookupResult(
                pool=self._symbol_to_pool_cache[symbol],
                matched_symbol=symbol,
                lookup_method="exact",
                confidence=1.0
            )
        
        # Try case-insensitive match
        normalized = self.normalize_symbol(symbol)
        if normalized in self._normalized_to_symbol_cache:
            original_symbol = self._normalized_to_symbol_cache[normalized]
            pool = self._symbol_to_pool_cache.get(original_symbol)
            if pool:
                return PoolLookupResult(
                    pool=pool,
                    matched_symbol=original_symbol,
                    lookup_method="case_insensitive",
                    confidence=0.9
                )
        
        # Try database lookup
        if self.db_manager:
            pool = self._database_lookup(symbol)
            if pool:
                return PoolLookupResult(
                    pool=pool,
                    matched_symbol=self.generate_symbol(pool),
                    lookup_method="database",
                    confidence=0.8
                )
        
        return PoolLookupResult(
            pool=None,
            matched_symbol=symbol,
            lookup_method="not_found",
            confidence=0.0
        )
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Create normalized (lowercase) version of symbol for case-insensitive lookup.
        
        Args:
            symbol: Original symbol
            
        Returns:
            Normalized lowercase symbol
            
        Requirements: 1.4, 2.1
        """
        if not symbol:
            return ""
        
        # Convert to lowercase for consistent normalization (Requirement 1.4)
        normalized = symbol.lower()
        
        logger.debug(f"Normalized symbol '{symbol}' -> '{normalized}'")
        return normalized
    
    def _add_to_cache(self, symbol: str, pool: Pool) -> None:
        """
        Add symbol-pool mapping to both caches.
        
        Args:
            symbol: Symbol to cache
            pool: Pool object to associate
        """
        # Add to case-sensitive cache
        self._symbol_to_pool_cache[symbol] = pool
        
        # Add to normalized cache
        normalized = self.normalize_symbol(symbol)
        self._normalized_to_symbol_cache[normalized] = symbol
        
        # Add metadata
        self._symbol_metadata[symbol] = SymbolMetadata(
            original_symbol=symbol,
            normalized_symbol=normalized,
            pool_id=pool.id,
            case_sensitive=True
        )
        
        logger.debug(f"Added symbol '{symbol}' to cache for pool {pool.id}")
    
    def _database_lookup(self, symbol: str) -> Optional[Pool]:
        """
        Perform database lookup for symbol when cache misses.
        
        This method attempts to find the pool by treating the symbol
        as a potential pool ID, since our symbol generation is based
        on pool IDs.
        
        Args:
            symbol: Symbol to look up in database
            
        Returns:
            Pool object if found, None otherwise
            
        Requirements: 1.2, 2.2
        """
        if not self.db_manager:
            return None
        
        try:
            # Since our symbol is based on the pool ID, try direct lookup
            # The symbol should match the pool ID (with character normalization)
            pool_id = symbol
            
            # Try to get the pool directly (this is async, but we'll handle it)
            # Note: This is a simplified version - in practice, you'd need to handle async properly
            logger.debug(f"Attempting database lookup for symbol '{symbol}' as pool ID")
            
            # For now, return None as we can't easily make async calls here
            # This would need to be implemented in the async context of the caller
            return None
            
        except Exception as e:
            logger.error(f"Database lookup failed for symbol '{symbol}': {e}")
            return None
    
    def _update_access_time(self, symbol: str) -> None:
        """
        Update last access time for symbol metadata.
        
        Args:
            symbol: Symbol to update access time for
        """
        if symbol in self._symbol_metadata:
            self._symbol_metadata[symbol].last_accessed = datetime.utcnow()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring and debugging.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'case_sensitive_entries': len(self._symbol_to_pool_cache),
            'normalized_entries': len(self._normalized_to_symbol_cache),
            'metadata_entries': len(self._symbol_metadata),
            'cache_consistency': len(self._symbol_to_pool_cache) == len(self._normalized_to_symbol_cache)
        }
    
    def clear_cache(self) -> None:
        """Clear all cached symbol mappings."""
        self._symbol_to_pool_cache.clear()
        self._normalized_to_symbol_cache.clear()
        self._symbol_metadata.clear()
        logger.info("Symbol mapper cache cleared")
    
    def get_symbol_metadata(self, symbol: str) -> Optional[SymbolMetadata]:
        """
        Get metadata for a symbol.
        
        Args:
            symbol: Symbol to get metadata for
            
        Returns:
            SymbolMetadata object if found, None otherwise
        """
        return self._symbol_metadata.get(symbol)
    
    def get_all_symbols(self) -> list[str]:
        """
        Get all cached symbols.
        
        Returns:
            List of all cached symbols
        """
        return list(self._symbol_to_pool_cache.keys())
    
    def get_symbol_variants(self, symbol: str) -> list[str]:
        """
        Get all case variants of a symbol that exist in cache.
        
        Args:
            symbol: Base symbol to find variants for
            
        Returns:
            List of symbol variants found in cache
        """
        variants = []
        normalized = self.normalize_symbol(symbol)
        
        # Find all symbols that normalize to the same value
        for cached_symbol, cached_normalized in [(s, self.normalize_symbol(s)) 
                                               for s in self._symbol_to_pool_cache.keys()]:
            if cached_normalized == normalized:
                variants.append(cached_symbol)
        
        return variants