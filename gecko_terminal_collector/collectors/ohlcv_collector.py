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
    
    async def _collect_pool_ohlcv_data(self, pool_id: str) -> int:
        """
        Collect OHLCV data for a specific pool across all configured timeframes.
        
        Args:
            pool_id: Pool identifier to collect data for
            
        Returns:
            Number of OHLCV records collected for this pool
        """
        total_records = 0
        
        for timeframe in self.supported_timeframes:
            try:
                logger.debug(f"Collecting OHLCV data for pool {pool_id}, timeframe {timeframe}")
                
                # Get OHLCV data from API
                response = await self.client.get_ohlcv_data(
                    network=self.network,
                    pool_address=pool_id,
                    timeframe=self._convert_timeframe_to_api_format(timeframe),
                    limit=self.limit,
                    currency=self.currency,
                    token=self.token
                )
                
                # Parse and validate OHLCV data
                ohlcv_records = self._parse_ohlcv_response(response, pool_id, timeframe)
                
                if ohlcv_records:
                    # Validate data before storage
                    validation_result = await self._validate_ohlcv_data(ohlcv_records)
                    
                    if validation_result.is_valid:
                        # Store OHLCV data with duplicate prevention
                        stored_count = await self.db_manager.store_ohlcv_data(ohlcv_records)
                        total_records += stored_count
                        
                        logger.debug(
                            f"Stored {stored_count} OHLCV records for pool {pool_id}, "
                            f"timeframe {timeframe}"
                        )
                    else:
                        logger.warning(
                            f"OHLCV data validation failed for pool {pool_id}, "
                            f"timeframe {timeframe}: {validation_result.errors}"
                        )
                else:
                    logger.debug(f"No OHLCV data returned for pool {pool_id}, timeframe {timeframe}")
                
            except Exception as e:
                error_msg = f"Error collecting OHLCV data for pool {pool_id}, timeframe {timeframe}: {e}"
                logger.warning(error_msg)
                self._collection_errors.append(error_msg)
                continue
        
        return total_records
    
    def _parse_ohlcv_response(
        self, 
        response: Dict, 
        pool_id: str, 
        timeframe: str
    ) -> List[OHLCVRecord]:
        """
        Parse OHLCV API response into OHLCVRecord objects.
        
        Args:
            response: API response from get_ohlcv_data
            pool_id: Pool identifier
            timeframe: Data timeframe
            
        Returns:
            List of OHLCVRecord objects
        """
        records = []
        
        try:
            data = response.get("data", {})
            attributes = data.get("attributes", {})
            ohlcv_list = attributes.get("ohlcv_list", [])
            
            if not isinstance(ohlcv_list, list):
                logger.warning(f"Expected list in OHLCV response for pool {pool_id}")
                return records
            
            for ohlcv_data in ohlcv_list:
                try:
                    record = self._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
                    if record:
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing OHLCV entry for pool {pool_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing OHLCV response for pool {pool_id}: {e}")
        
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
                logger.warning(f"Invalid OHLCV data format for pool {pool_id}: {ohlcv_data}")
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
                    f"Unusual price relationships for pool {pool_id} at {datetime_obj}: "
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
            logger.warning(f"Error parsing OHLCV entry for pool {pool_id}: {e}")
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
        Validate OHLCV data before storage.
        
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
        
        # Check for duplicate timestamps within the batch
        timestamps = set()
        duplicate_count = 0
        for record in records:
            timestamp_key = (record.pool_id, record.timeframe, record.timestamp)
            if timestamp_key in timestamps:
                duplicate_count += 1
                if duplicate_count <= 3:  # Only log first few duplicates
                    warnings.append(
                        f"Duplicate timestamp in batch: pool {record.pool_id}, "
                        f"timeframe {record.timeframe}, timestamp {record.timestamp}"
                    )
            timestamps.add(timestamp_key)
        if duplicate_count > 3:
            warnings.append(f"Found {duplicate_count} total duplicate timestamps in batch")
        
        # Validate individual records
        for record in records:
            # Check timestamp is reasonable (not too far in future or past)
            now = datetime.now()
            if record.datetime > now + timedelta(hours=1):
                warnings.append(
                    f"Future timestamp detected: {record.datetime} for pool {record.pool_id}"
                )
            
            # Check for very old data (more than 1 year)
            if record.datetime < now - timedelta(days=365):
                warnings.append(
                    f"Very old timestamp detected: {record.datetime} for pool {record.pool_id}"
                )
            
            # Check volume is non-negative
            if record.volume_usd < 0:
                errors.append(
                    f"Negative volume detected: {record.volume_usd} for pool {record.pool_id}"
                )
            
            # Check timeframe is supported
            if record.timeframe not in self.supported_timeframes:
                errors.append(
                    f"Unsupported timeframe: {record.timeframe} for pool {record.pool_id}"
                )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
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
                
                response = await self.client.get_ohlcv_data(
                    network=self.network,
                    pool_address=pool_id,
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