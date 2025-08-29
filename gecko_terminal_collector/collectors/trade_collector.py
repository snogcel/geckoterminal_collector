"""
Trade data collector.

This module provides functionality to collect trade data for watchlist tokens
with volume filtering, configurable minimum USD volume thresholds, duplicate
prevention using trade IDs and composite keys.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import (
    CollectionResult, TradeRecord, ValidationResult
)
from gecko_terminal_collector.utils.metadata import MetadataTracker

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
        use_mock: bool = False
    ):
        """
        Initialize the trade collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        self.network = config.dexes.network
        
        # Trade collection settings
        self.min_trade_volume_usd = getattr(config.thresholds, 'min_trade_volume_usd', 100.0)
        self.trade_limit = getattr(config, 'trade_limit', 300)  # Max trades per API call
        
        # Track errors during collection
        self._collection_errors = []
        
        # Trade data validation settings
        self.max_trade_age_hours = getattr(config, 'max_trade_age_hours', 24)
        
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "trade_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect trade data for watchlist tokens.
        
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
            
            # Collect trade data for each pool
            for pool_id in watchlist_pools:
                try:
                    pool_records = await self._collect_pool_trade_data(pool_id)
                    records_collected += pool_records
                    
                except Exception as e:
                    error_msg = f"Error collecting trade data for pool {pool_id}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
            
            logger.info(
                f"Trade collection completed: {records_collected} records collected "
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
            
            # Get trade data from API
            response = await self.client.get_trades(
                network=self.network,
                pool_address=pool_id,
                trade_volume_filter=self.min_trade_volume_usd
            )
            
            # Parse and validate trade data
            trade_records = self._parse_trade_response(response, pool_id)
            
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
            
            # Extract attributes
            attributes = trade_data.get("attributes", {})
            
            # Extract required fields
            block_number = attributes.get("block_number")
            tx_hash = attributes.get("tx_hash")
            tx_from_address = attributes.get("tx_from_address")
            from_token_amount = attributes.get("from_token_amount")
            to_token_amount = attributes.get("to_token_amount")
            block_timestamp = attributes.get("block_timestamp")
            side = attributes.get("kind", attributes.get("side", "buy"))
            
            # Parse numeric values
            try:
                from_token_amount = Decimal(str(from_token_amount)) if from_token_amount else Decimal('0')
                to_token_amount = Decimal(str(to_token_amount)) if to_token_amount else Decimal('0')
                
                # Calculate price and volume from available data
                price_usd = self._extract_price_usd(attributes)
                volume_usd = self._calculate_volume_usd(attributes, from_token_amount, to_token_amount, price_usd)
                
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