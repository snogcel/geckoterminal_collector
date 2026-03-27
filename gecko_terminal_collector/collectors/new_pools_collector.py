"""
New pools collector for systematic collection and historical tracking with signal analysis.
"""

import asyncio
import logging
import decimal
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.database.models import Pool as PoolModel
from gecko_terminal_collector.database.postgresql_models import NewPoolsHistory
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer, SignalResult
from gecko_terminal_collector.utils.signal_alerting import setup_signal_logging, SignalAlerter

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
        
        # Configure Unicode handling for safe logging
        try:
            from gecko_terminal_collector.utils.unicode_utils import UnicodeHandler
            UnicodeHandler.configure_console_encoding()
        except Exception as e:
            self.logger.warning(f"Could not configure Unicode handling: {e}")
        
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
        
        # Log auto-watchlist configuration
        if self.auto_watchlist_enabled:
            threshold = signal_config.get('auto_watchlist_threshold', 75.0)
            self.logger.info(
                f"Auto-watchlist ENABLED for {network} - "
                f"threshold: {threshold:.1f}, "
                f"signal analysis: {self.signal_analysis_enabled}"
            )
        else:
            self.logger.info(f"Auto-watchlist DISABLED for {network}")
        
        # Get target dexes for filtering signal alerts
        self.target_dexes = []
        if hasattr(config, 'dexes') and hasattr(config.dexes, 'targets'):
            self.target_dexes = [dex.lower() for dex in config.dexes.targets]
            self.logger.info(f"Signal alerts will be filtered to target dexes: {self.target_dexes}")
        
        # Setup enhanced signal alerting
        alert_config = {
            'enable_file_alerts': signal_config.get('enable_file_alerts', True),
            'enable_sound_alerts': signal_config.get('enable_sound_alerts', False),
            'enable_desktop_notifications': signal_config.get('enable_desktop_notifications', False),
            'enable_webhook': signal_config.get('enable_webhook', False),
            'webhook_url': signal_config.get('webhook_url'),
            'min_signal_score': signal_config.get('min_signal_score', 60.0),
            'alerts_dir': signal_config.get('alerts_dir', 'alerts'),
            'use_colors': signal_config.get('use_colors', True),
            'use_emojis': signal_config.get('use_emojis', True)
        }
        self.signal_alerter = setup_signal_logging(self.logger, alert_config)
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return f"new_pools_{self.network}"
    
    def _get_max_pages(self) -> int:
        """
        Get maximum number of pages to fetch from config.
        
        Returns:
            Maximum number of pages (default: 10 for free tier)
        """
        try:
            new_pools_config = getattr(self.config, 'new_pools', None)
            if new_pools_config:
                # Check for network-specific setting first
                if hasattr(new_pools_config, 'networks'):
                    network_config = new_pools_config.networks.get(self.network, None)
                    if network_config and hasattr(network_config, 'max_pages') and network_config.max_pages is not None:
                        return network_config.max_pages
                
                # Fall back to global setting
                if hasattr(new_pools_config, 'max_pages') and new_pools_config.max_pages is not None:
                    return new_pools_config.max_pages
            
            # Default to 10 pages (free tier limit)
            return 10
        except Exception as e:
            self.logger.warning(f"Error getting max_pages config: {e}, using default of 10")
            return 10
    
    def _get_page_delay(self) -> float:
        """
        Get delay between page requests from config.
        
        Returns:
            Delay in seconds (default: 1.0)
        """
        try:
            new_pools_config = getattr(self.config, 'new_pools', None)
            if new_pools_config:
                # Check for network-specific setting first
                if hasattr(new_pools_config, 'networks'):
                    network_config = new_pools_config.networks.get(self.network, None)
                    if network_config and hasattr(network_config, 'page_delay') and network_config.page_delay is not None:
                        return network_config.page_delay
                
                # Fall back to global setting
                if hasattr(new_pools_config, 'page_delay') and new_pools_config.page_delay is not None:
                    return new_pools_config.page_delay
            
            # Default to 1 second delay
            return 1.0
        except Exception as e:
            self.logger.warning(f"Error getting page_delay config: {e}, using default of 1.0s")
            return 1.0
    
    async def collect(self) -> CollectionResult:
        """
        Collect new pools data for the specified network with pagination support.
        
        Returns:
            CollectionResult with collection status and statistics
        """
        start_time = datetime.now()
        errors = []
        pools_created = 0
        history_records = 0
        
        try:
            self.logger.info(f"Starting new pools collection for network: {self.network}")
            
            # Get pagination settings from config
            max_pages = self._get_max_pages()
            page_delay = self._get_page_delay()
            
            # Validate pagination settings
            if max_pages is None or max_pages < 1:
                self.logger.warning(f"Invalid max_pages value: {max_pages}, using default of 10")
                max_pages = 10
            if page_delay is None or page_delay < 0:
                self.logger.warning(f"Invalid page_delay value: {page_delay}, using default of 1.0")
                page_delay = 1.0
            
            self.logger.info(f"Pagination enabled: fetching up to {max_pages} pages with {page_delay}s delay")
            
            all_pools_data = []
            seen_pool_ids = set()  # Track pool IDs to avoid duplicates
            pages_fetched = 0
            
            # Fetch multiple pages
            for page in range(1, max_pages + 1):
                pages_fetched = page
                try:
                    self.logger.info(f"Fetching page {page}/{max_pages} for network: {self.network}")
                    
                    # Fetch new pools data using the SDK method with pagination
                    response = await self.make_api_request(
                        self.client.get_new_pools_by_network,
                        self.network,
                        page=page
                    )
                    
                    if response is None or (isinstance(response, dict) and 'data' not in response):
                        self.logger.warning(f"No data received on page {page}, stopping pagination")
                        break
                    
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
                    
                    if not pools_data or len(pools_data) == 0:
                        self.logger.info(f"Empty page {page}, stopping pagination")
                        break
                    
                    # Deduplicate pools by ID
                    page_new_pools = 0
                    for pool in pools_data:
                        pool_id = pool.get('id')
                        if pool_id and pool_id not in seen_pool_ids:
                            all_pools_data.append(pool)
                            seen_pool_ids.add(pool_id)
                            page_new_pools += 1
                    
                    self.logger.info(
                        f"Page {page}: Received {len(pools_data)} pools, "
                        f"{page_new_pools} new (after deduplication)"
                    )
                    
                    # Stop if we got fewer pools than expected (likely last page)
                    if len(pools_data) < 20:  # Typical page size is ~20 pools
                        self.logger.info(f"Page {page} has fewer pools than expected, likely last page")
                        break
                    
                    # Add delay between pages to respect rate limits (except after last page)
                    if page < max_pages:
                        await asyncio.sleep(page_delay)
                        
                except Exception as e:
                    error_msg = f"Error fetching page {page}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    # Continue to next page on error (could be transient)
                    if page < max_pages:
                        await asyncio.sleep(page_delay * 2)  # Longer delay after error
                    continue
            
            pools_data = all_pools_data
            self.logger.info(
                f"Pagination complete: collected {len(pools_data)} unique pools "
                f"across {pages_fetched} pages"
            )
            
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
                        if signal_result:
                            if self.auto_watchlist_enabled:
                                await self._handle_auto_watchlist(pool_data, signal_result)
                            else:
                                self.logger.debug(f"Auto-watchlist disabled for network {self.network}")
                    
                    # Always create historical record for predictive modeling
                    history_record = self._create_history_record(pool_data, signal_result)
                    if history_record:
                        await self._store_history_record(history_record)
                        history_records += 1
                        
                except Exception as e:
                    try:
                        from gecko_terminal_collector.utils.unicode_utils import UnicodeHandler
                        safe_pool_id = UnicodeHandler.safe_str(pool_data.get('id', 'unknown'))
                        error_msg = f"Error processing pool {safe_pool_id}: {str(e)}"
                    except Exception:
                        error_msg = f"Error processing pool (ID extraction failed): {str(e)}"
                    
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
                    'api_pools_received': len(pools_data),
                    'pages_fetched': pages_fetched,
                    'max_pages_configured': max_pages,
                    'unique_pools_collected': len(seen_pool_ids),
                    'duplicates_filtered': sum(1 for _ in all_pools_data) - len(seen_pool_ids) if all_pools_data else 0
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
            
            # Helper function to safely convert to Decimal
            def safe_decimal(value, default=None):
                if value is None or value == '':
                    return default
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError, decimal.InvalidOperation):
                    self.logger.warning(f"Failed to convert value to Decimal: {value}")
                    return default
            
            # Validate required fields
            pool_id = pool_data.get('id')
            if not pool_id:
                self.logger.warning("Pool data missing required 'id' field")
                return None
            
            # Ensure pool ID has proper network prefix
            pool_id = PoolIDUtils.normalize_pool_id(pool_id, self.network)
            
            # Validate DEX ID - this is required for foreign key constraint
            # Try to get from attributes first, then from relationships
            dex_id = get_field('dex_id', '').strip()
            if not dex_id:
                # Try to extract from relationships (new API format)
                relationships = pool_data.get('relationships', {})
                dex_data = relationships.get('dex', {}).get('data', {})
                dex_id = dex_data.get('id', '').strip()
            
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
            
            # Extract token IDs - try attributes first, then relationships
            base_token_id = get_field('base_token_id', '').strip()
            quote_token_id = get_field('quote_token_id', '').strip()
            
            if not base_token_id or not quote_token_id:
                # Try to extract from relationships (new API format)
                relationships = pool_data.get('relationships', {})
                if not base_token_id:
                    base_token_data = relationships.get('base_token', {}).get('data', {})
                    base_token_id = base_token_data.get('id', '').strip()
                if not quote_token_id:
                    quote_token_data = relationships.get('quote_token', {}).get('data', {})
                    quote_token_id = quote_token_data.get('id', '').strip()
            
            # Strip network prefix from token IDs for database storage
            # Token IDs come as "solana_ADDRESS" but database expects just "ADDRESS"
            if base_token_id and '_' in base_token_id:
                base_token_id = base_token_id.split('_', 1)[1]
            if quote_token_id and '_' in quote_token_id:
                quote_token_id = quote_token_id.split('_', 1)[1]
            
            return {
                'id': pool_id,
                'address': address,
                'name': name,
                'dex_id': dex_id,
                'base_token_id': base_token_id if base_token_id else None,
                'quote_token_id': quote_token_id if quote_token_id else None,
                'reserve_usd': safe_decimal(get_field('reserve_in_usd', 0), Decimal('0')),
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
            
            # Helper function to get nested field values
            def get_nested_field(parent_key, child_key, default=None):
                """Get value from nested dict like price_change_percentage.h1"""
                parent = get_field(parent_key, {})
                if isinstance(parent, dict):
                    return parent.get(child_key, default)
                return default
            
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
            
            # Helper function to cap extreme values to prevent database overflow
            def cap_value(value, max_val=999999.0):
                """Cap value to database field limits."""
                if value is None:
                    return None
                decimal_val = safe_decimal(value)
                if decimal_val is None:
                    return None
                # Cap to max value while preserving sign
                if decimal_val > Decimal(str(max_val)):
                    return Decimal(str(max_val))
                elif decimal_val < Decimal(str(-max_val)):
                    return Decimal(str(-max_val))
                return decimal_val
            
            # Base record data with capped extreme values
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
                # Cap FDV and market cap - these can be in billions, but we'll cap at reasonable limits
                # After migration, these will support NUMERIC(30,4), but cap at 999 billion for safety
                'fdv_usd': cap_value(get_field('fdv_usd'), 999999999999.0),
                'market_cap_usd': cap_value(get_field('market_cap_usd'), 999999999999.0),
                # Cap price change percentages - extreme values indicate data issues or pump/dumps
                # After migration, these will support NUMERIC(15,4), cap at 99,999%
                # Extract from nested structure: price_change_percentage.h1
                'price_change_percentage_h1': cap_value(get_nested_field('price_change_percentage', 'h1'), 99999.0),
                'price_change_percentage_h24': cap_value(get_nested_field('price_change_percentage', 'h24'), 99999.0),
                # Extract from nested structure: transactions.h1.buys
                'transactions_h1_buys': safe_int(get_nested_field('transactions', 'h1', {}).get('buys') if get_nested_field('transactions', 'h1') else None),
                'transactions_h1_sells': safe_int(get_nested_field('transactions', 'h1', {}).get('sells') if get_nested_field('transactions', 'h1') else None),
                'transactions_h24_buys': safe_int(get_nested_field('transactions', 'h24', {}).get('buys') if get_nested_field('transactions', 'h24') else None),
                'transactions_h24_sells': safe_int(get_nested_field('transactions', 'h24', {}).get('sells') if get_nested_field('transactions', 'h24') else None),
                # Extract from nested structure: volume_usd.h24
                'volume_usd_h24': safe_decimal(get_nested_field('volume_usd', 'h24')),
                'dex_id': self._extract_dex_id(pool_data),
                'base_token_id': self._extract_base_token_id(pool_data),
                'quote_token_id': self._extract_quote_token_id(pool_data),
                'network_id': get_field('network_id', self.network),
                'collected_at': datetime.now()
            }
            
            # Add signal analysis data if available
            if signal_result:
                signals = signal_result.signals
                record_data.update({
                    'signal_score': cap_value(signal_result.signal_score, 100.0),
                    'volume_trend': signal_result.volume_trend,
                    'liquidity_trend': signal_result.liquidity_trend,
                    'momentum_indicator': cap_value(signal_result.momentum_indicator, 99999.0),
                    'activity_score': cap_value(signal_result.activity_score, 100.0),
                    'volatility_score': cap_value(signal_result.volatility_score, 100.0),
                    # Extended signal fields
                    'rf_score': cap_value(signals.get('rf_score'), 100.0) if signals.get('rf_score') is not None else None,
                    'rf_tier': signals.get('rf_tier'),
                    'fdv_liq_ratio': cap_value(signals.get('fdv_liq_ratio'), 99999.0) if signals.get('fdv_liq_ratio') is not None else None,
                    'vol_velocity': cap_value(signals.get('vol_velocity'), 99999.0) if signals.get('vol_velocity') is not None else None,
                    'sell_authentic': signals.get('sell_authentic'),
                    'buy_ratio_1h': cap_value(signals.get('buy_ratio_1h'), 1.0) if signals.get('buy_ratio_1h') is not None else None,
                    'signals_json': __import__('json').dumps({
                        k: v for k, v in signals.items()
                        if k not in ('rf_score', 'rf_tier', 'rf_tier_label', 'fdv_liq_ratio',
                                     'vol_velocity', 'sell_authentic', 'buy_ratio_1h')
                    }) if signals else None,
                })
            
            # Filter out None values to let SQLAlchemy use column defaults (NULL)
            # This prevents "conversion from NoneType to Decimal" errors
            record_data = {k: v for k, v in record_data.items() if v is not None}
            
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
                self.logger.debug(f"Ensuring base token exists: {base_token_id}")
                await self._ensure_token_exists(base_token_id)
            if quote_token_id:
                self.logger.debug(f"Ensuring quote token exists: {quote_token_id}")
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
    
    async def _ensure_token_exists(self, token_address: str) -> None:
        """
        Ensure token exists in the database, create if it doesn't.
        
        Args:
            token_address: Token address (without network prefix)
        """
        try:
            from gecko_terminal_collector.database.models import Token as TokenModel
            
            # Check if token already exists
            existing_token = await self.db_manager.get_token_by_id(token_address)
            if existing_token:
                return
            
            # Token ID in database is just the address (no network prefix)
            # Network is stored separately
            address = token_address
            network = self.network
            
            # Create new token record with minimal information
            token_data = {
                'id': address,  # Just the address, no network prefix
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
            
            self.logger.debug(f"Created new token: {address}")
            
        except Exception as e:
            self.logger.error(f"Error ensuring token exists for {token_address}: {e}")
            # Raise the error so pool creation knows tokens failed
            raise
    
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
    
    def _extract_dex_id(self, pool_data: Dict) -> Optional[str]:
        """
        Extract dex_id from pool data (handles both old and new API formats).
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            DEX ID string or None if not found
        """
        # Try attributes first (old format)
        attributes = pool_data.get('attributes', {})
        dex_id = attributes.get('dex_id', pool_data.get('dex_id', '')).strip()
        
        # If not found, try relationships (new API format)
        if not dex_id:
            relationships = pool_data.get('relationships', {})
            dex_data = relationships.get('dex', {}).get('data', {})
            dex_id = dex_data.get('id', '').strip()
        
        return dex_id if dex_id else None
    
    def _extract_base_token_id(self, pool_data: Dict) -> Optional[str]:
        """
        Extract base_token_id from pool data (handles both old and new API formats).
        Returns address without network prefix for database storage.
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            Base token address (without network prefix) or None if not found
        """
        # Try attributes first (old format)
        attributes = pool_data.get('attributes', {})
        token_id = attributes.get('base_token_id', pool_data.get('base_token_id', '')).strip()
        
        # If not found, try relationships (new API format)
        if not token_id:
            relationships = pool_data.get('relationships', {})
            token_data = relationships.get('base_token', {}).get('data', {})
            token_id = token_data.get('id', '').strip()
        
        # Strip network prefix (e.g., "solana_ADDRESS" -> "ADDRESS")
        if token_id and '_' in token_id:
            token_id = token_id.split('_', 1)[1]
        
        return token_id if token_id else None
    
    def _extract_quote_token_id(self, pool_data: Dict) -> Optional[str]:
        """
        Extract quote_token_id from pool data (handles both old and new API formats).
        Returns address without network prefix for database storage.
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            Quote token address (without network prefix) or None if not found
        """
        # Try attributes first (old format)
        attributes = pool_data.get('attributes', {})
        token_id = attributes.get('quote_token_id', pool_data.get('quote_token_id', '')).strip()
        
        # If not found, try relationships (new API format)
        if not token_id:
            relationships = pool_data.get('relationships', {})
            token_data = relationships.get('quote_token', {}).get('data', {})
            token_id = token_data.get('id', '').strip()
        
        # Strip network prefix (e.g., "solana_ADDRESS" -> "ADDRESS")
        if token_id and '_' in token_id:
            token_id = token_id.split('_', 1)[1]
        
        return token_id if token_id else None
    
    def _get_pool_dex_id(self, pool_data: Dict) -> Optional[str]:
        """
        Extract dex_id from pool data (legacy method, calls _extract_dex_id).
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            DEX ID string or None if not found
        """
        return self._extract_dex_id(pool_data)
    
    def _flatten_pool_data_for_analysis(self, pool_data: Dict) -> Dict:
        """
        Flatten nested API response fields for signal analyzer.
        
        The signal analyzer expects flat fields like 'volume_usd_h24',
        but the API returns nested structures like volume_usd.h24.
        
        Args:
            pool_data: Raw pool data from API with nested structure
            
        Returns:
            Flattened dictionary with fields the analyzer expects
        """
        attributes = pool_data.get('attributes', {})
        
        # Helper to get nested values
        def get_nested(parent_key, child_key, default=None):
            parent = attributes.get(parent_key, {})
            if isinstance(parent, dict):
                return parent.get(child_key, default)
            return default
        
        # Create flattened structure
        flattened = {
            # Copy basic fields
            'id': pool_data.get('id'),
            'type': pool_data.get('type'),
            'name': attributes.get('name'),
            'address': attributes.get('address'),
            'reserve_in_usd': attributes.get('reserve_in_usd'),
            'fdv_usd': attributes.get('fdv_usd'),
            'market_cap_usd': attributes.get('market_cap_usd'),
            'pool_created_at': attributes.get('pool_created_at'),
            'collected_at': datetime.now(timezone.utc).isoformat(),

            # Flatten price change percentages
            'price_change_percentage_h1': get_nested('price_change_percentage', 'h1'),
            'price_change_percentage_h24': get_nested('price_change_percentage', 'h24'),
            
            # Flatten transactions
            'transactions_h1_buys': get_nested('transactions', 'h1', {}).get('buys') if get_nested('transactions', 'h1') else None,
            'transactions_h1_sells': get_nested('transactions', 'h1', {}).get('sells') if get_nested('transactions', 'h1') else None,
            'transactions_h24_buys': get_nested('transactions', 'h24', {}).get('buys') if get_nested('transactions', 'h24') else None,
            'transactions_h24_sells': get_nested('transactions', 'h24', {}).get('sells') if get_nested('transactions', 'h24') else None,
            
            # Flatten volume
            'volume_usd_h24': get_nested('volume_usd', 'h24'),
        }
        
        return flattened
    
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
            
            # Flatten nested fields for signal analyzer
            flattened_data = self._flatten_pool_data_for_analysis(pool_data)
            
            # Get historical data for the pool (last 24 hours)
            historical_data = await self._get_pool_historical_data(pool_id, hours=24)
            
            # Perform signal analysis with flattened data
            signal_result = self.signal_analyzer.analyze_pool_signals(flattened_data, historical_data)
            
            # Log significant signals (only if signal detection is enabled and for target dexes)
            if (self.signal_analysis_enabled and 
                signal_result.signal_score >= self.signal_analyzer.min_signal_score):
                # Check if this pool's dex is in our target list
                pool_dex_id = self._get_pool_dex_id(pool_data)
                should_alert = not self.target_dexes or (pool_dex_id and pool_dex_id.lower() in self.target_dexes)
                
                if should_alert:
                    alert_message = self.signal_analyzer.generate_alert_message(pool_id, signal_result)
                    
                    # Use custom TRADE_SIGNAL log level for high visibility
                    self.logger.trade_signal(f"STRONG SIGNAL DETECTED: {alert_message}")
                    
                    # Send multi-channel alerts (file, sound, notification, webhook)
                    signal_data = {
                        'signal_score': signal_result.signal_score,
                        'volume_trend': signal_result.volume_trend,
                        'liquidity_trend': signal_result.liquidity_trend,
                        'momentum_indicator': signal_result.momentum_indicator,
                        'activity_score': signal_result.activity_score,
                        'volatility_score': signal_result.volatility_score,
                        'dex_id': pool_dex_id,
                        'network': self.network
                    }
                    self.signal_alerter.alert(pool_id, signal_data, alert_message)
            
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
                self.logger.debug("Auto-watchlist: No pool_id found in pool_data")
                return
            
            # Get the threshold for logging
            threshold = self.signal_analyzer.config.get('auto_watchlist_threshold', 65.0)
            
            # Check if signal is strong enough for watchlist addition
            if not self.signal_analyzer.should_add_to_watchlist(signal_result):
                self.logger.debug(
                    f"Auto-watchlist: Pool {pool_id} signal score {signal_result.signal_score:.1f} "
                    f"below threshold {threshold:.1f} - not adding to watchlist"
                )
                return
            
            # Check if pool's DEX is in our target list (same logic as signal alerts)
            pool_dex_id = self._get_pool_dex_id(pool_data)
            should_add = not self.target_dexes or (pool_dex_id and pool_dex_id.lower() in self.target_dexes)
            
            if not should_add:
                self.logger.debug(
                    f"Auto-watchlist: Pool {pool_id} DEX '{pool_dex_id}' not in target dexes {self.target_dexes} - skipping"
                )
                return
            
            self.logger.info(
                f"Auto-watchlist: Pool {pool_id} has strong signal ({signal_result.signal_score:.1f} >= {threshold:.1f}) "
                f"and is from target DEX '{pool_dex_id}' - checking if already in watchlist..."
            )
            
            # Check if pool is already in watchlist
            if hasattr(self.db_manager, 'is_pool_in_watchlist'):
                is_in_watchlist = await self.db_manager.is_pool_in_watchlist(pool_id)
                if is_in_watchlist:
                    self.logger.info(f"Auto-watchlist: Pool {pool_id} already in watchlist - skipping")
                    return
                else:
                    self.logger.info(f"Auto-watchlist: Pool {pool_id} not in watchlist - proceeding with addition")
            else:
                self.logger.warning("Auto-watchlist: is_pool_in_watchlist method not available - proceeding without duplicate check")
            
            # Extract token information for watchlist entry
            # Handle both nested (attributes) and flat data formats
            attributes = pool_data.get('attributes', {})
            
            # Helper function to get field from either attributes or root level
            def get_field(field_name, default=''):
                return attributes.get(field_name, pool_data.get(field_name, default))
            
            # Get pool name and address
            pool_name = get_field('name', f"Pool {pool_id[:8]}...")
            pool_address = get_field('address', '')
            
            # Extract token symbol from pool name
            token_symbol = self._extract_token_symbol_from_name(pool_name, pool_id)
            
            # Create watchlist entry
            watchlist_data = {
                'pool_id': pool_id,
                'token_symbol': token_symbol,
                'token_name': pool_name,
                'network_address': pool_address,
                'is_active': True,
                'metadata_json': {
                    'auto_added': True,
                    'signal_score': float(signal_result.signal_score),
                    'added_at': datetime.now().isoformat(),
                    'source': 'new_pools_signal_detection'
                }
            }
            
            self.logger.info(f"Auto-watchlist: Adding pool {pool_id} to watchlist with data: {watchlist_data}")
            
            # Add to watchlist
            if hasattr(self.db_manager, 'add_to_watchlist'):
                await self.db_manager.add_to_watchlist(watchlist_data)
                self.logger.info(
                    f"✅ Auto-watchlist: Successfully added pool {pool_id} to watchlist "
                    f"(signal score: {signal_result.signal_score:.1f})"
                )
            else:
                self.logger.warning("Auto-watchlist: add_to_watchlist method not available in database manager")
                
        except Exception as e:
            self.logger.error(f"Auto-watchlist: Error handling auto-watchlist for pool {pool_data.get('id')}: {e}")
            import traceback
            self.logger.error(f"Auto-watchlist: Traceback: {traceback.format_exc()}")
    
    def _extract_token_symbol(self, pool_data: Dict) -> str:
        """
        Extract a reasonable token symbol from pool data.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            Token symbol string
        """
        try:
            # Handle both nested (attributes) and flat data formats
            attributes = pool_data.get('attributes', {})
            name = attributes.get('name', pool_data.get('name', ''))
            pool_id = pool_data.get('id', '')
            
            return self._extract_token_symbol_from_name(name, pool_id)
            
        except Exception as e:
            self.logger.error(f"Error extracting token symbol: {e}")
            return "UNKNOWN"
    
    def _extract_token_symbol_from_name(self, name: str, pool_id: str = '') -> str:
        """
        Extract token symbol from pool name.
        
        Args:
            name: Pool name (e.g., "TOKEN / SOL" or "TOKEN/SOL")
            pool_id: Pool ID for fallback
            
        Returns:
            Token symbol string
        """
        try:
            if not name:
                # Fallback to pool ID prefix if no name
                if pool_id:
                    return f"POOL{pool_id.split('_')[-1][:6].upper()}"
                return "UNKNOWN"
            
            # Handle "TOKEN / SOL" or "TOKEN/SOL" format
            if '/' in name:
                token_part = name.split('/')[0].strip()
                # Don't uppercase if it has mixed case (preserve branding)
                return token_part if token_part else "UNKNOWN"
            
            # Handle space-separated format
            if ' ' in name:
                # Use first word
                token_part = name.split()[0].strip()
                return token_part if token_part else "UNKNOWN"
            
            # Single word name
            return name.strip() if name.strip() else "UNKNOWN"
            
        except Exception as e:
            self.logger.error(f"Error extracting token symbol from name '{name}': {e}")
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

            # Safe logging instead of print to avoid Unicode encoding issues
            # Only log detailed info in debug mode to avoid performance impact
            try:
                from gecko_terminal_collector.utils.unicode_utils import UnicodeHandler
                safe_info = UnicodeHandler.safe_format_pool_info(pool_data)
                self.logger.debug(f"Processing: {safe_info}")
            except Exception as debug_error:
                # Fallback if Unicode handling fails
                pool_id = str(pool_data.get('id', 'unknown'))[:20]
                self.logger.debug(f"Processing pool: {pool_id}...")

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