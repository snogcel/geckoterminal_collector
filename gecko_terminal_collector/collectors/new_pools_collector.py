"""
New pools collector for systematic collection and historical tracking.
"""

import logging
import decimal
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.database.models import Pool, NewPoolsHistory
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class NewPoolsCollector(BaseDataCollector):
    """
    Collector for new pools data using get_new_pools_by_network() API method.
    
    This collector systematically fetches new pools for specified networks,
    populates the Pools table to resolve foreign key constraints, and maintains
    comprehensive historical records for predictive modeling.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        network: str,
        **kwargs
    ):
        """
        Initialize the new pools collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            network: Network identifier to collect pools for
            **kwargs: Additional arguments passed to base class
        """
        # Set network before calling super() to avoid logger initialization issues
        self.network = network
        super().__init__(config, db_manager, **kwargs)
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return f"new_pools_{self.network}"
    
    async def collect(self) -> CollectionResult:
        """
        Collect new pools data for the specified network.
        
        Returns:
            CollectionResult with collection status and statistics
        """
        start_time = datetime.now()
        errors = []
        pools_created = 0
        history_records = 0
        
        try:
            self.logger.info(f"Starting new pools collection for network: {self.network}")
            
            # Fetch new pools data using the SDK method
            response = await self.make_api_request(
                self.client.get_new_pools_by_network,
                self.network
            )
            
            if response is None or (isinstance(response, dict) and 'data' not in response):
                error_msg = f"No data received from API for network {self.network}"
                self.logger.warning(error_msg)
                return self.create_failure_result([error_msg], 0, start_time)
            
            # Handle different response formats (dict with 'data' key, DataFrame, or direct list)
            if isinstance(response, dict) and 'data' in response:
                pools_data = response['data']
            elif hasattr(response, 'to_dict'):  # pandas DataFrame
                pools_data = response.to_dict('records')
            elif isinstance(response, list):
                pools_data = response
            else:
                # Try to normalize the response using the data normalizer
                pools_data = self.normalize_response_data(response)
            
            self.logger.info(f"Received {len(pools_data)} new pools from API")
            
            # Validate the response data
            validation_result = await self.validate_data(pools_data)
            if not validation_result.is_valid:
                # Log validation errors but continue processing valid records
                error_msg = f"Data validation failed: {'; '.join(validation_result.errors)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                # Don't return early - continue processing what we can
            
            # Process each pool
            for pool_data in pools_data:
                try:
                    # Extract and validate pool information
                    pool_info = self._extract_pool_info(pool_data)
                    if not pool_info:
                        self.logger.warning(f"Failed to extract pool info from: {pool_data}")
                        continue
                    
                    # Check if pool already exists and create if needed
                    pool_created = await self._ensure_pool_exists(pool_info)
                    if pool_created:
                        pools_created += 1
                    
                    # Always create historical record for predictive modeling
                    history_record = self._create_history_record(pool_data)
                    if history_record:
                        await self._store_history_record(history_record)
                        history_records += 1
                        
                except Exception as e:
                    error_msg = f"Error processing pool {pool_data.get('id', 'unknown')}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            total_records = pools_created + history_records
            
            self.logger.info(
                f"New pools collection completed for {self.network}: "
                f"{pools_created} pools created, {history_records} history records"
            )
            
            return CollectionResult(
                success=True,
                records_collected=total_records,
                errors=errors,
                collection_time=start_time,
                collector_type=self.get_collection_key(),
                metadata={
                    'network': self.network,
                    'pools_created': pools_created,
                    'history_records': history_records,
                    'api_pools_received': len(pools_data)
                }
            )
            
        except Exception as e:
            error_msg = f"New pools collection failed for {self.network}: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            return self.create_failure_result(errors, pools_created + history_records, start_time)
    
    def _extract_pool_info(self, pool_data: Dict) -> Optional[Dict]:
        """
        Extract essential pool information for the Pools table.
        
        Args:
            pool_data: Raw pool data from API
            
        Returns:
            Dictionary with pool information or None if extraction fails
        """
        try:
            attributes = pool_data.get('attributes', {})
            
            # Validate required fields
            pool_id = pool_data.get('id')
            if not pool_id:
                self.logger.warning("Pool data missing required 'id' field")
                return None
            
            # Parse pool creation timestamp
            pool_created_at = None
            created_at_str = attributes.get('pool_created_at')
            if created_at_str:
                try:
                    # Handle ISO format with Z suffix
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1] + '+00:00'
                    pool_created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse pool_created_at '{created_at_str}': {e}")
            
            return {
                'id': pool_id,
                'address': attributes.get('address', ''),
                'name': attributes.get('name', ''),
                'dex_id': attributes.get('dex_id', ''),
                'base_token_id': attributes.get('base_token_id', ''),
                'quote_token_id': attributes.get('quote_token_id', ''),
                'reserve_usd': Decimal(str(attributes.get('reserve_in_usd', 0))),
                'created_at': pool_created_at,
                'last_updated': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting pool info: {e}")
            return None
    
    def _create_history_record(self, pool_data: Dict) -> Optional[Dict]:
        """
        Create comprehensive historical record for predictive modeling.
        
        Args:
            pool_data: Raw pool data from API
            
        Returns:
            Dictionary with history record data or None if creation fails
        """
        try:
            attributes = pool_data.get('attributes', {})
            
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
            
            # Helper function to safely convert to Decimal
            def safe_decimal(value, default=None):
                if value is None or value == '':
                    return default
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError, decimal.InvalidOperation):
                    return default
            
            # Helper function to safely convert to int
            def safe_int(value, default=None):
                if value is None or value == '':
                    return default
                try:
                    # Handle float strings by converting to float first, then int
                    return int(float(value))
                except (ValueError, TypeError):
                    return default
            
            return {
                'pool_id': pool_data.get('id'),
                'type': pool_data.get('type', 'pool'),
                'name': attributes.get('name'),
                'base_token_price_usd': safe_decimal(attributes.get('base_token_price_usd')),
                'base_token_price_native_currency': safe_decimal(attributes.get('base_token_price_native_currency')),
                'quote_token_price_usd': safe_decimal(attributes.get('quote_token_price_usd')),
                'quote_token_price_native_currency': safe_decimal(attributes.get('quote_token_price_native_currency')),
                'address': attributes.get('address'),
                'reserve_in_usd': safe_decimal(attributes.get('reserve_in_usd')),
                'pool_created_at': pool_created_at,
                'fdv_usd': safe_decimal(attributes.get('fdv_usd')),
                'market_cap_usd': safe_decimal(attributes.get('market_cap_usd')),
                'price_change_percentage_h1': safe_decimal(attributes.get('price_change_percentage_h1')),
                'price_change_percentage_h24': safe_decimal(attributes.get('price_change_percentage_h24')),
                'transactions_h1_buys': safe_int(attributes.get('transactions_h1_buys')),
                'transactions_h1_sells': safe_int(attributes.get('transactions_h1_sells')),
                'transactions_h24_buys': safe_int(attributes.get('transactions_h24_buys')),
                'transactions_h24_sells': safe_int(attributes.get('transactions_h24_sells')),
                'volume_usd_h24': safe_decimal(attributes.get('volume_usd_h24')),
                'dex_id': attributes.get('dex_id'),
                'base_token_id': attributes.get('base_token_id'),
                'quote_token_id': attributes.get('quote_token_id'),
                'network_id': attributes.get('network_id', self.network),
                'collected_at': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error creating history record: {e}")
            return None
    
    async def _ensure_pool_exists(self, pool_info: Dict) -> bool:
        """
        Ensure pool exists in the Pools table, create if it doesn't.
        
        Args:
            pool_info: Pool information dictionary
            
        Returns:
            True if pool was created, False if it already existed
        """
        try:
            # Check if pool already exists
            existing_pool = await self.db_manager.get_pool_by_id(pool_info['id'])
            if existing_pool:
                self.logger.debug(f"Pool {pool_info['id']} already exists")
                return False
            
            # Create new pool record
            pool = Pool(**pool_info)
            await self.db_manager.store_pool(pool)
            self.logger.debug(f"Created new pool: {pool_info['id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error ensuring pool exists for {pool_info.get('id')}: {e}")
            return False
    
    async def _store_history_record(self, history_record: Dict) -> None:
        """
        Store historical record in the new_pools_history table.
        
        Args:
            history_record: History record data dictionary
        """
        try:
            # Create NewPoolsHistory model instance
            history_entry = NewPoolsHistory(**history_record)
            
            # Store using database manager
            await self.db_manager.store_new_pools_history(history_entry)
            self.logger.debug(f"Stored history record for pool: {history_record['pool_id']}")
            
        except Exception as e:
            self.logger.error(f"Error storing history record for {history_record.get('pool_id')}: {e}")
            raise
    
    async def _validate_specific_data(self, data: Any) -> Optional[ValidationResult]:
        """
        Validate new pools specific data structure.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        if not isinstance(data, list):
            errors.append(f"Expected list of pools, got {type(data)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        if len(data) == 0:
            warnings.append("No new pools data received")
        
        # Validate individual pool records
        for i, pool_data in enumerate(data):
            if not isinstance(pool_data, dict):
                errors.append(f"Pool {i}: Expected dict, got {type(pool_data)}")
                continue
            
            # Check required fields
            if 'id' not in pool_data:
                errors.append(f"Pool {i}: Missing required 'id' field")
            
            if 'attributes' not in pool_data:
                errors.append(f"Pool {i}: Missing 'attributes' field")
                continue
            
            attributes = pool_data['attributes']
            if not isinstance(attributes, dict):
                errors.append(f"Pool {i}: 'attributes' must be a dict")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )