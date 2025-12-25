"""
Database-based address resolver for enhanced watchlist data.

This module provides address resolution using existing database tables
(pools, tokens, new_pools_history) to avoid API calls and handle
corrupted lowercase addresses.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseAddressResolver:
    """
    Resolve pool and token addresses using existing database tables.
    
    This resolver uses the pools, tokens, and new_pools_history tables
    to perform reverse lookups without requiring API calls.
    """
    
    def __init__(self, db_manager):
        """
        Initialize the database address resolver.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self._address_cache = {}  # Cache for resolved addresses
        self._lowercase_lookup = {}  # Lowercase to proper case mapping
    
    async def build_address_lookup_cache(self) -> Dict[str, int]:
        """
        Build a lookup cache from existing database tables.
        
        Creates mappings from lowercase addresses to their proper case versions
        using data from pools, tokens, and new_pools_history tables.
        
        Returns:
            Dictionary with cache statistics
        """
        logger.info("Building address lookup cache from database...")
        
        stats = {
            'pools_processed': 0,
            'tokens_processed': 0,
            'history_processed': 0,
            'total_mappings': 0
        }
        
        try:
            with self.db_manager.connection.get_session() as session:
                # 1. Process pools table
                pools = session.query(self.db_manager.PoolModel).all()
                for pool in pools:
                    if pool.address:
                        lowercase_addr = pool.address.lower()
                        self._lowercase_lookup[lowercase_addr] = {
                            'address': pool.address,
                            'pool_id': pool.id,
                            'base_token_id': pool.base_token_id,
                            'quote_token_id': pool.quote_token_id,
                            'dex_id': pool.dex_id,
                            'source': 'pools'
                        }
                        stats['pools_processed'] += 1
                
                # 2. Process tokens table
                tokens = session.query(self.db_manager.TokenModel).all()
                for token in tokens:
                    if token.address:
                        lowercase_addr = token.address.lower()
                        if lowercase_addr not in self._lowercase_lookup:
                            self._lowercase_lookup[lowercase_addr] = {
                                'address': token.address,
                                'token_id': token.id,
                                'symbol': token.symbol,
                                'name': token.name,
                                'source': 'tokens'
                            }
                        stats['tokens_processed'] += 1
                
                # 3. Process new_pools_history table
                history_records = session.query(self.db_manager.NewPoolsHistoryModel).all()
                for record in history_records:
                    if record.address:
                        lowercase_addr = record.address.lower()
                        if lowercase_addr not in self._lowercase_lookup:
                            self._lowercase_lookup[lowercase_addr] = {
                                'address': record.address,
                                'pool_id': record.pool_id,
                                'base_token_id': record.base_token_id,
                                'quote_token_id': record.quote_token_id,
                                'dex_id': record.dex_id,
                                'source': 'new_pools_history'
                            }
                        stats['history_processed'] += 1
                
                stats['total_mappings'] = len(self._lowercase_lookup)
                
                logger.info(f"Address lookup cache built: {stats['total_mappings']} mappings from "
                           f"{stats['pools_processed']} pools, {stats['tokens_processed']} tokens, "
                           f"{stats['history_processed']} history records")
                
                return stats
                
        except Exception as e:
            logger.error(f"Error building address lookup cache: {e}")
            return stats
    
    def resolve_pool_address(self, lowercase_address: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a lowercase pool address to its proper case and related data.
        
        Args:
            lowercase_address: Lowercase pool address to resolve
            
        Returns:
            Dictionary with resolved address data or None if not found
        """
        if not lowercase_address:
            return None
        
        # Check cache first
        lookup_key = lowercase_address.lower()
        if lookup_key in self._lowercase_lookup:
            resolved = self._lowercase_lookup[lookup_key]
            logger.debug(f"Resolved address from {resolved['source']}: {lowercase_address} → {resolved['address']}")
            return resolved
        
        # Not found in cache
        logger.warning(f"Address not found in database cache: {lowercase_address}")
        return None
    
    def get_pool_data_by_lowercase_address(self, lowercase_address: str) -> Optional[Dict[str, Any]]:
        """
        Get complete pool data for a lowercase address.
        
        Args:
            lowercase_address: Lowercase pool address
            
        Returns:
            Dictionary with pool data including token addresses
        """
        resolved = self.resolve_pool_address(lowercase_address)
        
        if not resolved:
            return None
        
        # Get token addresses by looking up token IDs in the database
        base_token_address = None
        quote_token_address = None
        
        if resolved.get('base_token_id') and resolved.get('quote_token_id'):
            try:
                with self.db_manager.connection.get_session() as session:
                    # Look up base token
                    if resolved['base_token_id']:
                        base_token = session.query(self.db_manager.TokenModel).filter_by(
                            id=resolved['base_token_id']
                        ).first()
                        if base_token:
                            base_token_address = base_token.address
                    
                    # Look up quote token
                    if resolved['quote_token_id']:
                        quote_token = session.query(self.db_manager.TokenModel).filter_by(
                            id=resolved['quote_token_id']
                        ).first()
                        if quote_token:
                            quote_token_address = quote_token.address
                            
            except Exception as e:
                logger.warning(f"Error looking up token addresses: {e}")
        
        # Build pool data structure similar to API response
        pool_data = {
            'pool_address': resolved['address'],
            'pool_id': resolved.get('pool_id'),
            'base_token_address': base_token_address,
            'quote_token_address': quote_token_address,
            'dex_id': resolved.get('dex_id'),
            'source': resolved['source']
        }
        
        return pool_data
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get statistics about the address cache."""
        return {
            'total_mappings': len(self._lowercase_lookup),
            'sources': {
                'pools': len([v for v in self._lowercase_lookup.values() if v['source'] == 'pools']),
                'tokens': len([v for v in self._lowercase_lookup.values() if v['source'] == 'tokens']),
                'new_pools_history': len([v for v in self._lowercase_lookup.values() if v['source'] == 'new_pools_history'])
            }
        }
    
    def search_similar_addresses(self, corrupted_address: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for addresses similar to a corrupted one.
        
        This can help identify potential matches for manual correction.
        
        Args:
            corrupted_address: The corrupted address to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of similar addresses with similarity scores
        """
        if not corrupted_address or len(corrupted_address) < 10:
            return []
        
        similar_addresses = []
        search_prefix = corrupted_address[:10].lower()  # Use first 10 characters
        
        for lowercase_addr, data in self._lowercase_lookup.items():
            if lowercase_addr.startswith(search_prefix):
                # Calculate simple similarity score
                similarity = self._calculate_similarity(corrupted_address.lower(), lowercase_addr)
                
                similar_addresses.append({
                    'address': data['address'],
                    'lowercase': lowercase_addr,
                    'similarity': similarity,
                    'source': data['source'],
                    'pool_id': data.get('pool_id'),
                    'dex_id': data.get('dex_id')
                })
        
        # Sort by similarity and return top results
        similar_addresses.sort(key=lambda x: x['similarity'], reverse=True)
        return similar_addresses[:max_results]
    
    def _calculate_similarity(self, addr1: str, addr2: str) -> float:
        """Calculate simple similarity score between two addresses."""
        if not addr1 or not addr2:
            return 0.0
        
        # Simple character-by-character comparison
        matches = sum(1 for a, b in zip(addr1, addr2) if a == b)
        max_length = max(len(addr1), len(addr2))
        
        return matches / max_length if max_length > 0 else 0.0


class EnhancedWatchlistDatabaseParser:
    """
    Enhanced watchlist parser using database lookups instead of API calls.
    
    This parser uses the DatabaseAddressResolver to resolve addresses
    from existing database tables, eliminating the need for API calls.
    """
    
    def __init__(self, db_manager):
        """
        Initialize parser with database manager.
        
        Args:
            db_manager: Database manager for address resolution
        """
        self.db_manager = db_manager
        self.address_resolver = DatabaseAddressResolver(db_manager)
        self._cache_built = False
    
    async def initialize(self) -> Dict[str, int]:
        """
        Initialize the parser by building the address lookup cache.
        
        Returns:
            Cache build statistics
        """
        if not self._cache_built:
            stats = await self.address_resolver.build_address_lookup_cache()
            self._cache_built = True
            logger.info(f"Database address resolver initialized with {stats['total_mappings']} mappings")
            return stats
        return await self.address_resolver.get_cache_statistics()
    
    async def parse_watchlist_entry(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single row from enhanced watchlist data using database lookups.
        
        Args:
            row: Dictionary containing watchlist row data
            
        Returns:
            Parsed and enriched watchlist entry or None if invalid
        """
        try:
            # Ensure cache is built
            if not self._cache_built:
                await self.initialize()
            
            # Extract pool address from detail URL
            detail_url = row.get('detailUrl', '')
            lowercase_address = self._extract_address_from_url(detail_url)
            
            if not lowercase_address:
                logger.error(f"Could not extract address from URL: {detail_url}")
                return None
            
            # Resolve address using database lookup
            pool_data = self.address_resolver.get_pool_data_by_lowercase_address(lowercase_address)
            
            if not pool_data:
                logger.warning(f"Address not found in database: {lowercase_address}")
                
                # Try to find similar addresses for debugging
                similar = self.address_resolver.search_similar_addresses(lowercase_address, 3)
                if similar:
                    logger.info(f"Similar addresses found for {lowercase_address}:")
                    for sim in similar:
                        logger.info(f"  {sim['address']} (similarity: {sim['similarity']:.2f})")
                
                return None
            
            # Build enhanced watchlist entry
            entry = {
                # Original data from CSV
                'timestamp': row.get('timestamp'),
                'ranking': int(row.get('ranking', 0)),
                'tokenSymbol': row.get('tokenSymbol'),
                'tokenName': row.get('tokenName'),
                'chain': row.get('chain'),
                'dex': row.get('dex'),
                'price': float(row.get('price', 0)) if row.get('price') else 0.0,
                'age': row.get('age'),
                'transactions': int(row.get('transactions', 0)) if row.get('transactions') else 0,
                'volume': float(row.get('volume', 0)) if row.get('volume') else 0.0,
                'makers': int(row.get('makers', 0)) if row.get('makers') else 0,
                'priceChange5m': float(row.get('priceChange5m', 0)) if row.get('priceChange5m') else 0.0,
                'priceChange1h': float(row.get('priceChange1h', 0)) if row.get('priceChange1h') else 0.0,
                'priceChange6h': float(row.get('priceChange6h', 0)) if row.get('priceChange6h') else 0.0,
                'priceChange24h': float(row.get('priceChange24h', 0)) if row.get('priceChange24h') else 0.0,
                'liquidity': float(row.get('liquidity', 0)) if row.get('liquidity') else 0.0,
                'marketCap': float(row.get('marketCap', 0)) if row.get('marketCap') else 0.0,
                
                # Resolved addresses from database
                'poolAddress': pool_data['pool_address'],
                'baseTokenAddress': pool_data['base_token_address'],
                'quoteTokenAddress': pool_data['quote_token_address'],
                'networkAddress': pool_data['base_token_address'],
                
                # Metadata
                'source': 'enhanced_watchlist_db',
                'detailUrl': detail_url,
                'resolvedFrom': pool_data['source']  # Which table provided the data
            }
            
            logger.info(f"Resolved entry for {entry['tokenSymbol']}: {lowercase_address} → {pool_data['pool_address']} (from {pool_data['source']})")
            return entry
            
        except Exception as e:
            logger.error(f"Error parsing watchlist entry: {e}")
            return None
    
    def _extract_address_from_url(self, detail_url: str) -> Optional[str]:
        """
        Extract lowercase address from detail URL.
        
        Args:
            detail_url: URL like "/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o"
            
        Returns:
            Extracted lowercase address (no case correction needed)
        """
        if not detail_url:
            return None
        
        import re
        
        # Extract address from URL pattern
        match = re.match(r'^/([^/]+)/([a-zA-Z0-9]+)$', detail_url.strip())
        if not match:
            logger.warning(f"Invalid detail URL format: {detail_url}")
            return None
        
        network, address = match.groups()
        
        # Only process Solana addresses
        if network.lower() != 'solana':
            logger.debug(f"Skipping non-Solana network: {network}")
            return None
        
        # Return lowercase address as-is (we'll resolve it via database)
        return address.lower()
    
    async def get_resolution_statistics(self) -> Dict[str, Any]:
        """Get statistics about address resolution."""
        cache_stats = await self.address_resolver.get_cache_statistics()
        
        return {
            'cache_built': self._cache_built,
            'total_mappings': cache_stats['total_mappings'],
            'source_breakdown': cache_stats['sources'],
            'cache_size_mb': len(str(self.address_resolver._lowercase_lookup)) / (1024 * 1024)
        }


# Example usage and testing
async def test_database_address_resolver(db_manager):
    """Test the database address resolver."""
    
    resolver = EnhancedWatchlistDatabaseParser(db_manager)
    
    # Initialize the resolver
    stats = await resolver.initialize()
    print(f"Resolver initialized: {stats}")
    
    # Test with sample data
    test_entries = [
        {
            'tokenSymbol': 'DINO',
            'tokenName': 'DINOSOL',
            'detailUrl': '/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o',
            'dex': 'pumpswap',
            'price': '0.001066'
        },
        {
            'tokenSymbol': 'SANTA',
            'tokenName': 'SANTA',
            'detailUrl': '/solana/ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9',
            'dex': 'raydium',
            'price': '0.006221'
        }
    ]
    
    for entry in test_entries:
        result = await resolver.parse_watchlist_entry(entry)
        if result:
            print(f"✅ Resolved {entry['tokenSymbol']}: {result['poolAddress']}")
        else:
            print(f"❌ Could not resolve {entry['tokenSymbol']}")
    
    # Get resolution statistics
    resolution_stats = await resolver.get_resolution_statistics()
    print(f"Resolution statistics: {resolution_stats}")