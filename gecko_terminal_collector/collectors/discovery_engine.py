"""
Discovery engine for automatic pool and token discovery.

This module provides the core discovery functionality that orchestrates
the automatic discovery of DEXes, pools, and tokens following the natural
data dependency flow: DEXes → Pools → Tokens → OHLCV/Trades.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal

from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import DEX, Pool, Token
from gecko_terminal_collector.clients import BaseGeckoClient
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer, ActivityMetrics
from gecko_terminal_collector.models.core import CollectionResult

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Result of a discovery operation."""
    success: bool
    dexes_discovered: int = 0
    pools_discovered: int = 0
    tokens_discovered: int = 0
    pools_filtered: int = 0
    execution_time_seconds: float = 0.0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class DiscoveryEngine:
    """
    Orchestrates automatic discovery of DEXes, pools, and tokens.
    
    The discovery engine follows the natural data dependency flow:
    1. Discover and populate DEXes from networks
    2. Discover pools from DEXes with activity filtering
    3. Extract tokens from discovered pools
    4. Apply intelligent filtering based on activity scores
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        client: BaseGeckoClient,
        activity_scorer: Optional[ActivityScorer] = None
    ):
        """
        Initialize the discovery engine.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            client: GeckoTerminal API client
            activity_scorer: Optional activity scorer for pool filtering
        """
        self.config = config
        self.db_manager = db_manager
        self.client = client
        
        # Initialize activity scorer with discovery configuration
        if activity_scorer is None:
            self.activity_scorer = ActivityScorer(
                min_volume_threshold=config.discovery.min_volume_usd,
                min_liquidity_threshold=Decimal("5000"),  # Default liquidity threshold
                min_transaction_threshold=10,  # Default transaction threshold
                activity_threshold=config.discovery.activity_threshold
            )
        else:
            self.activity_scorer = activity_scorer
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def bootstrap_system(self) -> DiscoveryResult:
        """
        Bootstrap empty system with initial data following dependency order.
        
        This method performs a complete system initialization:
        1. Discover and populate DEXes
        2. Discover and populate pools from DEXes
        3. Extract and populate tokens from pools
        
        Returns:
            DiscoveryResult with bootstrap statistics
        """
        start_time = datetime.now()
        errors = []
        total_dexes = 0
        total_pools = 0
        total_tokens = 0
        
        try:
            self.logger.info("Starting system bootstrap process")
            
            # Step 1: Discover DEXes
            self.logger.info("Step 1: Discovering DEXes")
            dexes = await self.discover_dexes()
            if dexes:
                total_dexes = len(dexes)
                self.logger.info(f"Discovered {total_dexes} DEXes")
            else:
                error_msg = "No DEXes discovered during bootstrap"
                errors.append(error_msg)
                self.logger.error(error_msg)
                return DiscoveryResult(
                    success=False,
                    errors=errors,
                    execution_time_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            # Step 2: Discover pools from DEXes
            self.logger.info("Step 2: Discovering pools from DEXes")
            all_pools = []
            dex_ids = [dex.id for dex in dexes if dex.id]
            
            for dex_id in dex_ids:
                try:
                    dex_pools = await self.discover_pools([dex_id])
                    if dex_pools:
                        all_pools.extend(dex_pools)
                        self.logger.info(f"Discovered {len(dex_pools)} pools from DEX {dex_id}")
                except Exception as e:
                    error_msg = f"Failed to discover pools from DEX {dex_id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
                    continue
            
            if all_pools:
                total_pools = len(all_pools)
                self.logger.info(f"Total pools discovered: {total_pools}")
            else:
                error_msg = "No pools discovered during bootstrap"
                errors.append(error_msg)
                self.logger.warning(error_msg)
            
            # Step 3: Extract tokens from pools
            if all_pools:
                self.logger.info("Step 3: Extracting tokens from pools")
                try:
                    tokens = await self.extract_tokens(all_pools)
                    if tokens:
                        total_tokens = len(tokens)
                        self.logger.info(f"Extracted {total_tokens} tokens")
                except Exception as e:
                    error_msg = f"Failed to extract tokens: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(
                f"Bootstrap completed in {execution_time:.2f}s: "
                f"{total_dexes} DEXes, {total_pools} pools, {total_tokens} tokens"
            )
            
            return DiscoveryResult(
                success=len(errors) == 0,
                dexes_discovered=total_dexes,
                pools_discovered=total_pools,
                tokens_discovered=total_tokens,
                execution_time_seconds=execution_time,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Bootstrap process failed: {str(e)}"
            errors.append(error_msg)
            self.logger.error(error_msg)
            
            return DiscoveryResult(
                success=False,
                dexes_discovered=total_dexes,
                pools_discovered=total_pools,
                tokens_discovered=total_tokens,
                execution_time_seconds=(datetime.now() - start_time).total_seconds(),
                errors=errors
            )
    
    async def discover_dexes(self) -> List[DEX]:
        """
        Discover and populate DEX information from configured networks.
        
        Uses the GeckoTerminal networks API to discover available DEXes
        and stores them in the database.
        
        Returns:
            List of discovered DEX objects
        """
        discovered_dexes = []
        
        try:
            self.logger.info("Starting DEX discovery")
            
            # Discover DEXes for each configured network
            for network in self.config.discovery.target_networks:
                try:
                    self.logger.info(f"Discovering DEXes for network: {network}")
                    
                    # Get DEXes from API
                    response = await self.client.get_dexes_by_network(network)
                    
                    if not response:
                        self.logger.warning(f"No DEXes found for network {network}")
                        continue
                    
                    # Handle different response formats
                    dexes_data = response
                    if isinstance(response, dict) and 'data' in response:
                        dexes_data = response['data']
                    
                    # Process each DEX
                    for dex_data in dexes_data:
                        try:
                            dex = await self._process_dex_data(dex_data, network)
                            if dex:
                                discovered_dexes.append(dex)
                        except Exception as e:
                            self.logger.error(f"Error processing DEX data: {e}")
                            continue
                    
                    self.logger.info(f"Discovered {len(dexes_data)} DEXes for network {network}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to discover DEXes for network {network}: {e}")
                    continue
            
            self.logger.info(f"Total DEXes discovered: {len(discovered_dexes)}")
            return discovered_dexes
            
        except Exception as e:
            self.logger.error(f"DEX discovery failed: {e}")
            return []
    
    async def discover_pools(self, dex_ids: List[str]) -> List[Pool]:
        """
        Discover pools from specified DEXes with batch processing and filtering.
        
        Args:
            dex_ids: List of DEX IDs to discover pools from
            
        Returns:
            List of discovered and filtered Pool objects
        """
        discovered_pools = []
        
        try:
            self.logger.info(f"Starting pool discovery for DEXes: {dex_ids}")
            
            for dex_id in dex_ids:
                try:
                    # Get network for this DEX
                    network = await self._get_network_for_dex(dex_id)
                    if not network:
                        self.logger.warning(f"Could not determine network for DEX {dex_id}")
                        continue
                    
                    self.logger.info(f"Discovering pools for DEX {dex_id} on network {network}")
                    
                    # Discover top pools by DEX
                    pools_data = await self._discover_pools_by_dex(network, dex_id)
                    
                    if not pools_data:
                        self.logger.warning(f"No pools found for DEX {dex_id}")
                        continue
                    
                    # Process and filter pools
                    dex_pools = []
                    for pool_data in pools_data:
                        try:
                            pool = await self._process_pool_data(pool_data, dex_id)
                            if pool:
                                dex_pools.append(pool)
                        except Exception as e:
                            self.logger.error(f"Error processing pool data: {e}")
                            continue
                    
                    # Apply activity filtering
                    filtered_pools = await self.apply_filters(dex_pools)
                    
                    # Limit pools per DEX
                    max_pools = self.config.discovery.max_pools_per_dex
                    if len(filtered_pools) > max_pools:
                        # Sort by activity score (if available) and take top pools
                        filtered_pools = filtered_pools[:max_pools]
                        self.logger.info(f"Limited to top {max_pools} pools for DEX {dex_id}")
                    
                    discovered_pools.extend(filtered_pools)
                    
                    self.logger.info(
                        f"DEX {dex_id}: {len(pools_data)} found, "
                        f"{len(filtered_pools)} after filtering"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Failed to discover pools for DEX {dex_id}: {e}")
                    continue
            
            self.logger.info(f"Total pools discovered: {len(discovered_pools)}")
            return discovered_pools
            
        except Exception as e:
            self.logger.error(f"Pool discovery failed: {e}")
            return []
    
    async def extract_tokens(self, pools: List[Pool]) -> List[Token]:
        """
        Extract token information from pool data.
        
        Args:
            pools: List of Pool objects to extract tokens from
            
        Returns:
            List of unique Token objects
        """
        extracted_tokens = []
        seen_token_ids: Set[str] = set()
        
        try:
            self.logger.info(f"Extracting tokens from {len(pools)} pools")
            
            for pool in pools:
                try:
                    # Extract base token
                    if pool.base_token_id and pool.base_token_id not in seen_token_ids:
                        base_token = await self._extract_token_from_pool(pool, 'base')
                        if base_token:
                            extracted_tokens.append(base_token)
                            seen_token_ids.add(base_token.id)
                    
                    # Extract quote token
                    if pool.quote_token_id and pool.quote_token_id not in seen_token_ids:
                        quote_token = await self._extract_token_from_pool(pool, 'quote')
                        if quote_token:
                            extracted_tokens.append(quote_token)
                            seen_token_ids.add(quote_token.id)
                            
                except Exception as e:
                    self.logger.error(f"Error extracting tokens from pool {pool.id}: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(extracted_tokens)} unique tokens")
            return extracted_tokens
            
        except Exception as e:
            self.logger.error(f"Token extraction failed: {e}")
            return []
    
    async def apply_filters(self, pools: List[Pool]) -> List[Pool]:
        """
        Apply activity and volume filters to pools using ActivityScorer.
        
        Args:
            pools: List of Pool objects to filter
            
        Returns:
            List of filtered Pool objects that meet activity criteria
        """
        filtered_pools = []
        
        try:
            self.logger.info(f"Applying filters to {len(pools)} pools")
            
            for pool in pools:
                try:
                    # Create pool data dict for activity scorer
                    pool_data = await self._create_pool_data_for_scoring(pool)
                    
                    # Check if pool should be included
                    if self.activity_scorer.should_include_pool(pool_data):
                        # Calculate activity score and set priority
                        activity_score = self.activity_scorer.calculate_activity_score(pool_data)
                        priority = self.activity_scorer.get_collection_priority(activity_score)
                        
                        # Update pool with activity information
                        pool.activity_score = activity_score
                        pool.collection_priority = priority.value
                        pool.discovery_source = "auto"
                        pool.auto_discovered_at = datetime.now()
                        
                        filtered_pools.append(pool)
                        
                        self.logger.debug(
                            f"Pool {pool.id} included with activity score {activity_score:.2f}, "
                            f"priority {priority.value}"
                        )
                    else:
                        self.logger.debug(f"Pool {pool.id} filtered out due to low activity")
                        
                except Exception as e:
                    self.logger.error(f"Error filtering pool {pool.id}: {e}")
                    continue
            
            self.logger.info(
                f"Filtering complete: {len(filtered_pools)}/{len(pools)} pools passed filters"
            )
            return filtered_pools
            
        except Exception as e:
            self.logger.error(f"Pool filtering failed: {e}")
            return pools  # Return unfiltered pools on error
    
    async def _process_dex_data(self, dex_data: Dict[str, Any], network: str) -> Optional[DEX]:
        """
        Process raw DEX data from API and create DEX object.
        
        Args:
            dex_data: Raw DEX data from API
            network: Network identifier
            
        Returns:
            DEX object or None if processing fails
        """
        try:
            # Handle different data formats
            dex_id = dex_data.get('id')
            if not dex_id:
                self.logger.warning("DEX data missing required 'id' field")
                return None
            
            # Extract attributes
            attributes = dex_data.get('attributes', {})
            dex_name = attributes.get('name', dex_id)
            
            # Check if DEX already exists
            existing_dex = await self.db_manager.get_dex_by_id(dex_id)
            if existing_dex:
                self.logger.debug(f"DEX {dex_id} already exists")
                return existing_dex
            
            # Create new DEX
            dex = DEX(
                id=dex_id,
                name=dex_name,
                network=network,
                last_updated=datetime.now()
            )
            
            # Store in database
            await self.db_manager.store_dex(dex)
            self.logger.debug(f"Created DEX: {dex_id} ({dex_name})")
            
            return dex
            
        except Exception as e:
            self.logger.error(f"Error processing DEX data: {e}")
            return None
    
    async def _discover_pools_by_dex(self, network: str, dex_id: str) -> List[Dict[str, Any]]:
        """
        Discover pools for a specific DEX using API.
        
        Args:
            network: Network identifier
            dex_id: DEX identifier
            
        Returns:
            List of raw pool data from API
        """
        try:
            response = await self.client.get_top_pools_by_network_dex(network, dex_id)
            
            if not response:
                return []
            
            # Handle different response formats
            if isinstance(response, dict) and 'data' in response:
                return response['data']
            elif isinstance(response, list):
                return response
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"Error discovering pools for DEX {dex_id}: {e}")
            return []
    
    async def _process_pool_data(self, pool_data: Dict[str, Any], dex_id: str) -> Optional[Pool]:
        """
        Process raw pool data from API and create Pool object.
        
        Args:
            pool_data: Raw pool data from API
            dex_id: DEX identifier
            
        Returns:
            Pool object or None if processing fails
        """
        try:
            # Extract pool ID
            pool_id = pool_data.get('id')
            if not pool_id:
                self.logger.warning("Pool data missing required 'id' field")
                return None
            
            # Check if pool already exists
            existing_pool = await self.db_manager.get_pool_by_id(pool_id)
            if existing_pool:
                self.logger.debug(f"Pool {pool_id} already exists")
                return existing_pool
            
            # Extract attributes
            attributes = pool_data.get('attributes', {})
            relationships = pool_data.get('relationships', {})
            
            # Extract token IDs from relationships
            base_token_id = None
            quote_token_id = None
            
            if 'base_token' in relationships:
                base_token_data = relationships['base_token'].get('data', {})
                base_token_id = base_token_data.get('id')
            
            if 'quote_token' in relationships:
                quote_token_data = relationships['quote_token'].get('data', {})
                quote_token_id = quote_token_data.get('id')
            
            # Parse pool creation timestamp
            pool_created_at = None
            created_at_str = attributes.get('pool_created_at')
            if created_at_str:
                try:
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1] + '+00:00'
                    pool_created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse pool_created_at '{created_at_str}': {e}")
            
            # Create Pool object
            pool = Pool(
                id=pool_id,
                address=attributes.get('address', ''),
                name=attributes.get('name', ''),
                dex_id=dex_id,
                base_token_id=base_token_id,
                quote_token_id=quote_token_id,
                reserve_usd=Decimal(str(attributes.get('reserve_in_usd', 0))),
                created_at=pool_created_at,
                last_updated=datetime.now()
            )
            
            # Store in database
            await self.db_manager.store_pool(pool)
            self.logger.debug(f"Created pool: {pool_id}")
            
            return pool
            
        except Exception as e:
            self.logger.error(f"Error processing pool data: {e}")
            return None
    
    async def _extract_token_from_pool(self, pool: Pool, token_type: str) -> Optional[Token]:
        """
        Extract token information from pool and fetch additional data if needed.
        
        Args:
            pool: Pool object containing token references
            token_type: 'base' or 'quote' to specify which token to extract
            
        Returns:
            Token object or None if extraction fails
        """
        try:
            # Get token ID based on type
            token_id = pool.base_token_id if token_type == 'base' else pool.quote_token_id
            
            if not token_id:
                return None
            
            # Check if token already exists
            existing_token = await self.db_manager.get_token_by_id(token_id)
            if existing_token:
                return existing_token
            
            # Try to get token information from API
            try:
                # Determine network from DEX
                network = await self._get_network_for_dex(pool.dex_id)
                if not network:
                    network = "solana"  # Default fallback
                
                # Extract token address from token ID (format: network_address)
                token_address = token_id
                if '_' in token_id:
                    token_address = token_id.split('_', 1)[1]
                
                # Get token data from API
                token_response = await self.client.get_specific_token_on_network(network, token_address)
                
                if token_response and 'data' in token_response:
                    token_data = token_response['data']
                    attributes = token_data.get('attributes', {})
                    
                    token = Token(
                        id=token_id,
                        address=attributes.get('address', token_address),
                        name=attributes.get('name', ''),
                        symbol=attributes.get('symbol', ''),
                        decimals=attributes.get('decimals'),
                        network=network,
                        last_updated=datetime.now()
                    )
                else:
                    # Create minimal token record if API call fails
                    token = Token(
                        id=token_id,
                        address=token_address,
                        name='',
                        symbol='',
                        decimals=None,
                        network=network,
                        last_updated=datetime.now()
                    )
                
            except Exception as api_error:
                self.logger.warning(f"Failed to fetch token data from API: {api_error}")
                
                # Create minimal token record
                network = await self._get_network_for_dex(pool.dex_id) or "solana"
                token_address = token_id.split('_', 1)[1] if '_' in token_id else token_id
                
                token = Token(
                    id=token_id,
                    address=token_address,
                    name='',
                    symbol='',
                    decimals=None,
                    network=network,
                    last_updated=datetime.now()
                )
            
            # Store token in database
            await self.db_manager.store_token(token)
            self.logger.debug(f"Created token: {token_id}")
            
            return token
            
        except Exception as e:
            self.logger.error(f"Error extracting {token_type} token from pool {pool.id}: {e}")
            return None
    
    async def _create_pool_data_for_scoring(self, pool: Pool) -> Dict[str, Any]:
        """
        Create pool data dictionary for activity scoring.
        
        Args:
            pool: Pool object
            
        Returns:
            Dictionary formatted for ActivityScorer
        """
        # Create basic pool data structure for scoring
        # Note: This is a simplified version - in a real implementation,
        # you might want to fetch current pool data from the API
        return {
            'id': pool.id,
            'attributes': {
                'volume_usd': {'h24': str(pool.reserve_usd or 0)},  # Use reserve as proxy for volume
                'transactions': {'h24': 10},  # Default transaction count
                'reserve_in_usd': str(pool.reserve_usd or 0),
                'price_change_percentage': {'h24': '0'}  # Default price change
            }
        }
    
    async def _get_network_for_dex(self, dex_id: str) -> Optional[str]:
        """
        Get network identifier for a DEX.
        
        Args:
            dex_id: DEX identifier
            
        Returns:
            Network identifier or None if not found
        """
        try:
            dex = await self.db_manager.get_dex_by_id(dex_id)
            return dex.network if dex else None
        except Exception as e:
            self.logger.error(f"Error getting network for DEX {dex_id}: {e}")
            return None