"""
Trade data collector.

This module provides functionality to collect trade data for watchlist tokens
with volume filtering, configurable minimum USD volume thresholds, duplicate
prevention using trade IDs and composite keys.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import (
    CollectionResult, TradeRecord, ValidationResult, Gap
)
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.utils.data_normalizer import DataTypeNormalizer

logger = logging.getLogger(__name__)


class TradeCollector(BaseDataCollector):
    """
    Collects trade data for watchlist tokens with volume filtering.
    
    This collector retrieves trade data with configurable minimum USD volume
    thresholds, implements duplicate prevention using trade IDs and composite
    keys, and processes trade data with proper validation.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False,
        **kwargs
    ):
        """
        Initialize the trade collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock, **kwargs)
        
        self.network = config.dexes['network'] if isinstance(config.dexes, dict) else config.dexes.network
        
        # Trade collection settings
        self.min_trade_volume_usd = getattr(config.thresholds, 'min_trade_volume_usd', 100.0)
        self.trade_limit = getattr(config, 'trade_limit', 300)  # Max trades per API call
        
        # Track errors during collection
        self._collection_errors = []
        
        # Trade data validation settings
        self.max_trade_age_hours = getattr(config, 'max_trade_age_hours', 24)
        
        # Continuity verification settings
        self.continuity_check_interval_hours = getattr(config, 'continuity_check_interval_hours', 1)
        self.significant_gap_threshold_hours = getattr(config, 'significant_gap_threshold_hours', 2)
        
        # Fair rotation and prioritization settings
        self.api_rate_limit_threshold = getattr(config, 'api_rate_limit_threshold', 0.8)  # 80% of limit
        self.high_volume_threshold_usd = getattr(config, 'high_volume_threshold_usd', 10000.0)
        self.rotation_window_minutes = getattr(config, 'rotation_window_minutes', 30)
        
        # Track pool priorities and rotation state
        self._pool_priorities: Dict[str, float] = {}
        self._last_collection_times: Dict[str, datetime] = {}
        self._api_call_count = 0
        self._rotation_start_time = datetime.now()
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "trade_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect trade data for watchlist tokens with continuity verification and fair rotation.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        self._collection_errors = []  # Reset error tracking
        
        try:
            # Get active watchlist pool IDs
            logger.info("Retrieving active watchlist pools for trade collection")
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            if not watchlist_pools:
                logger.info("No active watchlist pools found")
                return self.create_success_result(0, start_time)
            
            logger.info(f"Found {len(watchlist_pools)} watchlist pools for trade collection")
            
            # Implement fair rotation and prioritization
            rotated_pools = await self.implement_fair_rotation(watchlist_pools)
            logger.info(f"Fair rotation selected {len(rotated_pools)} pools for collection")
            
            # handle prefix scenario with pool_addresses
            processed_pool_addresses = []

            for pool in rotated_pools:
                prefix, _, _ = pool.partition('_')
                lookup_prefix = prefix + '_'
                processed_pool_addresses.append(pool.removeprefix(lookup_prefix))  
            
            # Collect trade data for each pool
            for pool_id in processed_pool_addresses:
                try:
                    pool_records = await self._collect_pool_trade_data(pool_id)
                    records_collected += pool_records
                    self._api_call_count += 1
                    
                except Exception as e:
                    error_msg = f"Error collecting trade data for pool {pool_id}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Verify data continuity and attempt recovery
            logger.info("Verifying trade data continuity")
            continuity_results = await self.verify_and_recover_continuity(rotated_pools)
            
            # Add continuity information to result metadata
            continuity_summary = {
                "pools_with_gaps": continuity_results.get("pools_with_gaps", 0),
                "total_gaps_found": continuity_results.get("total_gaps_found", 0),
                "recovery_attempts": continuity_results.get("recovery_attempts", 0),
                "recovery_successes": continuity_results.get("recovery_successes", 0)
            }
            
            logger.info(
                f"Trade collection completed: {records_collected} records collected "
                f"for {len(rotated_pools)} pools. Continuity: {continuity_summary['pools_with_gaps']} "
                f"pools with gaps, {continuity_summary['recovery_successes']} recoveries successful"
            )
            
            # Combine pool-level errors with individual API call errors
            all_errors = errors + self._collection_errors
            
            # Create result with continuity information
            if all_errors:
                result = CollectionResult(
                    success=True,  # Partial success - system continues despite errors
                    records_collected=records_collected,
                    errors=all_errors,
                    collection_time=start_time,
                    collector_type=self.get_collection_key()
                )
            else:
                result = self.create_success_result(records_collected, start_time)
            
            # Add continuity metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata.update({
                "continuity_verification": continuity_summary,
                "fair_rotation": {
                    "total_pools": len(watchlist_pools),
                    "selected_pools": len(rotated_pools),
                    "api_calls_made": self._api_call_count
                }
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error in trade collection: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def _collect_pool_trade_data(self, pool_id: str) -> int:
        """
        Collect trade data for a specific pool.
        
        Args:
            pool_id: Pool identifier to collect data for
            
        Returns:
            Number of trade records collected for this pool
        """
        try:
            logger.debug(f"Collecting trade data for pool {pool_id}")
            
            # Extract pool address from pool_id (remove network prefix if present)
            pool_address = pool_id
            if pool_id.startswith(f"{self.network}_"):
                pool_address = pool_id[len(f"{self.network}_"):]
            
            # Get trade data from API with rate limiting
            response = await self.make_api_request(
                self.client.get_trades,
                network=self.network,
                pool_address=pool_address,
                trade_volume_filter=self.min_trade_volume_usd
            )

            logger.debug(f"Received trade data of type: {type(response)} for pool: {pool_id}")
            
            # Normalize data to consistent List[Dict] format
            try:
                normalized_data = DataTypeNormalizer.normalize_response_data(response)
                # Wrap in expected API response format
                response_dict = {"data": normalized_data}
                logger.debug(f"Normalized trade data to list with {len(normalized_data)} items for pool: {pool_id}")
            except ValueError as e:
                error_msg = f"Failed to normalize trade data for pool {pool_id}: {str(e)}"
                logger.error(error_msg)
                return 0

            # Parse and validate trade data
            trade_records = self._parse_trade_response(response_dict, pool_id)
            
            if trade_records:
                # Filter trades by volume threshold
                filtered_records = self._filter_trades_by_volume(trade_records)
                
                # Validate data before storage
                validation_result = await self._validate_trade_data(filtered_records)
                
                if validation_result.is_valid:
                    # Store trade data with duplicate prevention
                    stored_count = await self.db_manager.store_trade_data(filtered_records)
                    
                    logger.debug(
                        f"Stored {stored_count} trade records for pool {pool_id} "
                        f"(filtered from {len(trade_records)} total)"
                    )
                    
                    return stored_count
                else:
                    logger.warning(
                        f"Trade data validation failed for pool {pool_id}: "
                        f"{validation_result.errors}"
                    )
            else:
                logger.debug(f"No trade data returned for pool {pool_id}")
            
            return 0
            
        except Exception as e:
            error_msg = f"Error collecting trade data for pool {pool_id}: {e}"
            logger.warning(error_msg)
            self._collection_errors.append(error_msg)
            return 0
    
    def _parse_trade_response(self, response: Dict, pool_id: str) -> List[TradeRecord]:
        """
        Parse trade API response into TradeRecord objects.
        
        Args:
            response: API response from get_trades
            pool_id: Pool identifier
            
        Returns:
            List of TradeRecord objects
        """
        records = []
        
        print("-_parse_trade_response--")
        
        try:
            data = response.get("data", [])
            
            if not isinstance(data, list):
                logger.warning(f"Expected list in trade response for pool {pool_id}")
                return records
            
            for trade_data in data:
                try:
                    record = self._parse_trade_entry(trade_data, pool_id)
                    if record:
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing trade entry for pool {pool_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing trade response for pool {pool_id}: {e}")
        
        return records
    
    def _parse_trade_entry(self, trade_data: Dict, pool_id: str) -> Optional[TradeRecord]:
        """
        Parse individual trade entry into TradeRecord object.
        
        Args:
            trade_data: Individual trade data dictionary
            pool_id: Pool identifier
            
        Returns:
            TradeRecord object or None if parsing fails
        """
        try:
            # Extract trade ID
            trade_id = trade_data.get("id")
            if not trade_id:
                logger.warning(f"Trade missing ID for pool {pool_id}")
                return None            

            # Extract required fields
            block_number = trade_data.get("block_number")
            tx_hash = trade_data.get("tx_hash")
            tx_from_address = trade_data.get("tx_from_address")
            from_token_amount = trade_data.get("from_token_amount")
            to_token_amount = trade_data.get("to_token_amount")
            block_timestamp = trade_data.get("block_timestamp")
            side = trade_data.get("kind", trade_data.get("side", "buy"))
            
            # Parse numeric values
            try:
                from_token_amount = Decimal(str(from_token_amount)) if from_token_amount else Decimal('0')
                to_token_amount = Decimal(str(to_token_amount)) if to_token_amount else Decimal('0')
                
                # Calculate price and volume from available data
                price_usd = self._extract_price_usd(trade_data)
                volume_usd = self._calculate_volume_usd(trade_data, from_token_amount, to_token_amount, price_usd)
                
            except (ValueError, TypeError, InvalidOperation) as e:
                logger.warning(f"Error parsing numeric values for trade {trade_id}: {e}")
                return None
            
            # Parse timestamp
            try:
                if isinstance(block_timestamp, str):
                    # Handle ISO format timestamp
                    if 'T' in block_timestamp:
                        block_timestamp = datetime.fromisoformat(block_timestamp.replace('Z', '+00:00'))
                        # Convert to naive datetime for consistency
                        block_timestamp = block_timestamp.replace(tzinfo=None)
                    else:
                        # Try parsing as timestamp
                        block_timestamp = datetime.fromtimestamp(float(block_timestamp))
                elif isinstance(block_timestamp, (int, float)):
                    block_timestamp = datetime.fromtimestamp(block_timestamp)
                else:
                    logger.warning(f"Invalid timestamp format for trade {trade_id}: {block_timestamp}")
                    return None
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing timestamp for trade {trade_id}: {e}")
                return None
            
            # Validate required fields
            if not all([block_number, tx_hash]):
                logger.warning(f"Trade {trade_id} missing required fields")
                return None
            
            # Validate trade age (within 24 hours as per API constraints)
            now = datetime.now()
            if block_timestamp < now - timedelta(hours=self.max_trade_age_hours):
                logger.debug(f"Trade {trade_id} is older than {self.max_trade_age_hours} hours, skipping")
                return None
            
            return TradeRecord(
                id=trade_id,
                pool_id=pool_id,
                block_number=int(block_number),
                tx_hash=tx_hash,
                tx_from_address=tx_from_address,
                from_token_amount=from_token_amount,
                to_token_amount=to_token_amount,
                price_usd=price_usd,
                volume_usd=volume_usd,
                side=side,
                block_timestamp=block_timestamp
            )
            
        except Exception as e:
            logger.warning(f"Error parsing trade entry for pool {pool_id}: {e}")
            return None
    
    def _extract_price_usd(self, attributes: Dict) -> Decimal:
        """
        Extract USD price from trade attributes.
        
        Args:
            attributes: Trade attributes dictionary
            
        Returns:
            USD price as Decimal
        """
        # Try different price fields in order of preference
        price_fields = [
            "price_from_in_usd",
            "price_to_in_usd", 
            "price_usd",
            "price_from_in_currency_token",
            "price_to_in_currency_token"
        ]
        
        for field in price_fields:
            price_value = attributes.get(field)
            if price_value is not None:
                try:
                    return Decimal(str(price_value))
                except (ValueError, TypeError, InvalidOperation):
                    continue
        
        return Decimal('0')
    
    def _calculate_volume_usd(
        self, 
        attributes: Dict, 
        from_token_amount: Decimal, 
        to_token_amount: Decimal, 
        price_usd: Decimal
    ) -> Decimal:
        """
        Calculate USD volume from trade data.
        
        Args:
            attributes: Trade attributes dictionary
            from_token_amount: Amount of from token
            to_token_amount: Amount of to token
            price_usd: USD price
            
        Returns:
            USD volume as Decimal
        """
        # First try to get volume directly from attributes
        volume_usd = attributes.get("volume_usd")
        if volume_usd is not None:
            try:
                return Decimal(str(volume_usd))
            except (ValueError, TypeError, InvalidOperation):
                pass
        
        # Calculate volume from token amounts and price
        if price_usd > 0:
            # Use the larger of the two token amounts for volume calculation
            max_amount = max(from_token_amount, to_token_amount)
            return max_amount * price_usd
        
        return Decimal('0')
    
    def _filter_trades_by_volume(self, trades: List[TradeRecord]) -> List[TradeRecord]:
        """
        Filter trades by minimum USD volume threshold.
        
        Args:
            trades: List of trade records to filter
            
        Returns:
            Filtered list of trade records
        """
        filtered_trades = []
        
        for trade in trades:
            if trade.volume_usd >= Decimal(str(self.min_trade_volume_usd)):
                filtered_trades.append(trade)
            else:
                logger.debug(
                    f"Filtering out trade {trade.id} with volume ${trade.volume_usd} "
                    f"< threshold ${self.min_trade_volume_usd}"
                )
        
        logger.debug(
            f"Filtered {len(filtered_trades)} trades from {len(trades)} total "
            f"(volume >= ${self.min_trade_volume_usd})"
        )
        
        return filtered_trades
    
    async def _validate_trade_data(self, records: List[TradeRecord]) -> ValidationResult:
        """
        Validate trade data before storage.
        
        Args:
            records: List of trade records to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not records:
            warnings.append("No trade records to validate")
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        # Check for duplicate trade IDs within the batch
        trade_ids = set()
        duplicate_count = 0
        for record in records:
            if record.id in trade_ids:
                duplicate_count += 1
                if duplicate_count <= 3:  # Only log first few duplicates
                    warnings.append(f"Duplicate trade ID in batch: {record.id}")
            trade_ids.add(record.id)
        if duplicate_count > 3:
            warnings.append(f"Found {duplicate_count} total duplicate trade IDs in batch")
        
        # Validate individual records
        for record in records:
            # Check trade ID is present
            if not record.id:
                errors.append("Trade record missing ID")
            
            # Check pool ID is present
            if not record.pool_id:
                if record.id:
                    errors.append(f"Trade {record.id} missing pool ID")
                else:
                    errors.append("Trade record missing pool ID")
            
            # Skip further validation if critical fields are missing
            if not record.id:
                continue
            
            # Check timestamp is reasonable (not too far in future or past)
            now = datetime.now()
            if record.block_timestamp > now + timedelta(hours=1):
                warnings.append(
                    f"Future timestamp detected: {record.block_timestamp} for trade {record.id}"
                )
            
            # Check for very old data (more than 24 hours as per API constraints)
            if record.block_timestamp < now - timedelta(hours=self.max_trade_age_hours):
                warnings.append(
                    f"Old timestamp detected: {record.block_timestamp} for trade {record.id}"
                )
            
            # Check volume meets minimum threshold
            if record.volume_usd < Decimal(str(self.min_trade_volume_usd)):
                warnings.append(
                    f"Trade {record.id} volume ${record.volume_usd} below threshold "
                    f"${self.min_trade_volume_usd}"
                )
            
            # Check volume is non-negative
            if record.volume_usd < 0:
                errors.append(f"Negative volume detected: ${record.volume_usd} for trade {record.id}")
            
            # Check price is non-negative
            if record.price_usd < 0:
                errors.append(f"Negative price detected: ${record.price_usd} for trade {record.id}")
            
            # Check token amounts are non-negative
            if record.from_token_amount < 0 or record.to_token_amount < 0:
                errors.append(f"Negative token amount for trade {record.id}")
            
            # Check side is valid
            if record.side and record.side not in ['buy', 'sell']:
                warnings.append(f"Invalid trade side '{record.side}' for trade {record.id}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def _validate_specific_data(self, data) -> Optional[ValidationResult]:
        """
        Validate collected trade data.
        
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
                warnings.append("No active watchlist pools found for trade validation")
                return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
            
            # Check data availability for each pool
            for pool_id in watchlist_pools:
                # Check if we have recent trade data
                recent_data = await self.db_manager.get_trade_data(
                    pool_id=pool_id,
                    start_time=datetime.now() - timedelta(hours=2),
                    end_time=datetime.now(),
                    min_volume_usd=self.min_trade_volume_usd
                )
                
                if not recent_data:
                    warnings.append(f"No recent trade data for pool {pool_id}")
            
        except Exception as e:
            errors.append(f"Trade validation error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def get_collection_status(self) -> Dict[str, any]:
        """
        Get current status of trade collection.
        
        Returns:
            Dictionary with collection status information
        """
        try:
            watchlist_pools = await self.db_manager.get_watchlist_pools()
            
            # Count pools with trade data
            pools_with_data = 0
            total_records = 0
            
            for pool_id in watchlist_pools:
                recent_data = await self.db_manager.get_trade_data(
                    pool_id=pool_id,
                    start_time=datetime.now() - timedelta(hours=24),
                    end_time=datetime.now(),
                    min_volume_usd=self.min_trade_volume_usd
                )
                
                if recent_data:
                    pools_with_data += 1
                    total_records += len(recent_data)
            
            coverage_percentage = (
                (pools_with_data / len(watchlist_pools) * 100) 
                if watchlist_pools else 0
            )
            
            return {
                "total_watchlist_pools": len(watchlist_pools),
                "pools_with_trade_data": pools_with_data,
                "coverage_percentage": coverage_percentage,
                "total_recent_records": total_records,
                "min_volume_threshold_usd": self.min_trade_volume_usd,
                "max_trade_age_hours": self.max_trade_age_hours
            }
            
        except Exception as e:
            logger.error(f"Error getting trade collection status: {e}")
            return {
                "error": str(e)
            }
    
    async def verify_data_continuity(self, pool_id: str) -> Dict[str, any]:
        """
        Verify trade data continuity for a pool within the 24-hour API window.
        
        Args:
            pool_id: Pool identifier to check continuity for
            
        Returns:
            Dictionary with continuity information
        """
        try:
            # Check trade data for the last 24 hours (API constraint)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            
            # Get trade data for the period
            trades = await self.db_manager.get_trade_data(
                pool_id=pool_id,
                start_time=start_time,
                end_time=end_time,
                min_volume_usd=self.min_trade_volume_usd
            )
            
            # Analyze trade distribution
            if not trades:
                return {
                    "pool_id": pool_id,
                    "has_trades": False,
                    "trade_count": 0,
                    "time_span_hours": 24,
                    "data_quality": "no_data"
                }
            
            # Calculate time gaps between trades
            trade_times = sorted([trade.block_timestamp for trade in trades])
            gaps = []
            
            for i in range(1, len(trade_times)):
                gap_duration = trade_times[i] - trade_times[i-1]
                if gap_duration > timedelta(hours=1):  # Consider gaps > 1 hour significant
                    gaps.append({
                        "start": trade_times[i-1],
                        "end": trade_times[i],
                        "duration_hours": gap_duration.total_seconds() / 3600
                    })
            
            # Calculate data quality score
            total_volume = sum(trade.volume_usd for trade in trades)
            avg_volume = total_volume / len(trades) if trades else Decimal('0')
            
            # Simple quality score based on trade frequency and volume
            quality_score = min(1.0, len(trades) / 100.0)  # Normalize by expected trade count
            
            return {
                "pool_id": pool_id,
                "has_trades": True,
                "trade_count": len(trades),
                "time_span_hours": 24,
                "total_volume_usd": float(total_volume),
                "average_volume_usd": float(avg_volume),
                "significant_gaps": len(gaps),
                "gaps": gaps[:5],  # Return first 5 gaps
                "data_quality_score": quality_score,
                "data_quality": "good" if quality_score > 0.7 else "fair" if quality_score > 0.3 else "poor"
            }
            
        except Exception as e:
            logger.error(f"Error verifying trade data continuity for pool {pool_id}: {e}")
            return {
                "pool_id": pool_id,
                "error": str(e)
            }
    
    async def detect_trade_data_gaps(self, pool_id: str) -> List[Gap]:
        """
        Detect gaps in trade data within the 24-hour API window constraints.
        
        Args:
            pool_id: Pool identifier to check for gaps
            
        Returns:
            List of Gap objects representing missing data periods
        """
        try:
            # Define the 24-hour window (API constraint)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            
            print("---TradeCollector---")

            database_id = "solana_"+pool_id

            # Get existing trade data for the period
            trades = await self.db_manager.get_trade_data(
                pool_id=database_id,
                start_time=start_time,
                end_time=end_time,
                min_volume_usd=self.min_trade_volume_usd
            )
            
            gaps = []
            
            if not trades:
                # No trades found - entire period is a gap
                gaps.append(Gap(
                    start_time=start_time,
                    end_time=end_time,
                    pool_id=database_id,
                    timeframe="trade_data",
                    duration_hours=24.0,
                    gap_type="no_data",
                    severity="high"
                ))
                return gaps
            
            # Sort trades by timestamp
            sorted_trades = sorted(trades, key=lambda t: t.block_timestamp)
            
            # Check for gap at the beginning
            first_trade_time = sorted_trades[0].block_timestamp
            if first_trade_time > start_time + timedelta(hours=self.significant_gap_threshold_hours):
                gap_duration = (first_trade_time - start_time).total_seconds() / 3600
                gaps.append(Gap(
                    start_time=start_time,
                    end_time=first_trade_time,
                    pool_id=database_id,
                    timeframe="trade_data",
                    duration_hours=gap_duration,
                    gap_type="beginning_gap",
                    severity="medium" if gap_duration > 4 else "low"
                ))
            
            # Check for gaps between trades
            for i in range(1, len(sorted_trades)):
                prev_trade = sorted_trades[i-1]
                curr_trade = sorted_trades[i]
                
                time_diff = curr_trade.block_timestamp - prev_trade.block_timestamp
                gap_hours = time_diff.total_seconds() / 3600
                
                # Consider gaps longer than threshold as significant
                if gap_hours > self.significant_gap_threshold_hours:
                    gaps.append(Gap(
                        start_time=prev_trade.block_timestamp,
                        end_time=curr_trade.block_timestamp,
                        pool_id=database_id,
                        timeframe="trade_data",
                        duration_hours=gap_hours,
                        gap_type="data_gap",
                        severity="high" if gap_hours > 6 else "medium"
                    ))
            
            # Check for gap at the end
            last_trade_time = sorted_trades[-1].block_timestamp
            if last_trade_time < end_time - timedelta(hours=self.significant_gap_threshold_hours):
                gap_duration = (end_time - last_trade_time).total_seconds() / 3600
                gaps.append(Gap(
                    start_time=last_trade_time,
                    end_time=end_time,
                    pool_id=database_id,
                    timeframe="trade_data",
                    duration_hours=gap_duration,
                    gap_type="ending_gap",
                    severity="high" if gap_duration > 4 else "medium"
                ))
            
            logger.debug(f"Found {len(gaps)} gaps in trade data for pool {pool_id}")
            return gaps
            
        except Exception as e:
            logger.error(f"Error detecting trade data gaps for pool {pool_id}: {e}")
            return []
    
    async def prioritize_pools_by_activity(self, pool_ids: List[str]) -> List[Tuple[str, float]]:
        """
        Prioritize pools based on volume and trading activity.
        
        Args:
            pool_ids: List of pool identifiers to prioritize
            
        Returns:
            List of tuples (pool_id, priority_score) sorted by priority (highest first)
        """
        pool_priorities = []
        
        try:                        
            # Calculate priority for each pool
            for pool_id in pool_ids:

                normalized_pool_id = DataTypeNormalizer.remove_prefix(pool_id)
                priority_score = await self._calculate_pool_priority(normalized_pool_id)
                pool_priorities.append((pool_id, priority_score))
                self._pool_priorities[pool_id] = priority_score
            
            # Sort by priority score (highest first)
            pool_priorities.sort(key=lambda x: x[1], reverse=True)
            
            logger.debug(f"Prioritized {len(pool_priorities)} pools by activity")
            return pool_priorities
            
        except Exception as e:
            logger.error(f"Error prioritizing pools by activity: {e}")
            # Return original order with default priority
            return [(pool_id, 1.0) for pool_id in pool_ids]
    
    async def _calculate_pool_priority(self, pool_id: str) -> float:
        """
        Calculate priority score for a pool based on volume and activity.
        
        Args:
            pool_id: Pool identifier
            
        Returns:
            Priority score (higher = more priority)
        """
        try:
            # Get recent trade data (last 4 hours for activity assessment)
            recent_end = datetime.now()
            recent_start = recent_end - timedelta(hours=4)
            
            recent_trades = await self.db_manager.get_trade_data(
                pool_id=pool_id,
                start_time=recent_start,
                end_time=recent_end,
                min_volume_usd=self.min_trade_volume_usd
            )
            
            # Get 24-hour trade data for volume assessment
            day_start = recent_end - timedelta(hours=24)
            day_trades = await self.db_manager.get_trade_data(
                pool_id=pool_id,
                start_time=day_start,
                end_time=recent_end,
                min_volume_usd=self.min_trade_volume_usd
            )
            
            # Calculate volume-based score
            total_volume_24h = sum(trade.volume_usd for trade in day_trades)
            volume_score = min(float(total_volume_24h) / self.high_volume_threshold_usd, 2.0)
            
            # Calculate activity-based score (trade frequency)
            trade_count_4h = len(recent_trades)
            activity_score = min(trade_count_4h / 20.0, 2.0)  # Normalize to max 2.0
            
            # Calculate recency score (when was last collection)
            recency_score = 1.0
            if pool_id in self._last_collection_times:
                time_since_last = recent_end - self._last_collection_times[pool_id]
                hours_since = time_since_last.total_seconds() / 3600
                # Higher score for pools not collected recently
                recency_score = min(hours_since / 2.0, 2.0)
            
            # Calculate data quality score (fewer gaps = higher priority)
            database_id = self.network+"_"+pool_id

            gaps = await self.detect_trade_data_gaps(database_id)
            gap_penalty = len([g for g in gaps if g.severity in ['high', 'medium']]) * 0.2
            quality_score = max(1.0 - gap_penalty, 0.1)
            
            # Combine scores with weights
            priority_score = (
                volume_score * 0.4 +      # 40% weight on volume
                activity_score * 0.3 +    # 30% weight on activity
                recency_score * 0.2 +     # 20% weight on recency
                quality_score * 0.1       # 10% weight on data quality
            )
            
            logger.debug(
                f"Pool {pool_id} priority: {priority_score:.2f} "
                f"(vol: {volume_score:.2f}, act: {activity_score:.2f}, "
                f"rec: {recency_score:.2f}, qual: {quality_score:.2f})"
            )
            
            return priority_score
            
        except Exception as e:
            logger.warning(f"Error calculating priority for pool {pool_id}: {e}")
            return 1.0  # Default priority
    
    async def implement_fair_rotation(self, pool_ids: List[str]) -> List[str]:
        """
        Implement fair rotation logic for high-volume pools when API limits are reached.
        
        Args:
            pool_ids: List of pool identifiers to rotate
            
        Returns:
            Reordered list of pool IDs based on fair rotation logic
        """
        try:
            current_time = datetime.now()
            
            # Check if we need to reset rotation window
            if (current_time - self._rotation_start_time).total_seconds() > (self.rotation_window_minutes * 60):
                self._rotation_start_time = current_time
                self._api_call_count = 0
                logger.debug("Reset rotation window")
            
            # Get prioritized pools
            prioritized_pools = await self.prioritize_pools_by_activity(pool_ids)
            
            # Separate high-volume and regular pools
            high_volume_pools = []
            regular_pools = []
            
            for pool_id, priority in prioritized_pools:
                if priority >= 2.0:  # High priority threshold
                    high_volume_pools.append(pool_id)
                else:
                    regular_pools.append(pool_id)
            
            # Implement rotation for high-volume pools
            rotated_pools = []
            
            # Always include some high-volume pools
            if high_volume_pools:
                # Rotate high-volume pools based on last collection time
                high_volume_with_times = []
                for pool_id in high_volume_pools:
                    last_time = self._last_collection_times.get(pool_id, datetime.min)
                    high_volume_with_times.append((pool_id, last_time))
                
                # Sort by last collection time (oldest first for fair rotation)
                high_volume_with_times.sort(key=lambda x: x[1])
                
                # Take a portion of high-volume pools based on API capacity
                max_high_volume = max(1, len(high_volume_pools) // 2)
                selected_high_volume = [pool_id for pool_id, _ in high_volume_with_times[:max_high_volume]]
                rotated_pools.extend(selected_high_volume)
            
            # Add regular pools
            rotated_pools.extend(regular_pools)
            
            # Limit total pools if approaching API limits
            if self._api_call_count > (100 * self.api_rate_limit_threshold):  # Assuming 100 calls per window
                max_pools = max(5, len(pool_ids) // 2)  # Reduce to half but minimum 5
                rotated_pools = rotated_pools[:max_pools]
                logger.info(f"Reduced pool collection to {len(rotated_pools)} due to API rate limits")
            
            logger.debug(
                f"Fair rotation: {len(high_volume_pools)} high-volume, "
                f"{len(regular_pools)} regular, {len(rotated_pools)} selected"
            )
            
            return rotated_pools
            
        except Exception as e:
            logger.error(f"Error implementing fair rotation: {e}")
            return pool_ids  # Return original order on error
    
    async def verify_and_recover_continuity(self, pool_ids: List[str]) -> Dict[str, any]:
        """
        Verify trade data continuity and attempt recovery for gaps.
        
        Args:
            pool_ids: List of pool identifiers to verify
            
        Returns:
            Dictionary with continuity verification results and recovery actions
        """
        results = {
            "pools_checked": len(pool_ids),
            "pools_with_gaps": 0,
            "total_gaps_found": 0,
            "recovery_attempts": 0,
            "recovery_successes": 0,
            "pool_details": {}
        }
        
        try:
            for pool_id in pool_ids:
                # Detect gaps for this pool
                gaps = await self.detect_trade_data_gaps(pool_id)
                
                pool_result = {
                    "gaps_found": len(gaps),
                    "gaps": [
                        {
                            "start": gap.start_time.isoformat(),
                            "end": gap.end_time.isoformat(),
                            "duration_hours": gap.duration_hours,
                            "type": gap.gap_type,
                            "severity": gap.severity
                        }
                        for gap in gaps
                    ],
                    "recovery_attempted": False,
                    "recovery_successful": False
                }
                
                if gaps:
                    results["pools_with_gaps"] += 1
                    results["total_gaps_found"] += len(gaps)
                    
                    # Attempt recovery for significant gaps
                    high_severity_gaps = [g for g in gaps if g.severity == "high"]
                    if high_severity_gaps:
                        try:
                            results["recovery_attempts"] += 1
                            pool_result["recovery_attempted"] = True
                            
                            # Attempt to collect data for the gap period
                            recovery_success = await self._attempt_gap_recovery(pool_id, high_severity_gaps)
                            
                            if recovery_success:
                                results["recovery_successes"] += 1
                                pool_result["recovery_successful"] = True
                                logger.info(f"Successfully recovered data for pool {pool_id}")
                            
                        except Exception as e:
                            logger.warning(f"Gap recovery failed for pool {pool_id}: {e}")
                
                results["pool_details"][pool_id] = pool_result
                
                # Update last collection time
                self._last_collection_times[pool_id] = datetime.now()
            
            logger.info(
                f"Continuity verification complete: {results['pools_with_gaps']}/{results['pools_checked']} "
                f"pools have gaps, {results['recovery_successes']}/{results['recovery_attempts']} recoveries successful"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in continuity verification: {e}")
            results["error"] = str(e)
            return results
    
    async def _attempt_gap_recovery(self, pool_id: str, gaps: List[Gap]) -> bool:
        """
        Attempt to recover data for detected gaps.
        
        Args:
            pool_id: Pool identifier
            gaps: List of gaps to attempt recovery for
            
        Returns:
            True if recovery was successful, False otherwise
        """
        try:
            # Only attempt recovery for recent gaps (within API window)
            current_time = datetime.now()
            recoverable_gaps = [
                gap for gap in gaps 
                if (current_time - gap.start_time).total_seconds() < (24 * 3600)  # Within 24 hours
            ]
            
            if not recoverable_gaps:
                logger.debug(f"No recoverable gaps found for pool {pool_id}")
                return False
            
            # Attempt to collect fresh data
            fresh_records = await self._collect_pool_trade_data(pool_id)
            
            if fresh_records > 0:
                logger.info(f"Recovered {fresh_records} trade records for pool {pool_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Gap recovery attempt failed for pool {pool_id}: {e}")
            return False
    
    async def detect_trade_data_gaps(self, pool_id: str) -> List[Gap]:
        """
        Detect gaps in trade data for a specific pool.
        
        Args:
            pool_id: Pool identifier to check for gaps
            
        Returns:
            List of Gap objects representing data gaps
        """
        try:
            # Get trade data for the last 24 hours
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            
            trades = await self.db_manager.get_trade_data(
                pool_id=pool_id,
                start_time=start_time,
                end_time=end_time,
                min_volume_usd=self.min_trade_volume_usd
            )
            
            gaps = []
            
            if not trades:
                # No data gap
                gaps.append(Gap(
                    pool_id=pool_id,
                    start_time=start_time,
                    end_time=end_time,
                    duration_hours=24.0,
                    gap_type="no_data",
                    severity="high"
                ))
                return gaps
            
            # Sort trades by timestamp
            sorted_trades = sorted(trades, key=lambda t: t.block_timestamp)
            
            # Check for gaps between trades
            for i in range(1, len(sorted_trades)):
                gap_duration = sorted_trades[i].block_timestamp - sorted_trades[i-1].block_timestamp
                gap_hours = gap_duration.total_seconds() / 3600
                
                if gap_hours > self.significant_gap_threshold_hours:
                    gaps.append(Gap(
                        pool_id=pool_id,
                        start_time=sorted_trades[i-1].block_timestamp,
                        end_time=sorted_trades[i].block_timestamp,
                        duration_hours=gap_hours,
                        gap_type="data_gap",
                        severity="high" if gap_hours > 6 else "medium"
                    ))
            
            return gaps
            
        except Exception as e:
            logger.warning(f"Error detecting gaps for pool {pool_id}: {e}")
            return []
    
    async def prioritize_pools_by_activity(self, pool_ids: List[str]) -> List[Tuple[str, float]]:
        """
        Prioritize pools based on trading activity and volume.
        
        Args:
            pool_ids: List of pool identifiers to prioritize
            
        Returns:
            List of tuples (pool_id, priority_score) sorted by priority
        """
        try:
            pool_priorities = []
            
            for pool_id in pool_ids:
                # Get recent trade data
                recent_trades = await self.db_manager.get_trade_data(
                    pool_id=pool_id,
                    start_time=datetime.now() - timedelta(minutes=self.rotation_window_minutes),
                    end_time=datetime.now(),
                    min_volume_usd=self.min_trade_volume_usd
                )
                
                # Calculate priority score based on activity and volume
                trade_count = len(recent_trades)
                total_volume = sum(trade.volume_usd for trade in recent_trades)
                avg_volume = total_volume / trade_count if trade_count > 0 else Decimal('0')
                
                # Check for gaps
                gaps = await self.detect_trade_data_gaps(pool_id)
                gap_penalty = len([g for g in gaps if g.severity == "high"]) * 0.5
                
                # Calculate priority score
                activity_score = min(trade_count / 50.0, 1.0)  # Normalize to 0-1
                volume_score = min(float(avg_volume) / self.high_volume_threshold_usd, 1.0)
                priority = (activity_score + volume_score) - gap_penalty
                
                pool_priorities.append((pool_id, max(priority, 0.1)))  # Minimum priority
            
            # Sort by priority (highest first)
            return sorted(pool_priorities, key=lambda x: x[1], reverse=True)
            
        except Exception as e:
            logger.warning(f"Error prioritizing pools: {e}")
            return [(pool_id, 1.0) for pool_id in pool_ids]
    
    async def implement_fair_rotation(self, pool_ids: List[str]) -> List[str]:
        """
        Implement fair rotation for pool selection based on API rate limits.
        
        Args:
            pool_ids: List of all available pool identifiers
            
        Returns:
            List of selected pool identifiers for this collection cycle
        """
        try:
            # Get pool priorities
            prioritized_pools = await self.prioritize_pools_by_activity(pool_ids)
            
            # Calculate how many pools we can process based on rate limits
            max_pools = min(len(pool_ids), 10)  # Conservative limit
            
            # Select top priority pools
            selected_pools = [pool_id for pool_id, _ in prioritized_pools[:max_pools]]
            
            logger.debug(f"Fair rotation selected {len(selected_pools)} pools from {len(pool_ids)} total")
            
            return selected_pools
            
        except Exception as e:
            logger.warning(f"Error in fair rotation: {e}")
            return pool_ids[:5]  # Fallback to first 5 pools
    
    async def verify_and_recover_continuity(self, pool_ids: List[str]) -> Dict[str, any]:
        """
        Verify data continuity and attempt recovery for gaps.
        
        Args:
            pool_ids: List of pool identifiers to verify
            
        Returns:
            Dictionary with continuity verification results
        """
        try:
            results = {
                "pools_checked": len(pool_ids),
                "pools_with_gaps": 0,
                "total_gaps_found": 0,
                "recovery_attempts": 0,
                "recovery_successes": 0,
                "pool_details": {}
            }
            
            for pool_id in pool_ids:
                # Detect gaps
                gaps = await self.detect_trade_data_gaps(pool_id)
                
                pool_details = {
                    "gaps_found": len(gaps),
                    "recovery_attempted": False,
                    "recovery_successful": False
                }
                
                if gaps:
                    results["pools_with_gaps"] += 1
                    results["total_gaps_found"] += len(gaps)
                    
                    # Attempt recovery for significant gaps
                    significant_gaps = [g for g in gaps if g.severity == "high"]
                    if significant_gaps:
                        results["recovery_attempts"] += 1
                        pool_details["recovery_attempted"] = True
                        
                        recovery_success = await self._attempt_gap_recovery(pool_id, significant_gaps)
                        if recovery_success:
                            results["recovery_successes"] += 1
                            pool_details["recovery_successful"] = True
                
                results["pool_details"][pool_id] = pool_details
            
            return results
            
        except Exception as e:
            logger.warning(f"Error in continuity verification: {e}")
            return {
                "pools_checked": len(pool_ids),
                "pools_with_gaps": 0,
                "total_gaps_found": 0,
                "recovery_attempts": 0,
                "recovery_successes": 0,
                "pool_details": {}
            }