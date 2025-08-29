"""
Watchlist token data collector.

This module provides functionality to collect detailed token and pool data
for tokens in the watchlist using the multiple pools API for efficiency,
with fallback to individual token and pool data collection.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import WatchlistEntry
from gecko_terminal_collector.models.core import CollectionResult, Pool, Token, ValidationResult
from gecko_terminal_collector.utils.metadata import MetadataTracker

logger = logging.getLogger(__name__)


class WatchlistCollector(BaseDataCollector):
    """
    Collects detailed token and pool data for watchlist tokens.
    
    This collector retrieves pool data using the multiple pools API for efficiency,
    with fallback to individual token and pool data collection. It handles both
    pool addresses ("id") and network addresses ("base_token_id") correctly.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False
    ):
        """
        Initialize the watchlist collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        self.network = config.dexes.network
        self.batch_size = getattr(config.watchlist, 'batch_size', 20)  # Max addresses per API call
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "watchlist_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect detailed token and pool data for watchlist tokens.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        
        try:
            # Get active watchlist entries
            logger.info("Retrieving active watchlist entries")
            watchlist_entries = await self._get_active_watchlist_entries()
            
            if not watchlist_entries:
                logger.info("No active watchlist entries found")
                return self.create_success_result(0, start_time)
            
            logger.info(f"Found {len(watchlist_entries)} active watchlist entries")
            
            # Collect pool data using multiple pools API
            pool_data_collected = await self._collect_pool_data_batch(watchlist_entries)
            records_collected += pool_data_collected
            
            # Collect individual token information for tokens not covered by pool data
            token_data_collected = await self._collect_token_data_individual(watchlist_entries)
            records_collected += token_data_collected
            
            # Update watchlist entry relationships
            await self._update_watchlist_relationships(watchlist_entries)
            
            logger.info(
                f"Watchlist collection completed: {records_collected} records collected "
                f"for {len(watchlist_entries)} watchlist entries"
            )
            
            return self.create_success_result(records_collected, start_time)
            
        except Exception as e:
            error_msg = f"Error collecting watchlist data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def _get_active_watchlist_entries(self) -> List[WatchlistEntry]:
        """
        Get all active watchlist entries from the database.
        
        Returns:
            List of active WatchlistEntry objects
        """
        try:
            # Get active watchlist pool IDs
            pool_ids = await self.db_manager.get_watchlist_pools()
            
            # Get full watchlist entries
            watchlist_entries = []
            for pool_id in pool_ids:
                entry = await self.db_manager.get_watchlist_entry_by_pool_id(pool_id)
                if entry and entry.is_active:
                    watchlist_entries.append(entry)
            
            return watchlist_entries
            
        except Exception as e:
            logger.error(f"Error retrieving watchlist entries: {e}")
            raise
    
    async def _collect_pool_data_batch(self, watchlist_entries: List[WatchlistEntry]) -> int:
        """
        Collect pool data using multiple pools API for efficiency.
        
        Args:
            watchlist_entries: List of watchlist entries to collect data for
            
        Returns:
            Number of pool records collected
        """
        records_collected = 0
        
        try:
            # Extract pool addresses for batch collection
            pool_addresses = [entry.pool_id for entry in watchlist_entries]
            
            # Process in batches to respect API limits
            for i in range(0, len(pool_addresses), self.batch_size):
                batch_addresses = pool_addresses[i:i + self.batch_size]
                
                logger.info(f"Collecting pool data for batch {i//self.batch_size + 1}: {len(batch_addresses)} pools")
                
                try:
                    # Use multiple pools API for efficiency
                    response = await self.client.get_multiple_pools_by_network(
                        self.network, 
                        batch_addresses
                    )
                    
                    # Process and store pool data
                    pools = self._parse_pools_response(response)
                    if pools:
                        stored_count = await self.db_manager.store_pools(pools)
                        records_collected += stored_count
                        logger.info(f"Stored {stored_count} pool records from batch")
                    
                except Exception as e:
                    logger.warning(f"Batch pool collection failed for addresses {batch_addresses}: {e}")
                    # Try individual collection as fallback
                    individual_count = await self._collect_pool_data_individual(batch_addresses)
                    records_collected += individual_count
            
            return records_collected
            
        except Exception as e:
            logger.error(f"Error in batch pool data collection: {e}")
            raise
    
    async def _collect_pool_data_individual(self, pool_addresses: List[str]) -> int:
        """
        Collect pool data individually as fallback when batch collection fails.
        
        Args:
            pool_addresses: List of pool addresses to collect data for
            
        Returns:
            Number of pool records collected
        """
        records_collected = 0
        
        for pool_address in pool_addresses:
            try:
                logger.debug(f"Collecting individual pool data for {pool_address}")
                
                response = await self.client.get_pool_by_network_address(
                    self.network, 
                    pool_address
                )
                
                # Process single pool response
                if response.get("data"):
                    pool = self._parse_single_pool_response(response)
                    if pool:
                        stored_count = await self.db_manager.store_pools([pool])
                        records_collected += stored_count
                        logger.debug(f"Stored individual pool record for {pool_address}")
                
            except Exception as e:
                logger.warning(f"Individual pool collection failed for {pool_address}: {e}")
                continue
        
        return records_collected
    
    async def _collect_token_data_individual(self, watchlist_entries: List[WatchlistEntry]) -> int:
        """
        Collect individual token information for watchlist entries.
        
        Args:
            watchlist_entries: List of watchlist entries to collect token data for
            
        Returns:
            Number of token records collected
        """
        records_collected = 0
        
        # Extract unique network addresses (base_token_id)
        network_addresses = set()
        for entry in watchlist_entries:
            if entry.network_address:
                network_addresses.add(entry.network_address)
        
        for network_address in network_addresses:
            try:
                logger.debug(f"Collecting token data for network address {network_address}")
                
                response = await self.client.get_token_info(
                    self.network, 
                    network_address
                )
                
                # Process token response
                if response.get("data"):
                    token = self._parse_token_response(response)
                    if token:
                        stored_count = await self.db_manager.store_tokens([token])
                        records_collected += stored_count
                        logger.debug(f"Stored token record for {network_address}")
                
            except Exception as e:
                logger.warning(f"Token collection failed for {network_address}: {e}")
                continue
        
        return records_collected
    
    async def _update_watchlist_relationships(self, watchlist_entries: List[WatchlistEntry]) -> None:
        """
        Update watchlist entry relationships with collected pool and token data.
        
        Args:
            watchlist_entries: List of watchlist entries to update
        """
        for entry in watchlist_entries:
            try:
                # Verify pool exists in database
                pool = await self.db_manager.get_pool(entry.pool_id)
                if not pool:
                    logger.warning(f"Pool {entry.pool_id} not found in database for watchlist entry")
                    continue
                
                # Verify token exists if network address is provided
                if entry.network_address:
                    token = await self.db_manager.get_token(entry.network_address)
                    if not token:
                        logger.warning(f"Token {entry.network_address} not found in database for watchlist entry")
                
                logger.debug(f"Verified relationships for watchlist entry {entry.pool_id}")
                
            except Exception as e:
                logger.warning(f"Error updating relationships for watchlist entry {entry.pool_id}: {e}")
                continue
    
    def _parse_pools_response(self, response: Dict) -> List[Pool]:
        """
        Parse multiple pools API response into Pool objects.
        
        Args:
            response: API response from get_multiple_pools_by_network
            
        Returns:
            List of Pool objects
        """
        pools = []
        
        try:
            data = response.get("data", [])
            if not isinstance(data, list):
                logger.warning("Expected list in pools response data")
                return pools
            
            for pool_data in data:
                try:
                    pool = self._parse_pool_data(pool_data)
                    if pool:
                        pools.append(pool)
                except Exception as e:
                    logger.warning(f"Error parsing pool data: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing pools response: {e}")
        
        return pools
    
    def _parse_single_pool_response(self, response: Dict) -> Optional[Pool]:
        """
        Parse single pool API response into Pool object.
        
        Args:
            response: API response from get_pool_by_network_address
            
        Returns:
            Pool object or None if parsing fails
        """
        try:
            pool_data = response.get("data")
            if not pool_data:
                return None
            
            return self._parse_pool_data(pool_data)
            
        except Exception as e:
            logger.error(f"Error parsing single pool response: {e}")
            return None
    
    def _parse_pool_data(self, pool_data: Dict) -> Optional[Pool]:
        """
        Parse individual pool data into Pool object.
        
        Args:
            pool_data: Individual pool data from API response
            
        Returns:
            Pool object or None if parsing fails
        """
        try:
            attributes = pool_data.get("attributes", {})
            relationships = pool_data.get("relationships", {})
            
            # Extract basic pool information
            pool_id = pool_data.get("id")
            address = attributes.get("address")
            name = attributes.get("name", "")
            
            # Extract DEX information
            dex_data = relationships.get("dex", {}).get("data", {})
            dex_id = dex_data.get("id", "")
            
            # Extract token information
            base_token_data = relationships.get("base_token", {}).get("data", {})
            quote_token_data = relationships.get("quote_token", {}).get("data", {})
            base_token_id = base_token_data.get("id", "")
            quote_token_id = quote_token_data.get("id", "")
            
            # Extract financial data
            reserve_usd_str = attributes.get("reserve_in_usd", "0")
            try:
                reserve_usd = Decimal(str(reserve_usd_str))
            except (ValueError, TypeError, InvalidOperation):
                reserve_usd = Decimal("0")
            
            # Extract creation date
            created_at_str = attributes.get("pool_created_at")
            created_at = None
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid date format for pool {pool_id}: {created_at_str}")
            
            # Validate required fields
            if not pool_id or not address:
                logger.warning(f"Missing required fields for pool: id={pool_id}, address={address}")
                return None
            
            return Pool(
                id=pool_id,
                address=address,
                name=name,
                dex_id=dex_id,
                base_token_id=base_token_id,
                quote_token_id=quote_token_id,
                reserve_usd=reserve_usd,
                created_at=created_at or datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error parsing pool data: {e}")
            return None
    
    def _parse_token_response(self, response: Dict) -> Optional[Token]:
        """
        Parse token API response into Token object.
        
        Args:
            response: API response from get_token_info
            
        Returns:
            Token object or None if parsing fails
        """
        try:
            token_data = response.get("data")
            if not token_data:
                return None
            
            attributes = token_data.get("attributes", {})
            
            # Extract token information
            token_id = token_data.get("id")
            address = attributes.get("address")
            name = attributes.get("name", "")
            symbol = attributes.get("symbol", "")
            
            # Extract decimals
            decimals = attributes.get("decimals", 9)
            if isinstance(decimals, str):
                try:
                    decimals = int(decimals)
                except ValueError:
                    decimals = 9
            
            # Extract price
            price_usd_str = attributes.get("price_usd")
            price_usd = None
            if price_usd_str:
                try:
                    price_usd = Decimal(str(price_usd_str))
                except (ValueError, TypeError):
                    price_usd = None
            
            # Validate required fields
            if not token_id or not address:
                logger.warning(f"Missing required fields for token: id={token_id}, address={address}")
                return None
            
            return Token(
                id=token_id,
                address=address,
                name=name,
                symbol=symbol,
                decimals=decimals,
                network=self.network,
                price_usd=price_usd
            )
            
        except Exception as e:
            logger.error(f"Error parsing token response: {e}")
            return None
    
    async def _validate_specific_data(self, data) -> Optional[ValidationResult]:
        """
        Validate collected watchlist data.
        
        Args:
            data: Data to validate (not used in this implementation)
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        try:
            # Get active watchlist entries for validation
            watchlist_entries = await self._get_active_watchlist_entries()
            
            if not watchlist_entries:
                warnings.append("No active watchlist entries found")
            
            # Validate each watchlist entry has corresponding pool data
            for entry in watchlist_entries:
                pool = await self.db_manager.get_pool(entry.pool_id)
                if not pool:
                    errors.append(f"Pool data missing for watchlist entry: {entry.pool_id}")
                
                # Validate token data if network address is provided
                if entry.network_address:
                    token = await self.db_manager.get_token(entry.network_address)
                    if not token:
                        warnings.append(f"Token data missing for network address: {entry.network_address}")
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def get_collection_status(self) -> Dict[str, any]:
        """
        Get current status of watchlist collection.
        
        Returns:
            Dictionary with collection status information
        """
        try:
            watchlist_entries = await self._get_active_watchlist_entries()
            
            # Count pools and tokens with data
            pools_with_data = 0
            tokens_with_data = 0
            
            for entry in watchlist_entries:
                pool = await self.db_manager.get_pool(entry.pool_id)
                if pool:
                    pools_with_data += 1
                
                if entry.network_address:
                    token = await self.db_manager.get_token(entry.network_address)
                    if token:
                        tokens_with_data += 1
            
            return {
                "total_watchlist_entries": len(watchlist_entries),
                "pools_with_data": pools_with_data,
                "tokens_with_data": tokens_with_data,
                "data_coverage_percentage": (
                    (pools_with_data / len(watchlist_entries) * 100) 
                    if watchlist_entries else 0
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting collection status: {e}")
            return {
                "error": str(e)
            }