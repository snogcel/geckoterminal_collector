"""
Top pools monitoring collector for fetching and storing top pools by DEX.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..models.core import CollectionResult, ValidationResult, Pool
from ..config.models import CollectionConfig
from ..database.manager import DatabaseManager
from .base import BaseDataCollector

logger = logging.getLogger(__name__)


class TopPoolsCollector(BaseDataCollector):
    """
    Collector for monitoring top pools by network and DEX.
    
    Fetches top pool information from the GeckoTerminal API for specific DEXes
    (heaven and pumpswap) and stores it in the database with volume and liquidity
    tracking. Supports configurable monitoring intervals and scheduler integration.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        network: str = "solana",
        target_dexes: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize the top pools collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            network: Network to monitor (default: solana)
            target_dexes: List of target DEX IDs to monitor (default: ["heaven", "pumpswap"])
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(config, db_manager, **kwargs)
        self.network = network
        self.target_dexes = target_dexes or ["heaven", "pumpswap"]
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        network = getattr(self, 'network', 'solana')
        return f"top_pools_{network}"
    
    async def collect(self) -> CollectionResult:
        """
        Collect top pools data from the API and store it in the database.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        total_records_collected = 0
        
        try:
            logger.info(f"Starting top pools collection for network: {self.network}")
            
            # Collect pools for each target DEX
            for dex_id in self.target_dexes:
                try:
                    logger.info(f"Collecting top pools for DEX: {dex_id}")
                    
                    # Fetch top pools data from API
                    pools_data = await self.client.get_top_pools_by_network_dex(
                        self.network, dex_id
                    )
                    
                    if pools_data is None:
                        error_msg = f"No pools data returned for DEX: {dex_id}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    # Validate the data
                    validation_result = await self.validate_data(pools_data)
                    if not validation_result.is_valid:
                        errors.extend([f"DEX {dex_id}: {error}" for error in validation_result.errors])
                        logger.error(f"Pools data validation failed for {dex_id}: {validation_result.errors}")
                        continue
                    
                    # Log any validation warnings
                    if validation_result.warnings:
                        for warning in validation_result.warnings:
                            logger.warning(f"DEX {dex_id} pools data validation warning: {warning}")
                    
                    # Process and store pools data
                    pool_records = self._process_pools_data(pools_data, dex_id)
                    stored_count = await self._store_pools_data(pool_records)
                    total_records_collected += stored_count
                    
                    logger.info(f"Processed {stored_count} pools for DEX: {dex_id}")
                    
                except Exception as e:
                    error_msg = f"Error collecting pools for DEX {dex_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
                    continue
            
            logger.info(
                f"Top pools collection completed: {total_records_collected} pools processed, "
                f"{len(errors)} errors"
            )
            
            # Return result based on whether we had errors
            if errors:
                return self.create_failure_result(errors, total_records_collected, start_time)
            else:
                return self.create_success_result(total_records_collected, start_time)
                
        except Exception as e:
            error_msg = f"Unexpected error during top pools collection: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return self.create_failure_result(errors, total_records_collected, start_time)
    
    async def _validate_specific_data(self, data: Any) -> Optional[ValidationResult]:
        """
        Validate top pools specific data structure.
        
        Args:
            data: Pools data to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not isinstance(data, dict):
            errors.append("Pools data must be a dictionary")
            return ValidationResult(False, errors, warnings)
        
        # Check for data field
        if "data" not in data:
            # If no data field, treat as empty data (valid but with warning)
            warnings.append("No pools found in response")
            return ValidationResult(True, errors, warnings)
        
        pools_list = data.get("data", [])
        if not isinstance(pools_list, list):
            errors.append("Pools data must contain a 'data' field with a list")
            return ValidationResult(False, errors, warnings)
        
        if len(pools_list) == 0:
            warnings.append("No pools found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each pool entry
        for i, pool in enumerate(pools_list):
            if not isinstance(pool, dict):
                errors.append(f"Pool entry {i} must be a dictionary")
                continue
            
            # Check required fields
            if "id" not in pool:
                errors.append(f"Pool entry {i} missing required 'id' field")
            
            if "type" not in pool:
                errors.append(f"Pool entry {i} missing required 'type' field")
            elif pool["type"] != "pool":
                warnings.append(f"Pool entry {i} has unexpected type: {pool['type']}")
            
            # Check attributes
            attributes = pool.get("attributes", {})
            if not isinstance(attributes, dict):
                errors.append(f"Pool entry {i} attributes must be a dictionary")
            else:
                # Check required attributes
                required_attrs = ["name", "address"]
                for attr in required_attrs:
                    if attr not in attributes:
                        errors.append(f"Pool entry {i} missing required attribute: {attr}")
            
            # Check relationships
            relationships = pool.get("relationships", {})
            if not isinstance(relationships, dict):
                warnings.append(f"Pool entry {i} missing relationships data")
            else:
                # Check for DEX relationship
                if "dex" not in relationships:
                    warnings.append(f"Pool entry {i} missing DEX relationship")
                
                # Check for token relationships
                if "base_token" not in relationships:
                    warnings.append(f"Pool entry {i} missing base_token relationship")
                
                if "quote_token" not in relationships:
                    warnings.append(f"Pool entry {i} missing quote_token relationship")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def _process_pools_data(self, pools_data: Dict[str, Any], dex_id: str) -> List[Pool]:
        """
        Process raw pools data into database model objects.
        
        Args:
            pools_data: Raw pools data from API
            dex_id: DEX ID for the pools
            
        Returns:
            List of Pool model objects
        """
        pool_records = []
        pools_list = pools_data.get("data", [])
        
        for pool_data in pools_list:
            try:
                # Skip None or invalid entries
                if not pool_data or not isinstance(pool_data, dict):
                    logger.error(f"Invalid pool entry: {pool_data}")
                    continue
                
                # Extract pool information
                pool_id = pool_data.get("id")
                if not pool_id:
                    logger.error(f"Pool entry missing ID: {pool_data}")
                    continue
                
                attributes = pool_data.get("attributes", {})
                relationships = pool_data.get("relationships", {})
                
                # Extract basic pool info
                pool_name = attributes.get("name", "")
                pool_address = attributes.get("address", pool_id)
                
                # Extract financial data with safe conversion
                reserve_usd = self._safe_decimal_conversion(attributes.get("reserve_in_usd"))
                
                # Extract token relationships
                base_token_id = None
                quote_token_id = None
                
                base_token_rel = relationships.get("base_token", {}).get("data", {})
                if base_token_rel:
                    base_token_id = base_token_rel.get("id")
                
                quote_token_rel = relationships.get("quote_token", {}).get("data", {})
                if quote_token_rel:
                    quote_token_id = quote_token_rel.get("id")
                
                # Extract creation date
                created_at = None
                pool_created_at = attributes.get("pool_created_at")
                if pool_created_at:
                    try:
                        created_at = datetime.fromisoformat(pool_created_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Invalid pool creation date {pool_created_at}: {e}")
                
                # Create Pool record
                pool_record = Pool(
                    id=pool_id,
                    address=pool_address,
                    name=pool_name,
                    dex_id=dex_id,
                    base_token_id=base_token_id,
                    quote_token_id=quote_token_id,
                    reserve_usd=reserve_usd,
                    created_at=created_at
                )
                
                pool_records.append(pool_record)
                logger.debug(f"Processed pool: {pool_id} ({pool_name}) - Reserve: ${reserve_usd}")
                
            except Exception as e:
                logger.error(f"Error processing pool data {pool_data}: {e}")
                continue
        
        return pool_records
    
    def _safe_decimal_conversion(self, value: Any) -> Optional[Decimal]:
        """
        Safely convert a value to Decimal, handling various input types.
        
        Args:
            value: Value to convert
            
        Returns:
            Decimal value or None if conversion fails
        """
        if value is None or value == "":
            return None
        
        try:
            # Handle string values
            if isinstance(value, str):
                # Remove any non-numeric characters except decimal point and minus
                cleaned_value = ''.join(c for c in value if c.isdigit() or c in '.-')
                if not cleaned_value or cleaned_value in ['.', '-', '-.']:
                    return None
                return Decimal(cleaned_value)
            
            # Handle numeric values
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            
            # Try direct conversion
            return Decimal(str(value))
            
        except (ValueError, TypeError, ArithmeticError) as e:
            logger.warning(f"Failed to convert value to Decimal: {value} - {e}")
            return None
    
    async def _store_pools_data(self, pool_records: List[Pool]) -> int:
        """
        Store pool records in the database with upsert logic.
        
        Args:
            pool_records: List of Pool records to store
            
        Returns:
            Number of records stored/updated
        """
        if not pool_records:
            logger.info("No pool records to store")
            return 0
        
        try:
            # Use database manager to store pool data
            stored_count = await self.db_manager.store_pools(pool_records)
            logger.info(f"Stored/updated {stored_count} pool records")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing pool data: {e}")
            raise
    
    async def get_top_pools_by_dex(self, dex_id: str, limit: Optional[int] = None) -> List[Pool]:
        """
        Get top pools for a specific DEX from the database.
        
        Args:
            dex_id: DEX ID to filter by
            limit: Optional limit on number of pools to return
            
        Returns:
            List of Pool objects ordered by reserve USD (descending)
        """
        try:
            pools = await self.db_manager.get_pools_by_dex(dex_id)
            
            # Sort by reserve USD (descending) and apply limit
            sorted_pools = sorted(
                pools, 
                key=lambda p: p.reserve_usd or Decimal('0'), 
                reverse=True
            )
            
            if limit:
                sorted_pools = sorted_pools[:limit]
            
            return sorted_pools
            
        except Exception as e:
            logger.error(f"Error retrieving top pools for DEX {dex_id}: {e}")
            return []
    
    async def get_pool_statistics(self, dex_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about collected pools.
        
        Args:
            dex_id: Optional DEX ID to filter by
            
        Returns:
            Dictionary with pool statistics
        """
        try:
            stats = {
                "total_pools": 0,
                "total_reserve_usd": Decimal('0'),
                "dex_breakdown": {}
            }
            
            if dex_id:
                # Get stats for specific DEX
                pools = await self.db_manager.get_pools_by_dex(dex_id)
                stats["total_pools"] = len(pools)
                stats["total_reserve_usd"] = sum(
                    (pool.reserve_usd or Decimal('0')) for pool in pools
                )
                stats["dex_breakdown"][dex_id] = {
                    "pools": len(pools),
                    "reserve_usd": stats["total_reserve_usd"]
                }
            else:
                # Get stats for all target DEXes
                for target_dex in self.target_dexes:
                    pools = await self.db_manager.get_pools_by_dex(target_dex)
                    dex_reserve = sum((pool.reserve_usd or Decimal('0')) for pool in pools)
                    
                    stats["total_pools"] += len(pools)
                    stats["total_reserve_usd"] += dex_reserve
                    stats["dex_breakdown"][target_dex] = {
                        "pools": len(pools),
                        "reserve_usd": dex_reserve
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating pool statistics: {e}")
            return {
                "total_pools": 0,
                "total_reserve_usd": Decimal('0'),
                "dex_breakdown": {},
                "error": str(e)
            }