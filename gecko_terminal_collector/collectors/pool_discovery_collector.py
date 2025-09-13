"""
Pool discovery collector for automatic pool discovery and management.

This module provides the PoolDiscoveryCollector class that orchestrates
automatic pool discovery from DEXes, replacing the manual watchlist approach
with intelligent pool filtering and activity-based prioritization.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import Pool, Token, DEX
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer, CollectionPriority
from gecko_terminal_collector.utils.metadata import MetadataTracker

logger = logging.getLogger(__name__)


class PoolDiscoveryCollector(BaseDataCollector):
    """
    Discovers and manages pools automatically from DEXes.
    
    This collector replaces the watchlist-based approach with intelligent
    pool discovery that:
    1. Discovers top pools by volume from configured DEXes
    2. Discovers newly created pools within a lookback window
    3. Evaluates pool activity using the ActivityScorer
    4. Manages pool collection priorities based on activity
    5. Integrates with existing rate limiting and error handling
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False
    ):
        """
        Initialize the pool discovery collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        # Initialize activity scorer with discovery configuration
        self.activity_scorer = ActivityScorer(
            min_volume_threshold=config.discovery.min_volume_usd,
            min_liquidity_threshold=Decimal("5000"),  # Default liquidity threshold
            min_transaction_threshold=10,  # Default transaction threshold
            activity_threshold=config.discovery.activity_threshold
        )
        
        # Discovery configuration shortcuts
        self.discovery_config = config.discovery
        self.max_pools_per_dex = config.discovery.max_pools_per_dex
        self.new_pool_lookback_hours = config.discovery.new_pool_lookback_hours
        self.target_networks = config.discovery.target_networks
        
        self.logger.info(
            f"PoolDiscoveryCollector initialized for networks: {self.target_networks}, "
            f"max_pools_per_dex: {self.max_pools_per_dex}"
        )
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "pool_discovery_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Orchestrate pool discovery process.
        
        This method coordinates the complete pool discovery workflow:
        1. Discover top pools from configured DEXes
        2. Discover new pools created recently
        3. Evaluate activity for all discovered pools
        4. Update pool priorities and metadata
        
        Returns:
            CollectionResult with details about the discovery operation
        """
        start_time = datetime.now()
        errors = []
        total_pools_discovered = 0
        total_pools_updated = 0
        
        try:
            self.logger.info("Starting pool discovery process")
            
            # Get available DEXes for discovery
            available_dexes = await self._get_available_dexes()
            if not available_dexes:
                error_msg = "No DEXes available for pool discovery"
                self.logger.warning(error_msg)
                return self.create_failure_result([error_msg], 0, start_time)
            
            self.logger.info(f"Discovered {len(available_dexes)} DEXes for pool discovery")
            
            # Discover top pools from each DEX
            for dex in available_dexes:
                try:
                    self.logger.info(f"Discovering top pools for DEX: {dex.id}")
                    
                    # Discover top pools by volume
                    top_pools = await self.discover_top_pools(dex.id, self.max_pools_per_dex)
                    
                    if top_pools:
                        # Store discovered pools
                        stored_count = await self._store_discovered_pools(top_pools)
                        total_pools_discovered += stored_count
                        
                        self.logger.info(
                            f"DEX {dex.id}: discovered {len(top_pools)} pools, "
                            f"stored {stored_count} new pools"
                        )
                    else:
                        self.logger.warning(f"No top pools discovered for DEX {dex.id}")
                        
                except Exception as e:
                    error_msg = f"Error discovering top pools for DEX {dex.id}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Discover new pools across all networks
            for network in self.target_networks:
                try:
                    self.logger.info(f"Discovering new pools for network: {network}")
                    
                    # Calculate lookback time
                    since_time = datetime.now() - timedelta(hours=self.new_pool_lookback_hours)
                    
                    # Discover new pools
                    new_pools = await self.discover_new_pools(network, since_time)
                    
                    if new_pools:
                        # Store discovered pools
                        stored_count = await self._store_discovered_pools(new_pools)
                        total_pools_discovered += stored_count
                        
                        self.logger.info(
                            f"Network {network}: discovered {len(new_pools)} new pools, "
                            f"stored {stored_count} new pools"
                        )
                    else:
                        self.logger.info(f"No new pools discovered for network {network}")
                        
                except Exception as e:
                    error_msg = f"Error discovering new pools for network {network}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Evaluate activity for existing pools and update priorities
            try:
                self.logger.info("Evaluating pool activity and updating priorities")
                updated_count = await self._evaluate_and_update_pool_activity()
                total_pools_updated += updated_count
                
                self.logger.info(f"Updated activity scores for {updated_count} pools")
                
            except Exception as e:
                error_msg = f"Error evaluating pool activity: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
            
            # Calculate total records processed
            total_records = total_pools_discovered + total_pools_updated
            
            self.logger.info(
                f"Pool discovery completed: {total_pools_discovered} pools discovered, "
                f"{total_pools_updated} pools updated, {len(errors)} errors"
            )
            
            return CollectionResult(
                success=len(errors) == 0,
                records_collected=total_records,
                errors=errors,
                collection_time=start_time,
                collector_type=self.get_collection_key(),
                metadata={
                    'pools_discovered': total_pools_discovered,
                    'pools_updated': total_pools_updated,
                    'dexes_processed': len(available_dexes),
                    'networks_processed': len(self.target_networks),
                    'errors_count': len(errors)
                }
            )
            
        except Exception as e:
            error_msg = f"Pool discovery process failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, total_pools_discovered + total_pools_updated, start_time)
    
    async def discover_top_pools(self, dex_id: str, limit: int) -> List[Pool]:
        """
        Discover top pools by volume for a DEX.
        
        Args:
            dex_id: DEX identifier to discover pools from
            limit: Maximum number of pools to discover
            
        Returns:
            List of discovered Pool objects with activity filtering applied
        """
        discovered_pools = []
        
        try:
            self.logger.debug(f"Discovering top {limit} pools for DEX {dex_id}")
            
            # Get network for this DEX
            dex = await self.db_manager.get_dex_by_id(dex_id)
            if not dex or not dex.network:
                self.logger.warning(f"Could not determine network for DEX {dex_id}")
                return []
            
            network = dex.network
            
            # Get top pools by DEX from API
            response = await self.make_api_request(
                self.client.get_top_pools_by_network_dex,
                network,
                dex_id
            )
            
            if not response:
                self.logger.warning(f"No response from top pools API for DEX {dex_id}")
                return []
            
            # Handle different response formats
            pools_data = response
            if isinstance(response, dict) and 'data' in response:
                pools_data = response['data']
            
            if not pools_data:
                self.logger.warning(f"No pools data in response for DEX {dex_id}")
                return []
            
            self.logger.debug(f"Received {len(pools_data)} pools from API for DEX {dex_id}")
            
            # Process each pool
            for pool_data in pools_data[:limit]:  # Respect the limit
                try:
                    # Parse pool data
                    pool = await self._parse_pool_data(pool_data, dex_id)
                    if not pool:
                        continue
                    
                    # Apply activity filtering
                    if await self._should_include_pool(pool_data):
                        # Calculate activity score and set priority
                        activity_score = self.activity_scorer.calculate_activity_score(pool_data)
                        priority = self.activity_scorer.get_collection_priority(activity_score)
                        
                        # Update pool with discovery metadata
                        pool.activity_score = activity_score
                        pool.collection_priority = priority.value
                        pool.discovery_source = "auto"
                        pool.auto_discovered_at = datetime.now()
                        pool.last_activity_check = datetime.now()
                        
                        discovered_pools.append(pool)
                        
                        self.logger.debug(
                            f"Pool {pool.id} included with activity score {activity_score:.2f}, "
                            f"priority {priority.value}"
                        )
                    else:
                        self.logger.debug(f"Pool {pool.id} filtered out due to low activity")
                        
                except Exception as e:
                    self.logger.warning(f"Error processing pool data for DEX {dex_id}: {e}")
                    continue
            
            self.logger.info(
                f"DEX {dex_id}: {len(discovered_pools)}/{len(pools_data)} pools passed activity filters"
            )
            
            return discovered_pools
            
        except Exception as e:
            self.logger.error(f"Error discovering top pools for DEX {dex_id}: {e}")
            return []
    
    async def discover_new_pools(self, network: str, since: datetime) -> List[Pool]:
        """
        Discover newly created pools for a network since a given timestamp.
        
        Args:
            network: Network identifier to discover pools from
            since: Only include pools created after this timestamp
            
        Returns:
            List of discovered Pool objects for newly created pools
        """
        discovered_pools = []
        
        try:
            self.logger.debug(f"Discovering new pools for network {network} since {since}")
            
            # Get new pools from API
            response = await self.make_api_request(
                self.client.get_new_pools_by_network,
                network
            )
            
            if not response:
                self.logger.warning(f"No response from new pools API for network {network}")
                return []
            
            # Handle different response formats
            pools_data = response
            if isinstance(response, dict) and 'data' in response:
                pools_data = response['data']
            elif hasattr(response, 'to_dict'):  # pandas DataFrame
                pools_data = response.to_dict('records')
            
            if not pools_data:
                self.logger.warning(f"No pools data in response for network {network}")
                return []
            
            self.logger.debug(f"Received {len(pools_data)} new pools from API for network {network}")
            
            # Process each pool
            for pool_data in pools_data:
                try:
                    # Check if pool was created after the since timestamp
                    if not await self._is_pool_new_enough(pool_data, since):
                        continue
                    
                    # Parse pool data (extract DEX ID from pool data)
                    attributes = pool_data.get('attributes', {})
                    dex_id = attributes.get('dex_id', '')
                    
                    if not dex_id:
                        self.logger.warning(f"Pool data missing dex_id: {pool_data.get('id', 'unknown')}")
                        continue
                    
                    pool = await self._parse_pool_data(pool_data, dex_id)
                    if not pool:
                        continue
                    
                    # Apply activity filtering for new pools
                    if await self._should_include_pool(pool_data):
                        # Calculate activity score and set priority
                        activity_score = self.activity_scorer.calculate_activity_score(pool_data)
                        priority = self.activity_scorer.get_collection_priority(activity_score)
                        
                        # Update pool with discovery metadata
                        pool.activity_score = activity_score
                        pool.collection_priority = priority.value
                        pool.discovery_source = "auto_new"
                        pool.auto_discovered_at = datetime.now()
                        pool.last_activity_check = datetime.now()
                        
                        discovered_pools.append(pool)
                        
                        self.logger.debug(
                            f"New pool {pool.id} included with activity score {activity_score:.2f}"
                        )
                    else:
                        self.logger.debug(f"New pool {pool.id} filtered out due to low activity")
                        
                except Exception as e:
                    self.logger.warning(f"Error processing new pool data for network {network}: {e}")
                    continue
            
            self.logger.info(
                f"Network {network}: {len(discovered_pools)}/{len(pools_data)} new pools passed filters"
            )
            
            return discovered_pools
            
        except Exception as e:
            self.logger.error(f"Error discovering new pools for network {network}: {e}")
            return []
    
    async def evaluate_pool_activity(self, pool_id: str) -> Optional[Decimal]:
        """
        Evaluate pool activity for ongoing pool assessment.
        
        This method fetches current pool data and calculates an updated
        activity score for priority adjustment and collection scheduling.
        
        Args:
            pool_id: Pool identifier to evaluate
            
        Returns:
            Updated activity score or None if evaluation fails
        """
        try:
            self.logger.debug(f"Evaluating activity for pool {pool_id}")
            
            # Get pool from database to determine network
            pool = await self.db_manager.get_pool_by_id(pool_id)
            if not pool:
                self.logger.warning(f"Pool {pool_id} not found in database")
                return None
            
            # Get DEX to determine network
            dex = await self.db_manager.get_dex_by_id(pool.dex_id)
            if not dex:
                self.logger.warning(f"DEX {pool.dex_id} not found for pool {pool_id}")
                return None
            
            network = dex.network
            
            # Get current pool data from API
            response = await self.make_api_request(
                self.client.get_pool_by_network_address,
                network,
                pool.address
            )
            
            if not response or not response.get('data'):
                self.logger.warning(f"No current data available for pool {pool_id}")
                return None
            
            pool_data = response['data']
            
            # Calculate updated activity score
            activity_score = self.activity_scorer.calculate_activity_score(pool_data)
            
            # Update pool in database
            pool.activity_score = activity_score
            pool.last_activity_check = datetime.now()
            
            # Update collection priority based on new score
            priority = self.activity_scorer.get_collection_priority(activity_score)
            pool.collection_priority = priority.value
            
            # Store updated pool
            await self.db_manager.store_pool(pool)
            
            self.logger.debug(
                f"Pool {pool_id} activity updated: score {activity_score:.2f}, "
                f"priority {priority.value}"
            )
            
            return activity_score
            
        except Exception as e:
            self.logger.error(f"Error evaluating activity for pool {pool_id}: {e}")
            return None
    
    async def _get_available_dexes(self) -> List[DEX]:
        """
        Get available DEXes for pool discovery from target networks.
        
        Returns:
            List of DEX objects available for discovery
        """
        try:
            available_dexes = []
            
            for network in self.target_networks:
                try:
                    # Get DEXes for this network from database
                    network_dexes = await self.db_manager.get_dexes_by_network(network)
                    if network_dexes:
                        available_dexes.extend(network_dexes)
                        self.logger.debug(f"Found {len(network_dexes)} DEXes for network {network}")
                    else:
                        self.logger.warning(f"No DEXes found for network {network}")
                        
                except Exception as e:
                    self.logger.error(f"Error getting DEXes for network {network}: {e}")
                    continue
            
            return available_dexes
            
        except Exception as e:
            self.logger.error(f"Error getting available DEXes: {e}")
            return []
    
    async def _parse_pool_data(self, pool_data: Dict[str, Any], dex_id: str) -> Optional[Pool]:
        """
        Parse raw pool data from API into Pool object.
        
        Args:
            pool_data: Raw pool data from API
            dex_id: DEX identifier for the pool
            
        Returns:
            Pool object or None if parsing fails
        """
        try:
            # Extract pool ID
            pool_id = pool_data.get('id')
            if not pool_id:
                self.logger.warning("Pool data missing required 'id' field")
                return None
            
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
            
            return pool
            
        except Exception as e:
            self.logger.error(f"Error parsing pool data: {e}")
            return None
    
    async def _should_include_pool(self, pool_data: Dict[str, Any]) -> bool:
        """
        Check if pool should be included based on activity criteria.
        
        Args:
            pool_data: Raw pool data from API
            
        Returns:
            True if pool meets inclusion criteria, False otherwise
        """
        try:
            return self.activity_scorer.should_include_pool(pool_data)
        except Exception as e:
            self.logger.warning(f"Error checking pool inclusion criteria: {e}")
            return False
    
    async def _is_pool_new_enough(self, pool_data: Dict[str, Any], since: datetime) -> bool:
        """
        Check if pool was created after the given timestamp.
        
        Args:
            pool_data: Raw pool data from API
            since: Minimum creation timestamp
            
        Returns:
            True if pool is new enough, False otherwise
        """
        try:
            attributes = pool_data.get('attributes', {})
            created_at_str = attributes.get('pool_created_at')
            
            if not created_at_str:
                # If no creation time, assume it's old
                return False
            
            # Parse creation timestamp
            if created_at_str.endswith('Z'):
                created_at_str = created_at_str[:-1] + '+00:00'
            
            pool_created_at = datetime.fromisoformat(created_at_str)
            
            # Check if created after since timestamp
            # Make sure both datetimes have the same timezone info
            if pool_created_at.tzinfo is None and since.tzinfo is not None:
                # Make since timezone-naive to match pool_created_at
                since = since.replace(tzinfo=None)
            elif pool_created_at.tzinfo is not None and since.tzinfo is None:
                # Make pool_created_at timezone-naive to match since
                pool_created_at = pool_created_at.replace(tzinfo=None)
            
            return pool_created_at > since
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing pool creation time: {e}")
            return False
    
    async def _store_discovered_pools(self, pools: List[Pool]) -> int:
        """
        Store discovered pools in the database.
        
        Args:
            pools: List of Pool objects to store
            
        Returns:
            Number of pools actually stored (new pools only)
        """
        try:
            if not pools:
                return 0
            
            stored_count = 0
            
            for pool in pools:
                try:
                    # Check if pool already exists
                    existing_pool = await self.db_manager.get_pool_by_id(pool.id)
                    
                    if existing_pool:
                        # Update existing pool with new activity data
                        existing_pool.activity_score = pool.activity_score
                        existing_pool.collection_priority = pool.collection_priority
                        existing_pool.last_activity_check = pool.last_activity_check
                        existing_pool.last_updated = datetime.now()
                        
                        await self.db_manager.store_pool(existing_pool)
                        self.logger.debug(f"Updated existing pool: {pool.id}")
                    else:
                        # Store new pool
                        await self.db_manager.store_pool(pool)
                        stored_count += 1
                        self.logger.debug(f"Stored new pool: {pool.id}")
                        
                except Exception as e:
                    self.logger.error(f"Error storing pool {pool.id}: {e}")
                    continue
            
            return stored_count
            
        except Exception as e:
            self.logger.error(f"Error storing discovered pools: {e}")
            return 0
    
    async def _evaluate_and_update_pool_activity(self) -> int:
        """
        Evaluate activity for existing pools and update their priorities.
        
        Returns:
            Number of pools updated
        """
        try:
            # Get all auto-discovered pools that need activity updates
            cutoff_time = datetime.now() - timedelta(hours=1)  # Update pools not checked in last hour
            
            pools_to_update = await self.db_manager.get_pools_needing_activity_update(cutoff_time)
            
            if not pools_to_update:
                self.logger.debug("No pools need activity updates")
                return 0
            
            updated_count = 0
            
            for pool in pools_to_update:
                try:
                    # Evaluate pool activity
                    activity_score = await self.evaluate_pool_activity(pool.id)
                    
                    if activity_score is not None:
                        updated_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"Error updating activity for pool {pool.id}: {e}")
                    continue
            
            return updated_count
            
        except Exception as e:
            self.logger.error(f"Error evaluating pool activity: {e}")
            return 0
    
    async def _validate_specific_data(self, data: Any) -> Optional[ValidationResult]:
        """
        Validate pool discovery specific data.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        try:
            # Validate discovery configuration
            if not self.discovery_config.enabled:
                warnings.append("Pool discovery is disabled in configuration")
            
            if not self.target_networks:
                errors.append("No target networks configured for discovery")
            
            if self.max_pools_per_dex <= 0:
                errors.append("max_pools_per_dex must be greater than 0")
            
            # Validate activity scorer configuration
            if self.discovery_config.min_volume_usd <= 0:
                warnings.append("Minimum volume threshold is 0 - all pools will be included")
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )