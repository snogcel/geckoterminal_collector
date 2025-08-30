"""
Historical OHLCV data collector using direct API requests.

This module provides functionality to collect historical OHLCV data up to 6 months back
using direct HTTP requests to GeckoTerminal API with proper query parameters, pagination
logic for large historical data sets, and backfill functionality for data gaps.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any

import aiohttp

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import (
    CollectionResult, OHLCVRecord, ValidationResult, Gap
)
from gecko_terminal_collector.utils.metadata import MetadataTracker

logger = logging.getLogger(__name__)


class HistoricalOHLCVCollector(BaseDataCollector):
    """
    Collects historical OHLCV data using direct API requests.
    
    This collector uses direct HTTP requests to GeckoTerminal API with proper query
    parameters, implements pagination logic for large historical data sets using
    before_timestamp, and provides backfill functionality for data gaps and missing intervals.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False
    ):
        """
        Initialize the historical OHLCV collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock responses for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        self.network = config.dexes['network'] if isinstance(config.dexes, dict) else config.dexes.network
        self.supported_timeframes = config.timeframes['supported'] if isinstance(config.timeframes, dict) else config.timeframes.supported
        self.api_base_url = config.api['base_url'] if isinstance(config.api, dict) else config.api.base_url
        
        # Historical collection settings
        self.max_history_days = getattr(config, 'max_history_days', 180)  # 6 months
        self.limit_per_request = getattr(config, 'historical_limit', 1000)
        self.include_empty_intervals = getattr(config, 'include_empty_intervals', False)
        self.pagination_delay = getattr(config, 'pagination_delay', 1.0)  # Delay between paginated requests
        
        # Session for direct API calls
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Track collection progress
        self._collection_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_records': 0
        }
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "historical_ohlcv_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect historical OHLCV data for watchlist tokens.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        self._collection_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_records': 0
        }
        
        try:
            # Initialize HTTP session
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.api.timeout)
            ) as session:
                self._session = session
                
                # Get active watchlist pool IDs
                logger.info("Retrieving active watchlist pools for historical OHLCV collection")
                watchlist_pools = await self.db_manager.get_watchlist_pools()
                
                if not watchlist_pools:
                    logger.info("No active watchlist pools found")
                    return self.create_success_result(0, start_time)
                
                logger.info(f"Found {len(watchlist_pools)} watchlist pools for historical OHLCV collection")
                
                # Collect historical OHLCV data for each pool
                for pool_id in watchlist_pools:
                    try:
                        pool_records = await self._collect_pool_historical_data(pool_id)
                        records_collected += pool_records
                        
                    except Exception as e:
                        error_msg = f"Error collecting historical OHLCV data for pool {pool_id}: {str(e)}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        continue
                
                logger.info(
                    f"Historical OHLCV collection completed: {records_collected} records collected "
                    f"for {len(watchlist_pools)} pools. Stats: {self._collection_stats}"
                )
                
                # Create result with any errors encountered
                if errors:
                    return CollectionResult(
                        success=True,  # Partial success
                        records_collected=records_collected,
                        errors=errors,
                        collection_time=start_time,
                        collector_type=self.get_collection_key()
                    )
                
                return CollectionResult(
                    success=True,
                    records_collected=records_collected,
                    errors=[],
                    collection_time=start_time,
                    collector_type=self.get_collection_key()
                )
                
        except Exception as e:
            error_msg = f"Error in historical OHLCV collection: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def _collect_pool_historical_data(self, pool_id: str) -> int:
        """
        Collect historical OHLCV data for a specific pool across all configured timeframes.
        
        Args:
            pool_id: Pool identifier to collect data for
            
        Returns:
            Number of OHLCV records collected for this pool
        """
        total_records = 0
        
        for timeframe in self.supported_timeframes:
            try:
                logger.debug(f"Collecting historical OHLCV data for pool {pool_id}, timeframe {timeframe}")
                
                # Determine the time range for historical data collection
                end_time = datetime.now()
                start_time = end_time - timedelta(days=self.max_history_days)
                
                # Check what data we already have to avoid unnecessary requests
                existing_data_range = await self._get_existing_data_range(pool_id, timeframe)
                
                if existing_data_range:
                    # Adjust start_time to only collect missing data
                    earliest_existing = existing_data_range[0]
                    if earliest_existing > start_time:
                        # We need data before our earliest existing data
                        end_time = earliest_existing
                    else:
                        logger.debug(
                            f"Historical data already exists for pool {pool_id}, timeframe {timeframe} "
                            f"from {earliest_existing}"
                        )
                        continue
                
                # Collect historical data with pagination
                records = await self._collect_historical_data_with_pagination(
                    pool_id, timeframe, start_time, end_time
                )
                
                if records:
                    # Validate data before storage
                    validation_result = await self._validate_ohlcv_data(records)
                    
                    if validation_result.is_valid:
                        # Store historical OHLCV data with duplicate prevention
                        stored_count = await self.db_manager.store_ohlcv_data(records)
                        total_records += stored_count
                        self._collection_stats['total_records'] += stored_count
                        
                        logger.info(
                            f"Stored {stored_count} historical OHLCV records for pool {pool_id}, "
                            f"timeframe {timeframe}"
                        )
                    else:
                        logger.warning(
                            f"Historical OHLCV data validation failed for pool {pool_id}, "
                            f"timeframe {timeframe}: {validation_result.errors}"
                        )
                else:
                    logger.debug(
                        f"No historical OHLCV data returned for pool {pool_id}, timeframe {timeframe}"
                    )
                
            except Exception as e:
                error_msg = f"Error collecting historical OHLCV data for pool {pool_id}, timeframe {timeframe}: {e}"
                logger.warning(error_msg)
                self._collection_stats['failed_requests'] += 1
                continue
        
        return total_records
    
    async def _get_existing_data_range(self, pool_id: str, timeframe: str) -> Optional[Tuple[datetime, datetime]]:
        """
        Get the range of existing OHLCV data for a pool and timeframe.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            Tuple of (earliest_datetime, latest_datetime) or None if no data exists
        """
        try:
            # Get the earliest and latest timestamps for existing data
            existing_data = await self.db_manager.get_ohlcv_data(
                pool_id=pool_id,
                timeframe=timeframe,
                start_time=None,  # Get all data
                end_time=None
            )
            
            if not existing_data:
                return None
            
            # Find min and max timestamps
            timestamps = [record.datetime for record in existing_data]
            return (min(timestamps), max(timestamps))
            
        except Exception as e:
            logger.warning(f"Error getting existing data range for pool {pool_id}: {e}")
            return None
    
    async def _collect_historical_data_with_pagination(
        self,
        pool_id: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[OHLCVRecord]:
        """
        Collect historical OHLCV data with pagination using before_timestamp.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            start_time: Start of time range to collect
            end_time: End of time range to collect
            
        Returns:
            List of OHLCV records collected
        """
        all_records = []
        current_before_timestamp = int(end_time.timestamp())
        start_timestamp = int(start_time.timestamp())
        
        logger.debug(
            f"Starting paginated collection for pool {pool_id}, timeframe {timeframe} "
            f"from {start_time} to {end_time}"
        )
        
        while current_before_timestamp > start_timestamp:
            try:
                # Make direct API request
                response_data = await self._make_direct_ohlcv_request(
                    pool_id, timeframe, current_before_timestamp
                )
                
                if not response_data:
                    logger.debug(f"No more data available for pool {pool_id}, timeframe {timeframe}")
                    break
                
                # Parse OHLCV data from response
                records = self._parse_direct_ohlcv_response(response_data, pool_id, timeframe)
                
                if not records:
                    logger.debug(f"No records parsed from response for pool {pool_id}, timeframe {timeframe}")
                    break
                
                # Filter records to only include those in our target time range
                # Use a more lenient time range for backfill scenarios
                filtered_records = [
                    record for record in records
                    if (start_time - timedelta(hours=1)) <= record.datetime <= (end_time + timedelta(hours=1))
                ]
                
                all_records.extend(filtered_records)
                
                # Update pagination cursor to the earliest timestamp from this batch
                earliest_timestamp = min(record.timestamp for record in records)
                
                # If we've reached our start time or got no new data, stop
                if earliest_timestamp <= start_timestamp or len(records) < self.limit_per_request:
                    break
                
                current_before_timestamp = earliest_timestamp
                
                # Add delay between paginated requests to respect rate limits
                if self.pagination_delay > 0:
                    await asyncio.sleep(self.pagination_delay)
                
                logger.debug(
                    f"Collected {len(filtered_records)} records for pool {pool_id}, "
                    f"timeframe {timeframe}, continuing from timestamp {current_before_timestamp}"
                )
                
            except Exception as e:
                logger.warning(
                    f"Error in paginated request for pool {pool_id}, timeframe {timeframe}: {e}"
                )
                self._collection_stats['failed_requests'] += 1
                break
        
        logger.debug(
            f"Completed paginated collection for pool {pool_id}, timeframe {timeframe}: "
            f"{len(all_records)} total records"
        )
        
        return all_records
    
    async def _make_direct_ohlcv_request(
        self,
        pool_id: str,
        timeframe: str,
        before_timestamp: int
    ) -> Optional[Dict[str, Any]]:
        """
        Make a direct API request for OHLCV data.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            before_timestamp: Timestamp to get data before
            
        Returns:
            API response data or None if request failed
        """
        if self.use_mock:
            return await self._get_mock_historical_response(pool_id, timeframe, before_timestamp)
        
        try:
            # Convert timeframe to API format
            api_timeframe = self._convert_timeframe_to_api_format(timeframe)
            
            # Build API endpoint URL
            endpoint = f"networks/{self.network}/pools/{pool_id}/ohlcv/{api_timeframe}"
            url = f"{self.api_base_url}/{endpoint}"
            
            # Build query parameters
            params = {
                'before_timestamp': before_timestamp,
                'limit': self.limit_per_request,
                'currency': 'usd',
                'token': 'base'
            }
            
            if self.include_empty_intervals:
                params['include_empty_intervals'] = 'true'
            
            self._collection_stats['total_requests'] += 1
            
            # Make the request
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    self._collection_stats['successful_requests'] += 1
                    return await response.json()
                else:
                    self._collection_stats['failed_requests'] += 1
                    logger.warning(
                        f"API request failed with status {response.status} for pool {pool_id}, "
                        f"timeframe {timeframe}: {await response.text()}"
                    )
                    return None
                    
        except Exception as e:
            self._collection_stats['failed_requests'] += 1
            logger.warning(f"Direct API request failed for pool {pool_id}, timeframe {timeframe}: {e}")
            return None
    
    async def _get_mock_historical_response(
        self,
        pool_id: str,
        timeframe: str,
        before_timestamp: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get mock historical response for testing.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            before_timestamp: Timestamp to get data before
            
        Returns:
            Mock API response data
        """
        try:
            # Load mock response from fixture files
            from pathlib import Path
            import json
            
            response_file = Path("specs/response_body.txt")
            if response_file.exists():
                with open(response_file, 'r') as f:
                    mock_data = json.load(f)
                
                # Modify timestamps to be before the requested timestamp
                if 'data' in mock_data and 'attributes' in mock_data['data']:
                    ohlcv_list = mock_data['data']['attributes'].get('ohlcv_list', [])
                    
                    # Adjust timestamps to be before the requested timestamp
                    adjusted_ohlcv_list = []
                    for i, ohlcv_entry in enumerate(ohlcv_list):
                        if len(ohlcv_entry) >= 6:
                            # Create timestamp before the requested one
                            adjusted_timestamp = before_timestamp - (i + 1) * 900  # 15 minutes apart
                            adjusted_entry = [adjusted_timestamp] + ohlcv_entry[1:]
                            adjusted_ohlcv_list.append(adjusted_entry)
                    
                    mock_data['data']['attributes']['ohlcv_list'] = adjusted_ohlcv_list
                
                self._collection_stats['successful_requests'] += 1
                return mock_data
            
        except Exception as e:
            logger.warning(f"Error loading mock historical response: {e}")
        
        self._collection_stats['failed_requests'] += 1
        return None
    
    def _parse_direct_ohlcv_response(
        self,
        response_data: Dict[str, Any],
        pool_id: str,
        timeframe: str
    ) -> List[OHLCVRecord]:
        """
        Parse direct API OHLCV response into OHLCVRecord objects.
        
        Args:
            response_data: Direct API response data
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            List of OHLCVRecord objects
        """
        records = []
        
        try:
            data = response_data.get("data", {})
            attributes = data.get("attributes", {})
            ohlcv_list = attributes.get("ohlcv_list", [])
            
            if not isinstance(ohlcv_list, list):
                logger.warning(f"Expected list in historical OHLCV response for pool {pool_id}")
                return records
            
            for ohlcv_data in ohlcv_list:
                try:
                    record = self._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
                    if record:
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing historical OHLCV entry for pool {pool_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing historical OHLCV response for pool {pool_id}: {e}")
        
        return records
    
    def _parse_ohlcv_entry(
        self,
        ohlcv_data: List,
        pool_id: str,
        timeframe: str
    ) -> Optional[OHLCVRecord]:
        """
        Parse individual OHLCV entry into OHLCVRecord object.
        
        Args:
            ohlcv_data: Individual OHLCV data array [timestamp, open, high, low, close, volume]
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            OHLCVRecord object or None if parsing fails
        """
        try:
            if not isinstance(ohlcv_data, list) or len(ohlcv_data) < 6:
                logger.warning(f"Invalid historical OHLCV data format for pool {pool_id}: {ohlcv_data}")
                return None
            
            # Extract OHLCV values
            timestamp = int(ohlcv_data[0])
            open_price = Decimal(str(ohlcv_data[1]))
            high_price = Decimal(str(ohlcv_data[2]))
            low_price = Decimal(str(ohlcv_data[3]))
            close_price = Decimal(str(ohlcv_data[4]))
            volume_usd = Decimal(str(ohlcv_data[5]))
            
            # Convert timestamp to datetime
            datetime_obj = datetime.fromtimestamp(timestamp)
            
            # Validate price relationships (log warning but don't reject)
            if not self._validate_price_relationships(open_price, high_price, low_price, close_price):
                logger.debug(
                    f"Unusual price relationships in historical data for pool {pool_id} at {datetime_obj}: "
                    f"O:{open_price}, H:{high_price}, L:{low_price}, C:{close_price}"
                )
                # Continue processing - real market data can have anomalies
            
            return OHLCVRecord(
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
            
        except (ValueError, TypeError, InvalidOperation, IndexError) as e:
            logger.warning(f"Error parsing historical OHLCV entry for pool {pool_id}: {e}")
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
    
    def _convert_timeframe_to_api_format(self, timeframe: str) -> str:
        """
        Convert internal timeframe format to API format.
        
        Args:
            timeframe: Internal timeframe (e.g., '1m', '1h', '1d')
            
        Returns:
            API timeframe format (e.g., 'minute', 'hour', 'day')
        """
        # Map internal timeframes to API formats
        timeframe_mapping = {
            '1m': 'minute',
            '5m': 'minute',
            '15m': 'minute',
            '1h': 'hour',
            '4h': 'hour',
            '12h': 'hour',
            '1d': 'day'
        }
        
        return timeframe_mapping.get(timeframe, 'hour')
    
    async def _validate_ohlcv_data(self, records: List[OHLCVRecord]) -> ValidationResult:
        """
        Validate historical OHLCV data before storage.
        
        Args:
            records: List of OHLCV records to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not records:
            warnings.append("No historical OHLCV records to validate")
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        # Check for duplicate timestamps within the batch
        timestamps = set()
        duplicate_count = 0
        for record in records:
            timestamp_key = (record.pool_id, record.timeframe, record.timestamp)
            if timestamp_key in timestamps:
                duplicate_count += 1
                if duplicate_count <= 3:  # Only log first few duplicates
                    warnings.append(
                        f"Duplicate timestamp in historical batch: pool {record.pool_id}, "
                        f"timeframe {record.timeframe}, timestamp {record.timestamp}"
                    )
            timestamps.add(timestamp_key)
        if duplicate_count > 3:
            warnings.append(f"Found {duplicate_count} total duplicate timestamps in historical batch")
        
        # Validate individual records
        for record in records:
            # Check timestamp is reasonable (not in future)
            now = datetime.now()
            if record.datetime > now + timedelta(hours=1):
                warnings.append(
                    f"Future timestamp in historical data: {record.datetime} for pool {record.pool_id}"
                )
            
            # Check for very old data (more than max history)
            max_age = now - timedelta(days=self.max_history_days + 30)  # Allow some buffer
            if record.datetime < max_age:
                warnings.append(
                    f"Very old timestamp in historical data: {record.datetime} for pool {record.pool_id}"
                )
            
            # Check volume is non-negative
            if record.volume_usd < 0:
                errors.append(
                    f"Negative volume in historical data: {record.volume_usd} for pool {record.pool_id}"
                )
            
            # Check timeframe is supported
            if record.timeframe not in self.supported_timeframes:
                errors.append(
                    f"Unsupported timeframe in historical data: {record.timeframe} for pool {record.pool_id}"
                )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def backfill_data_gaps(self, pool_id: str, timeframe: str, gaps: List[Gap]) -> int:
        """
        Backfill data gaps using historical data collection.
        
        Args:
            pool_id: Pool identifier
            timeframe: Data timeframe
            gaps: List of gaps to backfill
            
        Returns:
            Number of records backfilled
        """
        backfilled_records = 0
        
        # Initialize HTTP session for backfill
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.api.timeout)
        ) as session:
            self._session = session
            
            for gap in gaps:
                try:
                    logger.info(
                        f"Attempting to backfill historical gap for pool {pool_id}, timeframe {timeframe}: "
                        f"{gap.start_time} to {gap.end_time}"
                    )
                    
                    # Collect historical data for the gap period
                    gap_records = await self._collect_historical_data_with_pagination(
                        pool_id, timeframe, gap.start_time, gap.end_time
                    )
                    
                    if gap_records:
                        # Validate and store backfilled data
                        validation_result = await self._validate_ohlcv_data(gap_records)
                        
                        if validation_result.is_valid:
                            stored_count = await self.db_manager.store_ohlcv_data(gap_records)
                            backfilled_records += stored_count
                            
                            logger.info(
                                f"Backfilled {stored_count} historical records for gap in pool {pool_id}, "
                                f"timeframe {timeframe}"
                            )
                        else:
                            logger.warning(
                                f"Historical backfill data validation failed for pool {pool_id}: "
                                f"{validation_result.errors}"
                            )
                    
                except Exception as e:
                    logger.warning(f"Error backfilling historical gap for pool {pool_id}: {e}")
                    continue
        
        return backfilled_records
    
    async def _validate_specific_data(self, data) -> Optional[ValidationResult]:
        """
        Validate collected historical OHLCV data.
        
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
                warnings.append("No active watchlist pools found for historical OHLCV validation")
                return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
            
            # Check historical data availability for each pool and timeframe
            for pool_id in watchlist_pools:
                for timeframe in self.supported_timeframes:
                    # Check if we have historical OHLCV data
                    historical_start = datetime.now() - timedelta(days=self.max_history_days)
                    historical_data = await self.db_manager.get_ohlcv_data(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_time=historical_start,
                        end_time=datetime.now() - timedelta(days=1)  # Exclude very recent data
                    )
                    
                    if not historical_data:
                        warnings.append(
                            f"No historical OHLCV data for pool {pool_id}, timeframe {timeframe}"
                        )
            
        except Exception as e:
            errors.append(f"Historical OHLCV validation error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def get_collection_status(self) -> Dict[str, Any]:
        """
        Get current status of historical OHLCV collection.
        
        Returns:
            Dictionary with collection status information
        """
        try:
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            # Count pools with historical OHLCV data for each timeframe
            timeframe_coverage = {}
            total_historical_records = 0
            historical_start = datetime.now() - timedelta(days=self.max_history_days)
            
            for timeframe in self.supported_timeframes:
                pools_with_historical_data = 0
                
                for pool_id in watchlist_pools:
                    historical_data = await self.db_manager.get_ohlcv_data(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_time=historical_start,
                        end_time=datetime.now() - timedelta(days=1)
                    )
                    
                    if historical_data:
                        pools_with_historical_data += 1
                        total_historical_records += len(historical_data)
                
                timeframe_coverage[timeframe] = {
                    "pools_with_historical_data": pools_with_historical_data,
                    "coverage_percentage": (
                        (pools_with_historical_data / len(watchlist_pools) * 100) 
                        if watchlist_pools else 0
                    )
                }
            
            return {
                "total_watchlist_pools": len(watchlist_pools),
                "supported_timeframes": self.supported_timeframes,
                "max_history_days": self.max_history_days,
                "timeframe_coverage": timeframe_coverage,
                "total_historical_records": total_historical_records,
                "collection_stats": self._collection_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting historical OHLCV collection status: {e}")
            return {
                "error": str(e)
            }