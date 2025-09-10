"""
Real-time OHLCV data collector.

This module provides functionality to collect OHLCV (Open, High, Low, Close, Volume)
data for watchlist tokens with configurable timeframes, data validation, duplicate
prevention, and gap detection algorithms.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import (
    CollectionResult, OHLCVRecord, ValidationResult, Gap, ContinuityReport
)
from gecko_terminal_collector.utils.metadata import MetadataTracker

logger = logging.getLogger(__name__)


class OHLCVCollector(BaseDataCollector):
    """
    Collects real-time OHLCV data for watchlist tokens.
    
    This collector retrieves OHLCV data using configurable timeframes,
    implements data validation and duplicate prevention logic, and provides
    data continuity verification and gap detection algorithms.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False
    ):
        """
        Initialize the OHLCV collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        self.network = config.dexes['network'] if isinstance(config.dexes, dict) else config.dexes.network
        self.supported_timeframes = config.timeframes['supported'] if isinstance(config.timeframes, dict) else config.timeframes.supported
        self.default_timeframe = config.timeframes['ohlcv_default'] if isinstance(config.timeframes, dict) else config.timeframes.ohlcv_default
        
        # OHLCV collection settings
        self.limit = getattr(config, 'ohlcv_limit', 1000)  # Max records per API call
        self.currency = getattr(config, 'ohlcv_currency', 'usd')
        self.token = getattr(config, 'ohlcv_token', 'base')
        
        # Track errors during collection
        self._collection_errors = []
        
        # Data quality thresholds
        self.min_data_quality_score = getattr(config, 'min_data_quality_score', 0.8)
        self.max_gap_hours = getattr(config, 'max_gap_hours', 24)
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "ohlcv_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect OHLCV data for watchlist tokens.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        self._collection_errors = []  # Reset error tracking
        
        try:
            # Get active watchlist pool IDs
            logger.info("Retrieving active watchlist pools for OHLCV collection")
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            if not watchlist_pools:
                logger.info("No active watchlist pools found")
                return self.create_success_result(0, start_time)
            
            logger.info(f"Found {len(watchlist_pools)} watchlist pools for OHLCV collection")
            
            # Collect OHLCV data for each pool and timeframe
            for pool_id in watchlist_pools:
                try:
                    pool_records = await self._collect_pool_ohlcv_data(pool_id)
                    records_collected += pool_records
                    
                    # Verify data continuity for this pool
                    await self._verify_data_continuity(pool_id)
                    
                except Exception as e:
                    error_msg = f"Error collecting OHLCV data for pool {pool_id}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
            
            logger.info(
                f"OHLCV collection completed: {records_collected} records collected "
                f"for {len(watchlist_pools)} pools"
            )
            
            # Combine pool-level errors with individual API call errors
            all_errors = errors + self._collection_errors
            
            # Create result with any errors encountered
            if all_errors:
                return CollectionResult(
                    success=True,  # Partial success
                    records_collected=records_collected,
                    errors=all_errors,
                    collection_time=start_time,
                    collector_type=self.get_collection_key()
                )
            
            return self.create_success_result(records_collected, start_time)
            
        except Exception as e:
            error_msg = f"Error in OHLCV collection: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def collect_for_pool(self, pool_id: str, timeframe: Optional[str] = None) -> CollectionResult:
        """
        Collect OHLCV data for a specific pool and timeframe.
        
        Args:
            pool_id: Pool identifier to collect data for
            timeframe: Specific timeframe to collect (optional, uses default if not provided)
            
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        
        try:
            # Use provided timeframe or default
            target_timeframe = timeframe or self.default_timeframe
            
            if target_timeframe not in self.supported_timeframes:
                error_msg = f"Unsupported timeframe: {target_timeframe}. Supported: {self.supported_timeframes}"
                logger.error(error_msg)
                return self.create_failure_result([error_msg], 0, start_time)
            
            logger.info(f"Collecting OHLCV data for pool {pool_id}, timeframe {target_timeframe}")
            
            try:
                # Extract pool address from pool_id (remove network prefix if present)
                pool_address = pool_id
                if pool_id.startswith(f"{self.network}_"):
                    pool_address = pool_id[len(f"{self.network}_"):]
                
                # Get OHLCV data from API
                response = await self.client.get_ohlcv_data(
                    network=self.network,
                    pool_address=pool_address,
                    timeframe=self._convert_timeframe_to_api_format(target_timeframe),
                    limit=self.limit,
                    currency=self.currency,
                    token=self.token
                )
                
                # Parse and validate OHLCV data
                ohlcv_records = self._parse_ohlcv_response(response, pool_id, target_timeframe)
                
                if ohlcv_records:
                    # Validate data before storage
                    validation_result = await self._validate_ohlcv_data(ohlcv_records)
                    
                    if validation_result.is_valid:
                        # Store OHLCV data with duplicate prevention
                        stored_count = await self.db_manager.store_ohlcv_data(ohlcv_records)
                        records_collected = stored_count
                        
                        logger.info(
                            f"Stored {stored_count} OHLCV records for pool {pool_id}, "
                            f"timeframe {target_timeframe}"
                        )
                        
                        # Verify data continuity for this pool
                        await self._verify_data_continuity(pool_id)
                        
                    else:
                        error_msg = (
                            f"OHLCV data validation failed for pool {pool_id}, "
                            f"timeframe {target_timeframe}: {validation_result.errors}"
                        )
                        logger.warning(error_msg)
                        errors.append(error_msg)
                else:
                    logger.info(f"No OHLCV data returned for pool {pool_id}, timeframe {target_timeframe}")
                
            except Exception as e:
                error_msg = f"Error collecting OHLCV data for pool {pool_id}, timeframe {target_timeframe}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            if records_collected > 0:
                return self.create_success_result(records_collected, start_time)
            else:
                return self.create_failure_result(errors or ["No data collected"], records_collected, start_time)
            
        except Exception as e:
            error_msg = f"Error in single pool OHLCV collection: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def _collect_pool_ohlcv_data(self, pool_id: str) -> int:
        """
        Enhanced OHLCV data collection with bulk storage optimization.
        
        Args:
            pool_id: Pool identifier to collect data for
            
        Returns:
            Number of OHLCV records collected for this pool
        """
        total_records = 0
        all_records_for_pool = []  # Collect all records for bulk storage
        collection_metadata = {
            'pool_id': pool_id,
            'timeframes_processed': [],
            'timeframes_failed': [],
            'api_calls_made': 0,
            'parsing_errors': 0,
            'validation_errors': 0
        }
        
        logger.debug(f"Starting enhanced OHLCV collection for pool {pool_id}")
        
        for timeframe in self.supported_timeframes:
            timeframe_start_time = datetime.now()
            
            try:
                logger.debug(f"Collecting OHLCV data for pool {pool_id}, timeframe {timeframe}")
                
                # Extract pool address from pool_id (remove network prefix if present)
                pool_address = pool_id
                if pool_id.startswith(f"{self.network}_"):
                    pool_address = pool_id[len(f"{self.network}_"):]
                
                # Get OHLCV data from API with enhanced error handling
                try:
                    response = await self.client.get_ohlcv_data(
                        network=self.network,
                        pool_address=pool_address,
                        timeframe=self._convert_timeframe_to_api_format(timeframe),
                        limit=self.limit,
                        currency=self.currency,
                        token=self.token
                    )
                    collection_metadata['api_calls_made'] += 1
                    
                except Exception as api_error:
                    error_msg = f"API call failed for pool {pool_id}, timeframe {timeframe}: {api_error}"
                    logger.warning(error_msg)
                    self._collection_errors.append(error_msg)
                    collection_metadata['timeframes_failed'].append(timeframe)
                    continue
                
                # Parse OHLCV data with enhanced error tracking
                parsing_errors_before = len(self._collection_errors)
                ohlcv_records = self._parse_ohlcv_response(response, pool_id, timeframe)
                parsing_errors_after = len(self._collection_errors)
                collection_metadata['parsing_errors'] += (parsing_errors_after - parsing_errors_before)
                
                if ohlcv_records:
                    logger.debug(f"Parsed {len(ohlcv_records)} OHLCV records for pool {pool_id}, timeframe {timeframe}")
                    
                    # Enhanced validation with detailed error tracking
                    validation_result = await self._validate_ohlcv_data(ohlcv_records)
                    
                    if validation_result.is_valid:
                        # Add records to bulk collection instead of immediate storage
                        all_records_for_pool.extend(ohlcv_records)
                        collection_metadata['timeframes_processed'].append(timeframe)
                        
                        logger.debug(
                            f"Added {len(ohlcv_records)} validated OHLCV records for pool {pool_id}, "
                            f"timeframe {timeframe} to bulk collection"
                        )
                    else:
                        collection_metadata['validation_errors'] += len(validation_result.errors)
                        error_msg = (
                            f"OHLCV data validation failed for pool {pool_id}, "
                            f"timeframe {timeframe}: {len(validation_result.errors)} errors, "
                            f"{len(validation_result.warnings)} warnings"
                        )
                        logger.warning(error_msg)
                        self._collection_errors.append(error_msg)
                        collection_metadata['timeframes_failed'].append(timeframe)
                        
                        # Log first few validation errors for debugging
                        for error in validation_result.errors[:3]:
                            logger.debug(f"Validation error: {error}")
                else:
                    logger.debug(f"No OHLCV data returned for pool {pool_id}, timeframe {timeframe}")
                    collection_metadata['timeframes_failed'].append(timeframe)
                
                # Log timeframe processing time
                timeframe_duration = (datetime.now() - timeframe_start_time).total_seconds()
                logger.debug(f"Processed timeframe {timeframe} for pool {pool_id} in {timeframe_duration:.2f}s")
                
            except Exception as e:
                error_msg = f"Unexpected error collecting OHLCV data for pool {pool_id}, timeframe {timeframe}: {e}"
                logger.error(error_msg, exc_info=True)
                self._collection_errors.append(error_msg)
                collection_metadata['timeframes_failed'].append(timeframe)
                continue
        
        # Bulk storage optimization - store all records for the pool at once
        if all_records_for_pool:
            try:
                logger.info(f"Performing bulk storage of {len(all_records_for_pool)} OHLCV records for pool {pool_id}")
                
                # Final validation of the complete dataset
                final_validation = await self._validate_ohlcv_data(all_records_for_pool)
                
                if final_validation.is_valid:
                    # Use enhanced bulk storage
                    stored_count = await self._bulk_store_ohlcv_data(all_records_for_pool)
                    total_records = stored_count
                    
                    logger.info(
                        f"Successfully bulk stored {stored_count} OHLCV records for pool {pool_id} "
                        f"across {len(collection_metadata['timeframes_processed'])} timeframes"
                    )
                else:
                    logger.error(
                        f"Final validation failed for pool {pool_id}: "
                        f"{len(final_validation.errors)} errors, {len(final_validation.warnings)} warnings"
                    )
                    # Store valid records only
                    valid_records = [r for r in all_records_for_pool if self._is_record_valid(r)]
                    if valid_records:
                        stored_count = await self._bulk_store_ohlcv_data(valid_records)
                        total_records = stored_count
                        logger.info(f"Stored {stored_count} valid records out of {len(all_records_for_pool)} for pool {pool_id}")
                
            except Exception as storage_error:
                error_msg = f"Bulk storage failed for pool {pool_id}: {storage_error}"
                logger.error(error_msg, exc_info=True)
                self._collection_errors.append(error_msg)
        
        # Log collection summary
        logger.info(
            f"OHLCV collection completed for pool {pool_id}: "
            f"{total_records} records stored, "
            f"{len(collection_metadata['timeframes_processed'])} timeframes succeeded, "
            f"{len(collection_metadata['timeframes_failed'])} timeframes failed, "
            f"{collection_metadata['api_calls_made']} API calls made"
        )
        
        return total_records
    
    def _parse_ohlcv_response(
        self, 
        response, 
        pool_id: str, 
        timeframe: str
    ) -> List[OHLCVRecord]:
        """
        Enhanced OHLCV API response parser with better error handling and data quality validation.
        
        Args:
            response: API response from get_ohlcv_data (can be Dict or DataFrame)
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            List of OHLCVRecord objects
        """
        records = []
        parsing_errors = []
        
        try:
            # Handle pandas DataFrame response (from geckoterminal-py SDK)
            if hasattr(response, 'iterrows'):  # It's a DataFrame
                logger.debug(f"Parsing DataFrame OHLCV response for pool {pool_id}")
                import pandas as pd
                df = response
                
                if df.empty:
                    logger.info(f"Empty DataFrame received for pool {pool_id}")
                    return records
                
                # Validate DataFrame structure
                required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume_usd']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    logger.error(f"Missing required columns in DataFrame for pool {pool_id}: {missing_columns}")
                    return records
                
                for idx, row in df.iterrows():
                    try:
                        # Enhanced data validation before conversion
                        if pd.isna(row['timestamp']) or pd.isna(row['open']) or pd.isna(row['high']) or pd.isna(row['low']) or pd.isna(row['close']):
                            logger.warning(f"Skipping row {idx} with null values for pool {pool_id}")
                            continue
                        
                        # Convert DataFrame row to OHLCV entry format with proper type conversion
                        ohlcv_data = [
                            self._safe_int_conversion(row['timestamp'], f"timestamp at row {idx}"),
                            self._safe_float_conversion(row['open'], f"open price at row {idx}"),
                            self._safe_float_conversion(row['high'], f"high price at row {idx}"),
                            self._safe_float_conversion(row['low'], f"low price at row {idx}"),
                            self._safe_float_conversion(row['close'], f"close price at row {idx}"),
                            self._safe_float_conversion(row['volume_usd'], f"volume at row {idx}")
                        ]
                        
                        # Skip if any conversion failed
                        if None in ohlcv_data:
                            continue
                        
                        record = self._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
                        if record:
                            records.append(record)
                    except Exception as e:
                        error_msg = f"Error parsing OHLCV DataFrame row {idx} for pool {pool_id}: {e}"
                        logger.warning(error_msg)
                        parsing_errors.append(error_msg)
                        continue
                        
            # Handle dictionary response (raw API format)
            elif isinstance(response, dict):
                logger.debug(f"Parsing dictionary OHLCV response for pool {pool_id}")
                
                # Enhanced response structure validation
                if "data" not in response:
                    logger.error(f"Missing 'data' key in OHLCV response for pool {pool_id}")
                    return records
                
                data = response.get("data", {})
                if not isinstance(data, dict):
                    logger.error(f"Invalid 'data' structure in OHLCV response for pool {pool_id}: expected dict, got {type(data)}")
                    return records
                
                attributes = data.get("attributes", {})
                if not isinstance(attributes, dict):
                    logger.error(f"Invalid 'attributes' structure in OHLCV response for pool {pool_id}: expected dict, got {type(attributes)}")
                    return records
                
                ohlcv_list = attributes.get("ohlcv_list", [])
                
                if not isinstance(ohlcv_list, list):
                    logger.error(f"Invalid 'ohlcv_list' structure in OHLCV response for pool {pool_id}: expected list, got {type(ohlcv_list)}")
                    return records
                
                if not ohlcv_list:
                    logger.info(f"Empty OHLCV list received for pool {pool_id}")
                    return records
                
                logger.debug(f"Processing {len(ohlcv_list)} OHLCV entries for pool {pool_id}")
                
                for idx, ohlcv_data in enumerate(ohlcv_list):
                    try:
                        # Enhanced entry validation
                        if not isinstance(ohlcv_data, list):
                            logger.warning(f"Skipping invalid OHLCV entry {idx} for pool {pool_id}: expected list, got {type(ohlcv_data)}")
                            continue
                        
                        if len(ohlcv_data) < 6:
                            logger.warning(f"Skipping incomplete OHLCV entry {idx} for pool {pool_id}: expected 6 elements, got {len(ohlcv_data)}")
                            continue
                        
                        record = self._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
                        if record:
                            records.append(record)
                    except Exception as e:
                        error_msg = f"Error parsing OHLCV entry {idx} for pool {pool_id}: {e}"
                        logger.warning(error_msg)
                        parsing_errors.append(error_msg)
                        continue
            
            # Handle list response (direct OHLCV list)
            elif isinstance(response, list):
                logger.debug(f"Parsing list OHLCV response for pool {pool_id}")
                
                if not response:
                    logger.info(f"Empty OHLCV list received for pool {pool_id}")
                    return records
                
                for idx, ohlcv_data in enumerate(response):
                    try:
                        record = self._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
                        if record:
                            records.append(record)
                    except Exception as e:
                        error_msg = f"Error parsing OHLCV list entry {idx} for pool {pool_id}: {e}"
                        logger.warning(error_msg)
                        parsing_errors.append(error_msg)
                        continue
            else:
                logger.error(f"Unsupported response type for pool {pool_id}: {type(response)}")
                return records
            
            # Log parsing summary
            if records:
                logger.info(f"Successfully parsed {len(records)} OHLCV records for pool {pool_id}")
            
            if parsing_errors:
                logger.warning(f"Encountered {len(parsing_errors)} parsing errors for pool {pool_id}")
                # Store parsing errors for later analysis
                self._collection_errors.extend(parsing_errors[:5])  # Limit to first 5 errors
            
        except Exception as e:
            error_msg = f"Critical error parsing OHLCV response for pool {pool_id}: {e}"
            logger.error(error_msg, exc_info=True)
            self._collection_errors.append(error_msg)
        
        return records
    
    def _safe_int_conversion(self, value, context: str) -> Optional[int]:
        """
        Safely convert value to integer with proper error handling.
        
        Args:
            value: Value to convert
            context: Context for error reporting
            
        Returns:
            Converted integer or None if conversion fails
        """
        try:
            if value is None:
                return None
            return int(float(value))  # Handle string numbers and floats
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Failed to convert {context} to int: {value} ({e})")
            return None
    
    def _safe_float_conversion(self, value, context: str) -> Optional[float]:
        """
        Safely convert value to float with proper error handling.
        
        Args:
            value: Value to convert
            context: Context for error reporting
            
        Returns:
            Converted float or None if conversion fails
        """
        try:
            if value is None:
                return None
            
            converted = float(value)
            
            # Check for infinity and NaN
            if not (converted != float('inf') and converted != float('-inf') and converted == converted):
                logger.warning(f"Invalid float value for {context}: {value} (inf or NaN)")
                return None
                
            return converted
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Failed to convert {context} to float: {value} ({e})")
            return None
    
    def _parse_ohlcv_entry(
        self, 
        ohlcv_data: List, 
        pool_id: str, 
        timeframe: str
    ) -> Optional[OHLCVRecord]:
        """
        Enhanced OHLCV entry parser with comprehensive data quality validation.
        
        Args:
            ohlcv_data: Individual OHLCV data array [timestamp, open, high, low, close, volume]
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            OHLCVRecord object or None if parsing fails
        """
        try:
            # Enhanced input validation
            if not isinstance(ohlcv_data, list):
                logger.warning(f"Invalid OHLCV data type for pool {pool_id}: expected list, got {type(ohlcv_data)}")
                return None
            
            if len(ohlcv_data) < 6:
                logger.warning(f"Incomplete OHLCV data for pool {pool_id}: expected 6 elements, got {len(ohlcv_data)} - {ohlcv_data}")
                return None
            
            # Enhanced timestamp conversion and validation
            raw_timestamp = ohlcv_data[0]
            timestamp = self._safe_int_conversion(raw_timestamp, f"timestamp for pool {pool_id}")
            if timestamp is None:
                logger.warning(f"Invalid timestamp for pool {pool_id}: {raw_timestamp}")
                return None
            
            # Validate timestamp range (not too far in past or future)
            current_time = datetime.now().timestamp()
            min_timestamp = current_time - (2 * 365 * 24 * 3600)  # 2 years ago (more lenient for historical data)
            max_timestamp = current_time + (7 * 24 * 3600)  # 1 week in future
            
            if timestamp < min_timestamp:
                logger.warning(f"Timestamp too old for pool {pool_id}: {timestamp} ({datetime.fromtimestamp(timestamp)})")
                return None
            
            if timestamp > max_timestamp:
                logger.warning(f"Timestamp too far in future for pool {pool_id}: {timestamp} ({datetime.fromtimestamp(timestamp)})")
                return None
            
            # Enhanced price conversion and validation
            try:
                open_price = Decimal(str(ohlcv_data[1]))
                high_price = Decimal(str(ohlcv_data[2]))
                low_price = Decimal(str(ohlcv_data[3]))
                close_price = Decimal(str(ohlcv_data[4]))
                volume_usd = Decimal(str(ohlcv_data[5]))
            except (ValueError, InvalidOperation, TypeError) as e:
                logger.warning(f"Invalid numeric values in OHLCV data for pool {pool_id}: {e} - {ohlcv_data}")
                return None
            
            # Enhanced data quality validation
            validation_errors = []
            
            # Check for negative or zero prices
            if open_price <= 0:
                validation_errors.append(f"Invalid open price: {open_price}")
            if high_price <= 0:
                validation_errors.append(f"Invalid high price: {high_price}")
            if low_price <= 0:
                validation_errors.append(f"Invalid low price: {low_price}")
            if close_price <= 0:
                validation_errors.append(f"Invalid close price: {close_price}")
            
            # Check for negative volume (allow zero volume)
            if volume_usd < 0:
                validation_errors.append(f"Invalid volume: {volume_usd}")
            
            # Check price relationships with tolerance for market anomalies
            price_relationship_errors = []
            if high_price < low_price:
                price_relationship_errors.append(f"High price ({high_price}) < Low price ({low_price})")
            if high_price < open_price:
                price_relationship_errors.append(f"High price ({high_price}) < Open price ({open_price})")
            if high_price < close_price:
                price_relationship_errors.append(f"High price ({high_price}) < Close price ({close_price})")
            if low_price > open_price:
                price_relationship_errors.append(f"Low price ({low_price}) > Open price ({open_price})")
            if low_price > close_price:
                price_relationship_errors.append(f"Low price ({low_price}) > Close price ({close_price})")
            
            # Check for extreme price movements (potential data quality issues)
            if open_price > 0 and close_price > 0:
                price_change_ratio = abs(close_price - open_price) / open_price
                if price_change_ratio > 10:  # 1000% change
                    validation_errors.append(f"Extreme price movement: {price_change_ratio:.2%}")
            
            # Check for extremely high volume relative to price
            if open_price > 0 and volume_usd > (open_price * 1000000):  # Volume > 1M times price
                validation_errors.append(f"Suspicious volume: {volume_usd} vs price {open_price}")
            
            # Handle validation errors
            if validation_errors:
                logger.warning(f"Data quality issues for pool {pool_id} at timestamp {timestamp}: {'; '.join(validation_errors)}")
                # For critical errors, reject the record
                critical_errors = [e for e in validation_errors if any(keyword in e.lower() for keyword in ['invalid', 'negative'])]
                if critical_errors:
                    return None
            
            # Handle price relationship errors (log but don't reject - real market data can have anomalies)
            if price_relationship_errors:
                logger.debug(f"Price relationship anomalies for pool {pool_id} at timestamp {timestamp}: {'; '.join(price_relationship_errors)}")
            
            # Convert timestamp to datetime with proper timezone handling
            try:
                datetime_obj = datetime.fromtimestamp(timestamp)
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to convert timestamp {timestamp} to datetime for pool {pool_id}: {e}")
                return None
            
            # Create and return the OHLCV record
            record = OHLCVRecord(
                pool_id=pool_id,
                timeframe=timeframe,
                timestamp=timestamp,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume_usd=volume_usd,
                datetime=datetime_obj
            )
            
            logger.debug(f"Successfully parsed OHLCV record for pool {pool_id} at {datetime_obj}")
            return record
            
        except Exception as e:
            logger.error(f"Unexpected error parsing OHLCV entry for pool {pool_id}: {e}", exc_info=True)
            return None
    
    def _validate_price_relationships(
        self, 
        open_price: Decimal, 
        high_price: Decimal, 
        low_price: Decimal, 
        close_price: Decimal
    ) -> bool:
        """
        Validate that OHLCV price relationships are correct.
        
        Args:
            open_price: Opening price
            high_price: High price
            low_price: Low price
            close_price: Closing price
            
        Returns:
            True if price relationships are valid, False otherwise
        """
        try:
            # High should be >= all other prices
            if high_price < open_price or high_price < close_price or high_price < low_price:
                return False
            
            # Low should be <= all other prices
            if low_price > open_price or low_price > close_price or low_price > high_price:
                return False
            
            # All prices should be positive
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _get_expected_timeframe_seconds(self, timeframe: str) -> Optional[int]:
        """
        Get expected seconds between records for a given timeframe.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '1h', '1d')
            
        Returns:
            Expected seconds between records or None if unknown
        """
        timeframe_seconds = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '12h': 43200,
            '1d': 86400,
            # Legacy mappings
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        return timeframe_seconds.get(timeframe)
    
    def _convert_timeframe_to_api_format(self, timeframe: str) -> str:
        """
        Convert internal timeframe format to API format.
        
        Args:
            timeframe: Internal timeframe (e.g., '1m', '1h', '1d')
            
        Returns:
            API timeframe format that the GeckoTerminal API expects
        """
        # Map internal timeframes to API timeframes
        timeframe_mapping = {
            '1m': '1m',
            '5m': '5m', 
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '12h': '12h',
            '1d': '1d',
            # Legacy mappings for backwards compatibility
            'minute': '1m',
            'hour': '1h',
            'day': '1d'
        }
        
        api_timeframe = timeframe_mapping.get(timeframe)
        if api_timeframe:
            return api_timeframe
        else:
            # Fallback to 1h if unsupported
            logger.warning(f"Unsupported timeframe {timeframe}, using 1h as fallback")
            return '1h'
    
    async def _validate_ohlcv_data(self, records: List[OHLCVRecord]) -> ValidationResult:
        """
        Enhanced OHLCV data validation with comprehensive quality checks.
        
        Args:
            records: List of OHLCV records to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not records:
            warnings.append("No OHLCV records to validate")
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        logger.debug(f"Validating {len(records)} OHLCV records")
        
        # Enhanced duplicate detection with detailed tracking
        timestamp_tracker = {}
        duplicate_count = 0
        
        for record in records:
            timestamp_key = (record.pool_id, record.timeframe, record.timestamp)
            if timestamp_key in timestamp_tracker:
                duplicate_count += 1
                if duplicate_count <= 5:  # Log first 5 duplicates with details
                    original_record = timestamp_tracker[timestamp_key]
                    warnings.append(
                        f"Duplicate timestamp in batch: pool {record.pool_id}, "
                        f"timeframe {record.timeframe}, timestamp {record.timestamp} "
                        f"({datetime.fromtimestamp(record.timestamp)}). "
                        f"Original: O:{original_record.open_price}, New: O:{record.open_price}"
                    )
            else:
                timestamp_tracker[timestamp_key] = record
        
        if duplicate_count > 5:
            warnings.append(f"Found {duplicate_count} total duplicate timestamps in batch (showing first 5)")
        
        # Enhanced individual record validation
        now = datetime.now()
        price_anomaly_count = 0
        volume_anomaly_count = 0
        
        for idx, record in enumerate(records):
            record_context = f"Record {idx+1}/{len(records)} for pool {record.pool_id}"
            
            # Enhanced timestamp validation
            if record.datetime > now + timedelta(hours=2):
                warnings.append(f"{record_context}: Future timestamp detected: {record.datetime}")
            
            if record.datetime < now - timedelta(days=400):  # More than ~13 months
                warnings.append(f"{record_context}: Very old timestamp detected: {record.datetime}")
            
            # Enhanced volume validation
            if record.volume_usd < 0:
                errors.append(f"{record_context}: Negative volume detected: {record.volume_usd}")
            elif record.volume_usd == 0:
                warnings.append(f"{record_context}: Zero volume detected")
            elif record.volume_usd > Decimal('10000000000'):  # > 10B USD (higher threshold)
                volume_anomaly_count += 1
                if volume_anomaly_count <= 3:
                    warnings.append(f"{record_context}: Extremely high volume: {record.volume_usd}")
            
            # Enhanced price validation
            prices = [record.open_price, record.high_price, record.low_price, record.close_price]
            
            # Check for zero or negative prices
            for price_name, price_value in zip(['open', 'high', 'low', 'close'], prices):
                if price_value <= 0:
                    errors.append(f"{record_context}: Invalid {price_name} price: {price_value}")
            
            # Check for extremely small prices (potential precision issues)
            min_price = min(prices)
            if min_price > 0 and min_price < Decimal('1e-15'):
                warnings.append(f"{record_context}: Extremely small prices detected, min: {min_price}")
            
            # Check for extremely large prices
            max_price = max(prices)
            if max_price > Decimal('1000000'):  # > 1M USD
                price_anomaly_count += 1
                if price_anomaly_count <= 3:
                    warnings.append(f"{record_context}: Extremely high price detected, max: {max_price}")
            
            # Enhanced price relationship validation
            relationship_errors = []
            if record.high_price < record.low_price:
                relationship_errors.append(f"High ({record.high_price}) < Low ({record.low_price})")
            if record.high_price < record.open_price:
                relationship_errors.append(f"High ({record.high_price}) < Open ({record.open_price})")
            if record.high_price < record.close_price:
                relationship_errors.append(f"High ({record.high_price}) < Close ({record.close_price})")
            if record.low_price > record.open_price:
                relationship_errors.append(f"Low ({record.low_price}) > Open ({record.open_price})")
            if record.low_price > record.close_price:
                relationship_errors.append(f"Low ({record.low_price}) > Close ({record.close_price})")
            
            if relationship_errors:
                # Price relationship issues are warnings, not errors (real market data can have anomalies)
                warnings.append(f"{record_context}: Price relationship anomalies: {'; '.join(relationship_errors)}")
            
            # Check for extreme price movements within the candle
            if record.open_price > 0:
                high_change = abs(record.high_price - record.open_price) / record.open_price
                low_change = abs(record.low_price - record.open_price) / record.open_price
                close_change = abs(record.close_price - record.open_price) / record.open_price
                
                max_change = max(high_change, low_change, close_change)
                if max_change > 50:  # 5000% change
                    warnings.append(f"{record_context}: Extreme price movement: {max_change:.1%}")
            
            # Timeframe validation
            if record.timeframe not in self.supported_timeframes:
                errors.append(f"{record_context}: Unsupported timeframe: {record.timeframe}")
            
            # Pool ID validation
            if not record.pool_id or len(record.pool_id.strip()) == 0:
                errors.append(f"{record_context}: Empty or invalid pool_id")
        
        # Summary warnings for anomalies
        if price_anomaly_count > 3:
            warnings.append(f"Found {price_anomaly_count} records with extremely high prices (showing first 3)")
        
        if volume_anomaly_count > 3:
            warnings.append(f"Found {volume_anomaly_count} records with extremely high volume (showing first 3)")
        
        # Data continuity checks
        if len(records) > 1:
            # Sort records by timestamp for continuity analysis
            sorted_records = sorted(records, key=lambda r: r.timestamp)
            
            # Check for reasonable time gaps between records
            large_gaps = 0
            for i in range(1, len(sorted_records)):
                time_diff = sorted_records[i].timestamp - sorted_records[i-1].timestamp
                
                # Expected time difference based on timeframe
                expected_diff = self._get_expected_timeframe_seconds(record.timeframe)
                if expected_diff and time_diff > expected_diff * 10:  # More than 10x expected
                    large_gaps += 1
                    if large_gaps <= 3:
                        warnings.append(
                            f"Large time gap detected: {time_diff}s between records "
                            f"({datetime.fromtimestamp(sorted_records[i-1].timestamp)} -> "
                            f"{datetime.fromtimestamp(sorted_records[i].timestamp)})"
                        )
            
            if large_gaps > 3:
                warnings.append(f"Found {large_gaps} large time gaps in data (showing first 3)")
        
        # Final validation summary
        logger.info(f"OHLCV validation completed: {len(records)} records, {len(errors)} errors, {len(warnings)} warnings")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def _bulk_store_ohlcv_data(self, records: List[OHLCVRecord]) -> int:
        """
        Enhanced bulk storage for OHLCV data with optimized performance.
        
        Args:
            records: List of OHLCV records to store
            
        Returns:
            Number of records successfully stored
        """
        if not records:
            return 0
        
        try:
            # Sort records by timestamp for better database performance
            sorted_records = sorted(records, key=lambda r: (r.pool_id, r.timeframe, r.timestamp))
            
            # Use the database manager's bulk storage method
            stored_count = await self.db_manager.store_ohlcv_data(sorted_records)
            
            logger.debug(f"Bulk stored {stored_count} OHLCV records")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error in bulk OHLCV storage: {e}", exc_info=True)
            raise
    
    def _is_record_valid(self, record: OHLCVRecord) -> bool:
        """
        Quick validation check for individual OHLCV record.
        
        Args:
            record: OHLCV record to validate
            
        Returns:
            True if record passes basic validation
        """
        try:
            # Basic validation checks
            if not record.pool_id or record.pool_id.strip() == "":
                return False
            
            if record.timeframe not in self.supported_timeframes:
                return False
            
            if record.timestamp <= 0:
                return False
            
            # Check for positive prices
            if any(price <= 0 for price in [record.open_price, record.high_price, record.low_price, record.close_price]):
                return False
            
            # Check for non-negative volume
            if record.volume_usd < 0:
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _verify_data_continuity(self, pool_id: str) -> None:
        """
        Verify data continuity for a pool and detect gaps.
        
        Args:
            pool_id: Pool identifier to check continuity for
        """
        try:
            for timeframe in self.supported_timeframes:
                # Check continuity for the last 24 hours
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=self.max_gap_hours)
                
                # Get continuity report
                continuity_report = await self.db_manager.check_data_continuity(
                    pool_id, timeframe
                )
                
                # Log gaps if found
                if continuity_report.total_gaps > 0:
                    logger.warning(
                        f"Data gaps detected for pool {pool_id}, timeframe {timeframe}: "
                        f"{continuity_report.total_gaps} gaps, "
                        f"quality score: {continuity_report.data_quality_score:.2f}"
                    )
                    
                    # Log individual gaps
                    for gap in continuity_report.gaps[:5]:  # Log first 5 gaps
                        logger.debug(
                            f"Gap: {gap.start_time} to {gap.end_time} "
                            f"for pool {pool_id}, timeframe {timeframe}"
                        )
                
                # Flag poor data quality
                if continuity_report.data_quality_score < self.min_data_quality_score:
                    logger.warning(
                        f"Poor data quality for pool {pool_id}, timeframe {timeframe}: "
                        f"score {continuity_report.data_quality_score:.2f} "
                        f"< threshold {self.min_data_quality_score}"
                    )
                
        except Exception as e:
            logger.warning(f"Error verifying data continuity for pool {pool_id}: {e}")
    
    async def _validate_specific_data(self, data) -> Optional[ValidationResult]:
        """
        Validate collected OHLCV data.
        
        Args:
            data: Data to validate (not used in this implementation)
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        try:
            # Get active watchlist pools for validation
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            if not watchlist_pools:
                warnings.append("No active watchlist pools found for OHLCV validation")
                return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
            
            # Check data availability for each pool and timeframe
            for pool_id in watchlist_pools:
                for timeframe in self.supported_timeframes:
                    # Check if we have recent OHLCV data
                    recent_data = await self.db_manager.get_ohlcv_data(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_time=datetime.now() - timedelta(hours=2),
                        end_time=datetime.now()
                    )
                    
                    if not recent_data:
                        warnings.append(
                            f"No recent OHLCV data for pool {pool_id}, timeframe {timeframe}"
                        )
            
        except Exception as e:
            errors.append(f"OHLCV validation error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def get_collection_status(self) -> Dict[str, any]:
        """
        Get current status of OHLCV collection.
        
        Returns:
            Dictionary with collection status information
        """
        try:
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            # Count pools with OHLCV data for each timeframe
            timeframe_coverage = {}
            total_records = 0
            
            for timeframe in self.supported_timeframes:
                pools_with_data = 0
                
                for pool_id in watchlist_pools:
                    recent_data = await self.db_manager.get_ohlcv_data(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_time=datetime.now() - timedelta(hours=24),
                        end_time=datetime.now()
                    )
                    
                    if recent_data:
                        pools_with_data += 1
                        total_records += len(recent_data)
                
                timeframe_coverage[timeframe] = {
                    "pools_with_data": pools_with_data,
                    "coverage_percentage": (
                        (pools_with_data / len(watchlist_pools) * 100) 
                        if watchlist_pools else 0
                    )
                }
            
            return {
                "total_watchlist_pools": len(watchlist_pools),
                "supported_timeframes": self.supported_timeframes,
                "timeframe_coverage": timeframe_coverage,
                "total_recent_records": total_records,
                "default_timeframe": self.default_timeframe
            }
            
        except Exception as e:
            logger.error(f"Error getting OHLCV collection status: {e}")
            return {
                "error": str(e)
            }
    
    async def detect_and_report_gaps(self, pool_id: str, timeframe: str) -> ContinuityReport:
        """
        Detect and report data gaps for a specific pool and timeframe.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            ContinuityReport with gap information
        """
        try:
            return await self.db_manager.check_data_continuity(pool_id, timeframe)
        except Exception as e:
            logger.error(f"Error detecting gaps for pool {pool_id}, timeframe {timeframe}: {e}")
            return ContinuityReport(
                pool_id=pool_id,
                timeframe=timeframe,
                total_gaps=0,
                gaps=[],
                data_quality_score=0.0
            )
    
    async def backfill_gaps(self, pool_id: str, timeframe: str, gaps: List[Gap]) -> int:
        """
        Attempt to backfill data gaps using historical data collection.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            gaps: List of gaps to backfill
            
        Returns:
            Number of records backfilled
        """
        backfilled_records = 0
        
        for gap in gaps:
            try:
                logger.info(
                    f"Attempting to backfill gap for pool {pool_id}, timeframe {timeframe}: "
                    f"{gap.start_time} to {gap.end_time}"
                )
                
                # Use before_timestamp to get historical data for the gap period
                before_timestamp = int(gap.end_time.timestamp())
                
                # Extract pool address from pool_id (remove network prefix if present)
                pool_address = pool_id
                if pool_id.startswith(f"{self.network}_"):
                    pool_address = pool_id[len(f"{self.network}_"):]
                
                response = await self.client.get_ohlcv_data(
                    network=self.network,
                    pool_address=pool_address,
                    timeframe=self._convert_timeframe_to_api_format(timeframe),
                    before_timestamp=before_timestamp,
                    limit=self.limit,
                    currency=self.currency,
                    token=self.token
                )
                
                # Parse and filter data for the gap period
                ohlcv_records = self._parse_ohlcv_response(response, pool_id, timeframe)
                gap_records = [
                    record for record in ohlcv_records
                    if gap.start_time <= record.datetime <= gap.end_time
                ]
                
                if gap_records:
                    # Validate and store backfilled data
                    validation_result = await self._validate_ohlcv_data(gap_records)
                    
                    if validation_result.is_valid:
                        stored_count = await self.db_manager.store_ohlcv_data(gap_records)
                        backfilled_records += stored_count
                        
                        logger.info(
                            f"Backfilled {stored_count} records for gap in pool {pool_id}, "
                            f"timeframe {timeframe}"
                        )
                    else:
                        logger.warning(
                            f"Backfill data validation failed for pool {pool_id}: "
                            f"{validation_result.errors}"
                        )
                
            except Exception as e:
                logger.warning(f"Error backfilling gap for pool {pool_id}: {e}")
                continue
        
        return backfilled_records