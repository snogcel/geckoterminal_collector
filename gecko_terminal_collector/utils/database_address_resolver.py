"""
Database-based address resolver for enhanced watchlist data.

This module provides address resolution using existing database tables
(pools, tokens, new_pools_history) to avoid API calls and handle
corrupted lowercase addresses.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

import aiohttp
from sqlalchemy.orm import Session

from .enhanced_rate_limiter import EnhancedRateLimiter, GlobalRateLimitCoordinator, RateLimitExceededError

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
        self.api_base_url = os.getenv(
            "GECKOTERMINAL_API_BASE_URL",
            "https://api.geckoterminal.com/api/v2",
        )
        self._rate_limiter: Optional[EnhancedRateLimiter] = None
        self._rate_limiter_ready = False
    
    async def build_address_lookup_cache(self, 
                                        network: Optional[str] = None,
                                        days_back: Optional[int] = None,
                                        use_lazy_loading: bool = True) -> Dict[str, int]:
        """
        Build a lookup cache from existing database tables.
        
        Creates mappings from lowercase addresses to their proper case versions
        using data from pools, tokens, and new_pools_history tables.
        
        Args:
            network: Optional network filter (e.g., 'solana') to limit cache size
            days_back: Optional number of days to look back for recent data only
            use_lazy_loading: If True, skip cache building and use on-demand queries (recommended)
        
        Returns:
            Dictionary with cache statistics
        """
        if use_lazy_loading:
            logger.info("Using lazy loading mode - addresses will be resolved on-demand")
            return {
                'pools_processed': 0,
                'tokens_processed': 0,
                'history_processed': 0,
                'total_mappings': 0,
                'mode': 'lazy_loading'
            }
        
        logger.info(f"Building address lookup cache from database (network: {network}, days_back: {days_back})...")
        
        stats = {
            'pools_processed': 0,
            'tokens_processed': 0,
            'history_processed': 0,
            'total_mappings': 0
        }
        
        try:
            from datetime import datetime, timedelta, timezone
            
            with self.db_manager.connection.get_session() as session:
                # Calculate date filter if specified
                date_filter = None
                if days_back:
                    date_filter = datetime.now(timezone.utc) - timedelta(days=days_back)
                    logger.info(f"Filtering records from last {days_back} days (since {date_filter})")
                
                # 1. Process pools table with filters
                pools_query = session.query(self.db_manager.PoolModel)
                if network:
                    # Extract network from pool ID (format: network_address)
                    pools_query = pools_query.filter(
                        self.db_manager.PoolModel.id.like(f"{network}_%")
                    )
                if date_filter:
                    pools_query = pools_query.filter(
                        self.db_manager.PoolModel.last_updated >= date_filter
                    )
                
                pools = pools_query.all()
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
                
                # 2. Process tokens table with filters
                tokens_query = session.query(self.db_manager.TokenModel)
                if network:
                    tokens_query = tokens_query.filter(
                        self.db_manager.TokenModel.network == network
                    )
                if date_filter:
                    tokens_query = tokens_query.filter(
                        self.db_manager.TokenModel.last_updated >= date_filter
                    )
                
                tokens = tokens_query.all()
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
                
                # 3. Process new_pools_history table with filters
                history_query = session.query(self.db_manager.NewPoolsHistoryModel)
                if network:
                    history_query = history_query.filter(
                        self.db_manager.NewPoolsHistoryModel.network_id == network
                    )
                if date_filter:
                    history_query = history_query.filter(
                        self.db_manager.NewPoolsHistoryModel.collected_at >= date_filter
                    )
                
                history_records = history_query.all()
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
        
        Uses lazy loading: queries database on-demand if not in cache.
        
        Args:
            lowercase_address: Lowercase pool address to resolve
            
        Returns:
            Dictionary with resolved address data or None if not found
        """
        if not lowercase_address:
            return None
        
        lookup_key = lowercase_address.lower()
        
        # Check cache first
        if lookup_key in self._lowercase_lookup:
            resolved = self._lowercase_lookup[lookup_key]
            logger.debug(f"Resolved address from cache ({resolved['source']}): {lowercase_address} → {resolved['address']}")
            return resolved
        
        # Not in cache - query database directly (lazy loading)
        logger.debug(f"Address not in cache, querying database for: {lowercase_address}")
        resolved = self._query_address_from_database(lowercase_address)
        
        if resolved:
            # Cache the result for future lookups
            self._lowercase_lookup[lookup_key] = resolved
            logger.debug(f"Resolved and cached address from {resolved['source']}: {lowercase_address} → {resolved['address']}")
            return resolved
        
        # Not found in cache or database
        logger.warning(f"Address not found in database: {lowercase_address}")
        return None
    
    def _query_address_from_database(self, lowercase_address: str) -> Optional[Dict[str, Any]]:
        """
        Query database directly for an address (lazy loading).
        
        This is much faster than loading all addresses upfront.
        Uses LOWER() for proper case-insensitive matching.
        
        Args:
            lowercase_address: Lowercase address to find
            
        Returns:
            Resolved address data or None
        """
        try:
            from sqlalchemy import func
            
            with self.db_manager.connection.get_session() as session:
                # Try pools table first (most likely for watchlist)
                pool = session.query(self.db_manager.PoolModel).filter(
                    func.lower(self.db_manager.PoolModel.address) == lowercase_address.lower()
                ).first()
                
                if pool:
                    return {
                        'address': pool.address,
                        'pool_id': pool.id,
                        'base_token_id': pool.base_token_id,
                        'quote_token_id': pool.quote_token_id,
                        'dex_id': pool.dex_id,
                        'source': 'pools'
                    }
                
                # Try new_pools_history table
                history = session.query(self.db_manager.NewPoolsHistoryModel).filter(
                    func.lower(self.db_manager.NewPoolsHistoryModel.address) == lowercase_address.lower()
                ).first()
                
                if history:
                    return {
                        'address': history.address,
                        'pool_id': history.pool_id,
                        'base_token_id': history.base_token_id,
                        'quote_token_id': history.quote_token_id,
                        'dex_id': history.dex_id,
                        'source': 'new_pools_history'
                    }
                
                # Try tokens table as last resort
                token = session.query(self.db_manager.TokenModel).filter(
                    func.lower(self.db_manager.TokenModel.address) == lowercase_address.lower()
                ).first()
                
                if token:
                    return {
                        'address': token.address,
                        'token_id': token.id,
                        'symbol': token.symbol,
                        'name': token.name,
                        'source': 'tokens'
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error querying address from database: {e}")
            return None
    
    async def _ensure_rate_limiter(self) -> None:
        """Initialize the shared rate limiter lazily for API-backed lookups."""
        if self._rate_limiter_ready:
            return

        try:
            # More conservative rate limiting to avoid 429s
            coordinator = await GlobalRateLimitCoordinator.get_instance(
                requests_per_minute=15,  # Reduced from 30 to be safer
                daily_limit=10000,
                state_dir=os.getenv("GECKOTERMINAL_RATE_LIMIT_STATE_DIR", None),
            )
            self._rate_limiter = await coordinator.get_limiter("database_address_resolver")
            self._rate_limiter_ready = True
        except Exception as exc:
            logger.warning(f"Unable to initialize shared rate limiter: {exc}")
            self._rate_limiter_ready = True

    async def _fetch_pool_data_from_api(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Fetch pool metadata from the GeckoTerminal API using the pool address."""
        if not pool_address:
            return None

        await self._ensure_rate_limiter()

        endpoint = f"/networks/solana/pools/{pool_address}"
        params = {
            "include": "base_token,quote_token,dex",
            "include_volume_breakdown": "false",
            "include_composition": "false",
        }

        max_attempts = int(os.getenv("GECKOTERMINAL_API_MAX_RETRIES", "10"))  # Increased from 3 to 10
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                if self._rate_limiter is not None:
                    await self._rate_limiter.acquire(endpoint="pools")

                timeout = aiohttp.ClientTimeout(total=15)  # Increased from 10 to 15
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        f"{self.api_base_url}{endpoint}",
                        params=params,
                        headers={"Accept": "application/json"},
                    ) as response:
                        if response.status == 429:
                            headers = {k: v for k, v in response.headers.items()}
                            if self._rate_limiter is not None:
                                await self._rate_limiter.handle_rate_limit_response(headers, response.status)
                            
                            # Wait for backoff period before retrying
                            if self._rate_limiter and self._rate_limiter.backoff_state.backoff_until:
                                wait_time = (self._rate_limiter.backoff_state.backoff_until - datetime.now()).total_seconds()
                                if wait_time > 0:
                                    logger.info(f"429 rate limit - waiting {wait_time:.1f}s before retry {attempt + 1}/{max_attempts}")
                                    await asyncio.sleep(wait_time)
                            else:
                                # Fallback exponential backoff if rate limiter doesn't provide wait time
                                wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                                logger.info(f"429 rate limit - waiting {wait_time}s before retry {attempt + 1}/{max_attempts}")
                                await asyncio.sleep(wait_time)
                            
                            continue

                        response.raise_for_status()
                        payload = await response.json()
                        if self._rate_limiter is not None:
                            await self._rate_limiter.handle_success()
                        return payload
            except RateLimitExceededError as exc:
                last_error = exc
                # Don't retry immediately on rate limit exceeded - the limiter is blocking for a reason
                if "Circuit breaker is open" in str(exc):
                    logger.warning(f"Circuit breaker is open for {pool_address}, waiting 10s before continuing...")
                    await asyncio.sleep(10)  # Wait longer when circuit breaker opens
                    if attempt < max_attempts:
                        continue
                    return None
                
                if attempt < max_attempts:
                    # Brief pause before retry
                    await asyncio.sleep(3)
                    continue
                logger.warning(f"Rate limiter blocked pool lookup for {pool_address}: {exc}")
                return None
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    wait_time = min(2 ** (attempt - 1), 10)  # Exponential backoff, cap at 10s
                    logger.warning(
                        f"Transient API error for pool lookup {pool_address}; retrying in {wait_time}s (attempt {attempt}/{max_attempts}): {exc}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.warning(f"Failed to fetch pool data from API for {pool_address} after {max_attempts} attempts: {exc}")
                return None

        if last_error:
            logger.warning(f"Exhausted pool lookup retries for {pool_address}: {last_error}")

        return None

    async def _resolve_token_id_from_address(self, token_address: str) -> Optional[int]:
        """Resolve a token database id from a token address when possible."""
        if not token_address:
            return None

        if not getattr(self.db_manager, "TokenModel", None):
            return None

        try:
            with self.db_manager.connection.get_session() as session:
                token = session.query(self.db_manager.TokenModel).filter_by(
                    address=token_address
                ).first()
                if token:
                    return token.id
        except Exception as exc:
            logger.warning(f"Error resolving token id for {token_address}: {exc}")

        return None

    async def get_pool_data_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get complete pool data for an address.

        This first tries the existing database tables and then falls back to
        the GeckoTerminal pool endpoint when those tables do not contain the
        pool. The API response is used to populate the token addresses and ids.
        """
        if not address:
            return None

        api_payload = await self._fetch_pool_data_from_api(address)
        if not api_payload:
            return None

        data = api_payload.get('data', {})
        attributes = data.get('attributes', {})
        relationships = data.get('relationships', {})
        included = api_payload.get('included', [])

        base_token_relationship = relationships.get('base_token', {}).get('data', {})
        quote_token_relationship = relationships.get('quote_token', {}).get('data', {})

        base_token_address = None
        quote_token_address = None
        base_token_id = None
        quote_token_id = None

        for item in included:
            if item.get('type') != 'token':
                continue
            item_id = item.get('id')
            if item_id == base_token_relationship.get('id'):
                base_token_address = item.get('attributes', {}).get('address')
            if item_id == quote_token_relationship.get('id'):
                quote_token_address = item.get('attributes', {}).get('address')

        if base_token_address:
            base_token_id = await self._resolve_token_id_from_address(base_token_address)
        if quote_token_address:
            quote_token_id = await self._resolve_token_id_from_address(quote_token_address)

        pool_data = {
            'pool_address': attributes.get('address') or address,
            'pool_id': data.get('id'),
            'base_token_address': base_token_address,
            'quote_token_address': quote_token_address,
            'base_token_id': base_token_id,
            'quote_token_id': quote_token_id,
            'dex_id': relationships.get('dex', {}).get('data', {}).get('id'),
            'source': 'api'
        }
        
        return pool_data

    async def get_pool_data_by_lowercase_address(self, lowercase_address: str) -> Optional[Dict[str, Any]]:
        """Backward-compatible wrapper for lowercase-address lookups."""
        return await self.get_pool_data_by_address(lowercase_address)
    
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
    
    async def initialize(self, use_lazy_loading: bool = True, network: str = 'solana', days_back: int = 30) -> Dict[str, int]:
        """
        Initialize the parser by building the address lookup cache.
        
        Args:
            use_lazy_loading: If True, skip cache building and query on-demand (much faster)
            network: Network to filter cache by (default: 'solana')
            days_back: Number of days to look back for recent data (default: 30)
        
        Returns:
            Cache build statistics
        """
        if not self._cache_built:
            stats = await self.address_resolver.build_address_lookup_cache(
                network=network if not use_lazy_loading else None,
                days_back=days_back if not use_lazy_loading else None,
                use_lazy_loading=use_lazy_loading
            )
            self._cache_built = True
            
            if use_lazy_loading:
                logger.info("Database address resolver initialized in lazy loading mode (on-demand queries)")
            else:
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
            address = self._extract_address_from_url(detail_url)
            
            if not address:
                logger.error(f"Could not extract address from URL: {detail_url}")
                return None
            
            # Resolve address using database lookup with API fallback
            pool_data = await self.address_resolver.get_pool_data_by_address(address)
            if not pool_data:
                logger.info(f"Skipping unresolved pool data for {address}; continuing with next row")
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

                # GMGN-specific quality fields
                'score': float(row.get('score', 0)) if row.get('score') else 0.0,
                'smart_degen_count': int(row.get('smart_degen_count', 0)) if row.get('smart_degen_count') else 0,
                'renowned_count': int(row.get('renowned_count', 0)) if row.get('renowned_count') else 0,
                'rug_ratio': float(row.get('rug_ratio', 0)) if row.get('rug_ratio') else 0.0,
                'bundler_rate': float(row.get('bundler_rate', 0)) if row.get('bundler_rate') else 0.0,
                'insider_rate': float(row.get('insider_rate', 0)) if row.get('insider_rate') else 0.0,                
                'top_10_holder_rate': float(row.get('top_10_holder_rate', 0)) if row.get('top_10_holder_rate') else 0.0,
                'dev_team_hold_rate': float(row.get('dev_team_hold_rate', 0)) if row.get('dev_team_hold_rate') else 0.0,
                'sniper_count': int(row.get('sniper_count', 0)) if row.get('sniper_count') else 0,
                'bot_degen_count': int(row.get('bot_degen_count', 0)) if row.get('bot_degen_count') else 0,

                # Resolved addresses from database
                'poolAddress': pool_data['pool_address'],
                'baseTokenAddress': pool_data['base_token_address'],
                'quoteTokenAddress': pool_data['quote_token_address'],
                'networkAddress': pool_data['base_token_address'],
                
                # Metadata
                'source': row.get('source', 'unknown'),
                'endpoint': row.get('endpoint', 'unknown'),
                'detailUrl': detail_url,
                'resolvedFrom': pool_data['source']  # Which table provided the data
            }
            
            logger.info(f"Resolved entry for {entry['tokenSymbol']}: {address} → {pool_data['pool_address']} (from {pool_data['source']})")
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
        
        # Return lowercase address as-is
        return address
    
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