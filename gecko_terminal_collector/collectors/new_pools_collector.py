"""
New pools collector for systematic collection and historical tracking with signal analysis.
"""

import logging
import decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.database.models import Pool as PoolModel
from gecko_terminal_collector.database.postgresql_models import NewPoolsHistory
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer, SignalResult

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
        
        # Initialize signal analyzer
        new_pools_config = getattr(config, 'new_pools', None)
        if new_pools_config and hasattr(new_pools_config, 'signal_detection'):
            signal_config = new_pools_config.signal_detection.__dict__ if hasattr(new_pools_config.signal_detection, '__dict__') else {}
        else:
            signal_config = {}
        
        self.signal_analyzer = NewPoolsSignalAnalyzer(signal_config)
        self.signal_analysis_enabled = signal_config.get('enabled', True)
        
        # Check auto-watchlist setting
        self.auto_watchlist_enabled = False
        if new_pools_config and hasattr(new_pools_config, 'networks'):
            network_config = new_pools_config.networks.get(network, None)
            if network_config and hasattr(network_config, 'auto_watchlist_integration'):
                self.auto_watchlist_enabled = network_config.auto_watchlist_integration
        
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
            
            #print("-_NewPoolsCollector--")
            #print(pools_data)
            #print("---")

            # Validate the response data
            validation_result = await self.validate_data(pools_data)

            print("_validation_result_")
            print(validation_result)
            print("---")

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
                    
                    # Perform signal analysis if enabled
                    signal_result = None
                    if self.signal_analysis_enabled:
                        signal_result = await self._analyze_pool_signals(pool_data)
                        
                        # Auto-add to watchlist if signal is strong enough
                        if self.auto_watchlist_enabled and signal_result:
                            await self._handle_auto_watchlist(pool_data, signal_result)
                    
                    # Always create historical record for predictive modeling
                    history_record = self._create_history_record(pool_data, signal_result)
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
        Handles both nested (attributes) and flat data formats.
        
        Args:
            pool_data: Raw pool data from API
            
        Returns:
            Dictionary with pool information or None if extraction fails
        """
        try:
            from gecko_terminal_collector.utils.pool_id_utils import PoolIDUtils
            
            # Handle both data formats: nested in 'attributes' or flat structure
            attributes = pool_data.get('attributes', {})
            
            # Helper function to get field from either attributes or root level
            def get_field(field_name, default=''):
                # Try attributes first, then root level
                return attributes.get(field_name, pool_data.get(field_name, default))
            
            # Validate required fields
            pool_id = pool_data.get('id')
            if not pool_id:
                self.logger.warning("Pool data missing required 'id' field")
                return None
            
            # Ensure pool ID has proper network prefix
            pool_id = PoolIDUtils.normalize_pool_id(pool_id, self.network)
            
            # Validate DEX ID - this is required for foreign key constraint
            dex_id = get_field('dex_id', '').strip()
            if not dex_id:
                self.logger.warning(f"Pool {pool_id} has empty dex_id, skipping")
                return None
            
            # Parse pool creation timestamp
            pool_created_at = None
            created_at_str = get_field('pool_created_at')
            if created_at_str:
                try:
                    # Handle ISO format with Z suffix
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1] + '+00:00'
                    pool_created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse pool_created_at '{created_at_str}': {e}")
            
            # Clean and validate other fields
            address = get_field('address', '').strip()
            name = get_field('name', '').strip()
            base_token_id = get_field('base_token_id', '').strip()
            quote_token_id = get_field('quote_token_id', '').strip()
            
            return {
                'id': pool_id,
                'address': address,
                'name': name,
                'dex_id': dex_id,
                'base_token_id': base_token_id if base_token_id else None,
                'quote_token_id': quote_token_id if quote_token_id else None,
                'reserve_usd': Decimal(str(get_field('reserve_in_usd', 0))),
                'created_at': pool_created_at,
                'last_updated': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting pool info: {e}")
            return None
    
    def _create_history_record(self, pool_data: Dict, signal_result: Optional[SignalResult] = None) -> Optional[Dict]:
        """
        Create comprehensive historical record for predictive modeling.
        Handles both nested (attributes) and flat data formats.
        
        Args:
            pool_data: Raw pool data from API
            
        Returns:
            Dictionary with history record data or None if creation fails
        """
        try:
            # Handle both data formats: nested in 'attributes' or flat structure
            attributes = pool_data.get('attributes', {})
            
            # Helper function to get field from either attributes or root level
            def get_field(field_name, default=None):
                # Try attributes first, then root level
                return attributes.get(field_name, pool_data.get(field_name, default))
            
            # Parse pool creation timestamp
            pool_created_at = None
            created_at_str = get_field('pool_created_at')
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
            
            # Base record data
            record_data = {
                'pool_id': pool_data.get('id'),
                'type': pool_data.get('type', 'pool'),
                'name': get_field('name'),
                'base_token_price_usd': safe_decimal(get_field('base_token_price_usd')),
                'base_token_price_native_currency': safe_decimal(get_field('base_token_price_native_currency')),
                'quote_token_price_usd': safe_decimal(get_field('quote_token_price_usd')),
                'quote_token_price_native_currency': safe_decimal(get_field('quote_token_price_native_currency')),
                'address': get_field('address'),
                'reserve_in_usd': safe_decimal(get_field('reserve_in_usd')),
                'pool_created_at': pool_created_at,
                'fdv_usd': safe_decimal(get_field('fdv_usd')),
                'market_cap_usd': safe_decimal(get_field('market_cap_usd')),
                'price_change_percentage_h1': safe_decimal(get_field('price_change_percentage_h1')),
                'price_change_percentage_h24': safe_decimal(get_field('price_change_percentage_h24')),
                'transactions_h1_buys': safe_int(get_field('transactions_h1_buys')),
                'transactions_h1_sells': safe_int(get_field('transactions_h1_sells')),
                'transactions_h24_buys': safe_int(get_field('transactions_h24_buys')),
                'transactions_h24_sells': safe_int(get_field('transactions_h24_sells')),
                'volume_usd_h24': safe_decimal(get_field('volume_usd_h24')),
                'dex_id': get_field('dex_id'),
                'base_token_id': get_field('base_token_id'),
                'quote_token_id': get_field('quote_token_id'),
                'network_id': get_field('network_id', self.network),
                'collected_at': datetime.now()
            }
            
            # Add signal analysis data if available
            if signal_result:
                record_data.update({
                    'signal_score': safe_decimal(signal_result.signal_score),
                    'volume_trend': signal_result.volume_trend,
                    'liquidity_trend': signal_result.liquidity_trend,
                    'momentum_indicator': safe_decimal(signal_result.momentum_indicator),
                    'activity_score': safe_decimal(signal_result.activity_score),
                    'volatility_score': safe_decimal(signal_result.volatility_score)
                })
            
            return record_data
            
        except Exception as e:
            self.logger.error(f"Error creating history record: {e}")
            return None
    
    async def _ensure_pool_exists(self, pool_info: Dict) -> bool:
        """
        Ensure pool exists in the Pools table, create if it doesn't.
        Also ensures required DEX and tokens exist.
        
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
            
            # Validate and ensure DEX exists before creating pool
            dex_id = pool_info.get('dex_id', '').strip()
            if not dex_id:
                self.logger.warning(f"Pool {pool_info['id']} has empty dex_id, skipping")
                return False
            
            # Ensure DEX exists
            await self._ensure_dex_exists(dex_id)
            
            # Ensure tokens exist if provided
            base_token_id = pool_info.get('base_token_id', '').strip()
            quote_token_id = pool_info.get('quote_token_id', '').strip()
            
            if base_token_id:
                await self._ensure_token_exists(base_token_id)
            if quote_token_id:
                await self._ensure_token_exists(quote_token_id)
            
            # Create new pool record with optimized storage
            pool = PoolModel(**pool_info)
            
            # Use optimized storage if available
            if hasattr(self.db_manager, 'store_pools_optimized'):
                await self.db_manager.store_pools_optimized([pool])
            else:
                # Fallback to standard method
                await self.db_manager.store_pool(pool)
            self.logger.debug(f"Created new pool: {pool_info['id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error ensuring pool exists for {pool_info.get('id')}: {e}")
            return False
    
    async def _ensure_dex_exists(self, dex_id: str) -> None:
        """
        Ensure DEX exists in the database, create if it doesn't.
        
        Args:
            dex_id: DEX identifier
        """
        try:
            from gecko_terminal_collector.database.models import DEX as DEXModel
            
            # Check if DEX already exists
            existing_dex = await self.db_manager.get_dex_by_id(dex_id)
            if existing_dex:
                return
            
            # Create new DEX record with minimal information
            dex_data = {
                'id': dex_id,
                'name': dex_id.replace('-', ' ').title(),  # Convert "pump-fun" to "Pump Fun"
                'network': self.network,
                'metadata_json': '{}'
            }
            
            dex = DEXModel(**dex_data)
            
            # Store DEX
            if hasattr(self.db_manager, 'store_dex'):
                await self.db_manager.store_dex(dex)
            else:
                # Fallback to generic store method
                with self.db_manager.connection.get_session() as session:
                    session.add(dex)
                    session.commit()
            
            self.logger.debug(f"Created new DEX: {dex_id}")
            
        except Exception as e:
            self.logger.error(f"Error ensuring DEX exists for {dex_id}: {e}")
            raise
    
    async def _ensure_token_exists(self, token_id: str) -> None:
        """
        Ensure token exists in the database, create if it doesn't.
        
        Args:
            token_id: Token identifier (usually network_address format)
        """
        try:
            from gecko_terminal_collector.database.models import Token as TokenModel
            
            # Check if token already exists
            existing_token = await self.db_manager.get_token_by_id(token_id)
            if existing_token:
                return
            
            # Parse token ID to extract network and address
            if '_' in token_id:
                network, address = token_id.split('_', 1)
            else:
                network = self.network
                address = token_id
            
            # Create new token record with minimal information
            token_data = {
                'id': token_id,
                'address': address,
                'network': network,
                'name': f"Token {address[:8]}...",  # Placeholder name
                'symbol': f"TKN{address[:4]}",  # Placeholder symbol
                'metadata_json': '{}'
            }
            
            token = TokenModel(**token_data)
            
            # Store token
            if hasattr(self.db_manager, 'store_token'):
                await self.db_manager.store_token(token)
            else:
                # Fallback to generic store method
                with self.db_manager.connection.get_session() as session:
                    session.add(token)
                    session.commit()
            
            self.logger.debug(f"Created new token: {token_id}")
            
        except Exception as e:
            self.logger.error(f"Error ensuring token exists for {token_id}: {e}")
            # Don't raise for tokens - they're optional
            pass
    
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
    
    async def _analyze_pool_signals(self, pool_data: Dict) -> Optional[SignalResult]:
        """
        Analyze pool data for trading signals.
        
        Args:
            pool_data: Current pool data from API
            
        Returns:
            SignalResult with analysis or None if analysis fails
        """
        try:
            pool_id = pool_data.get('id')
            if not pool_id:
                return None
            
            # Get historical data for the pool (last 24 hours)
            historical_data = await self._get_pool_historical_data(pool_id, hours=24)
            
            # Perform signal analysis
            signal_result = self.signal_analyzer.analyze_pool_signals(pool_data, historical_data)
            
            # Log significant signals
            if signal_result.signal_score >= self.signal_analyzer.min_signal_score:
                alert_message = self.signal_analyzer.generate_alert_message(pool_id, signal_result)
                self.logger.info(f"Strong signal detected: {alert_message}")
            
            return signal_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing signals for pool {pool_data.get('id')}: {e}")
            return None
    
    async def _get_pool_historical_data(self, pool_id: str, hours: int = 24) -> List[Dict]:
        """
        Get historical data for a pool from the new_pools_history table.
        
        Args:
            pool_id: Pool identifier
            hours: Number of hours to look back
            
        Returns:
            List of historical data dictionaries
        """
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Get historical records from database
            if hasattr(self.db_manager, 'get_pool_history'):
                return await self.db_manager.get_pool_history(pool_id, cutoff_time)
            else:
                # Fallback: return empty list if method not available
                self.logger.debug(f"No historical data method available for pool {pool_id}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting historical data for pool {pool_id}: {e}")
            return []
    
    async def _handle_auto_watchlist(self, pool_data: Dict, signal_result: SignalResult) -> None:
        """
        Handle automatic watchlist addition for pools with strong signals.
        
        Args:
            pool_data: Pool data from API
            signal_result: Signal analysis result
        """
        try:
            pool_id = pool_data.get('id')
            if not pool_id:
                return
            
            # Check if signal is strong enough for watchlist addition
            if not self.signal_analyzer.should_add_to_watchlist(signal_result):
                return
            
            # Check if pool is already in watchlist
            if hasattr(self.db_manager, 'is_pool_in_watchlist'):
                if await self.db_manager.is_pool_in_watchlist(pool_id):
                    self.logger.debug(f"Pool {pool_id} already in watchlist")
                    return
            
            # Extract token information for watchlist entry
            attributes = pool_data.get('attributes', {})
            
            # Create watchlist entry
            watchlist_data = {
                'pool_id': pool_id,
                'token_symbol': self._extract_token_symbol(pool_data),
                'token_name': attributes.get('name', f"Pool {pool_id[:8]}..."),
                'network_address': attributes.get('address', ''),
                'is_active': True,
                'metadata_json': {
                    'auto_added': True,
                    'signal_score': float(signal_result.signal_score),
                    'added_at': datetime.now().isoformat(),
                    'source': 'new_pools_signal_detection'
                }
            }
            
            # Add to watchlist
            if hasattr(self.db_manager, 'add_to_watchlist'):
                await self.db_manager.add_to_watchlist(watchlist_data)
                self.logger.info(f"Auto-added pool {pool_id} to watchlist (signal score: {signal_result.signal_score:.1f})")
            else:
                self.logger.warning("Watchlist functionality not available in database manager")
                
        except Exception as e:
            self.logger.error(f"Error handling auto-watchlist for pool {pool_data.get('id')}: {e}")
    
    def _extract_token_symbol(self, pool_data: Dict) -> str:
        """
        Extract a reasonable token symbol from pool data.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            Token symbol string
        """
        try:
            attributes = pool_data.get('attributes', {})
            
            # Try to extract from name
            name = attributes.get('name', '')
            if name and '/' in name:
                # Handle "TOKEN/SOL" format
                return name.split('/')[0].strip().upper()
            elif name:
                # Use first word of name
                return name.split()[0].upper()
            
            # Fallback to pool ID prefix
            pool_id = pool_data.get('id', '')
            if pool_id:
                return f"POOL{pool_id[:6].upper()}"
            
            return "UNKNOWN"
            
        except Exception as e:
            self.logger.error(f"Error extracting token symbol: {e}")
            return "UNKNOWN"
    
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

            print("pool_data: ", pool_data)

            if not isinstance(pool_data, dict):
                errors.append(f"Pool {i}: Expected dict, got {type(pool_data)}")
                continue
            
            # Check required fields
            if 'id' not in pool_data:
                errors.append(f"Pool {i}: Missing required 'id' field")
            
            """ if 'attributes' not in pool_data:
                errors.append(f"Pool {i}: Missing 'attributes' field")
                continue
            
            attributes = pool_data['attributes']
            if not isinstance(attributes, dict):
                errors.append(f"Pool {i}: 'attributes' must be a dict")
                continue """
            
            # Check for required fields in attributes
            #if 'base_token_id' not in attributes:
            #    errors.append(f"Pool {i}: Missing 'base_token_id' field in attributes")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )