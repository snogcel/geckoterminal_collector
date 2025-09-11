"""
Example of integrating the error handling framework with existing collectors.

This script demonstrates how to modify existing collectors to use the
comprehensive error handling framework.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from gecko_terminal_collector.utils.error_handler import ErrorHandler, handle_errors
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.utils.enhanced_rate_limiter import EnhancedRateLimiter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedBaseCollector:
    """
    Enhanced base collector with integrated error handling.
    
    This shows how to modify existing collectors to use the error handling framework.
    """
    
    def __init__(
        self,
        db_manager: EnhancedDatabaseManager,
        rate_limiter: EnhancedRateLimiter,
        error_handler: Optional[ErrorHandler] = None
    ):
        self.db_manager = db_manager
        self.rate_limiter = rate_limiter
        self.error_handler = error_handler or ErrorHandler(db_manager)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def collect_with_error_handling(
        self,
        collection_method: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generic collection method with comprehensive error handling.
        
        Args:
            collection_method: Name of the collection method to call
            *args, **kwargs: Arguments to pass to the collection method
            
        Returns:
            Collection result with error handling metadata
        """
        start_time = datetime.now()
        execution_id = f"{self.__class__.__name__}_{collection_method}_{int(start_time.timestamp())}"
        
        try:
            # Get the collection method
            method = getattr(self, collection_method)
            if not method:
                raise AttributeError(f"Collection method '{collection_method}' not found")
            
            # Execute with error handling
            result = await self._execute_with_error_handling(
                method, execution_id, *args, **kwargs
            )
            
            return {
                "success": True,
                "execution_id": execution_id,
                "start_time": start_time,
                "end_time": datetime.now(),
                "result": result,
                "errors": []
            }
            
        except Exception as e:
            end_time = datetime.now()
            
            # Handle the error
            recovery_result = await self.error_handler.handle_error(
                e,
                component=self.__class__.__name__,
                operation=collection_method,
                context={"execution_id": execution_id}
            )
            
            return {
                "success": recovery_result.success,
                "execution_id": execution_id,
                "start_time": start_time,
                "end_time": end_time,
                "result": recovery_result.recovered_data if recovery_result.partial_success else None,
                "errors": [str(e)],
                "recovery_attempted": True,
                "recovery_message": recovery_result.message,
                "partial_success": recovery_result.partial_success
            }
    
    async def _execute_with_error_handling(
        self,
        method,
        execution_id: str,
        *args,
        **kwargs
    ):
        """Execute method with rate limiting and error handling."""
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        # Execute the method
        return await method(*args, **kwargs)


class EnhancedPoolCollector(EnhancedBaseCollector):
    """Enhanced pool collector with error handling integration."""
    
    @handle_errors(component="PoolCollector", operation="collect_pools")
    async def collect_pools_by_network(self, network: str) -> List[Dict[str, Any]]:
        """Collect pools by network with error handling."""
        self.logger.info(f"Collecting pools for network: {network}")
        
        try:
            # Simulate API call with potential errors
            pools_data = await self._fetch_pools_from_api(network)
            
            # Validate and normalize data
            validated_data = await self._validate_and_normalize_pools(pools_data)
            
            # Store in database
            stored_count = await self._store_pools_with_error_handling(validated_data)
            
            self.logger.info(f"Successfully collected {stored_count} pools for {network}")
            return validated_data
            
        except Exception as e:
            self.logger.error(f"Error collecting pools for {network}: {e}")
            raise
    
    async def _fetch_pools_from_api(self, network: str) -> List[Dict[str, Any]]:
        """Fetch pools from API with error simulation."""
        # Simulate various API errors for demonstration
        import random
        
        error_chance = random.random()
        if error_chance < 0.2:  # 20% chance of rate limit
            raise Exception("HTTP 429: Too Many Requests")
        elif error_chance < 0.25:  # 5% chance of server error
            raise Exception("HTTP 500: Internal Server Error")
        
        # Return mock pool data
        return [
            {
                "id": f"pool_{network}_{i}",
                "address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                "name": f"Pool {i}",
                "network": network,
                "reserve_usd": random.uniform(1000, 1000000)
            }
            for i in range(random.randint(5, 20))
        ]
    
    async def _validate_and_normalize_pools(self, pools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and normalize pool data with error handling."""
        valid_pools = []
        invalid_pools = []
        
        for pool in pools_data:
            try:
                # Validate required fields
                if not all(key in pool for key in ["id", "address", "name"]):
                    invalid_pools.append(pool)
                    continue
                
                # Normalize data
                normalized_pool = {
                    "id": str(pool["id"]),
                    "address": str(pool["address"]).lower(),
                    "name": str(pool["name"]),
                    "network": pool.get("network", "unknown"),
                    "reserve_usd": float(pool.get("reserve_usd", 0))
                }
                
                valid_pools.append(normalized_pool)
                
            except Exception as e:
                self.logger.warning(f"Failed to validate pool {pool.get('id', 'unknown')}: {e}")
                invalid_pools.append(pool)
        
        # If we have validation errors, handle them appropriately
        if invalid_pools:
            validation_error = Exception("Pool validation failed")
            
            recovery_result = await self.error_handler.handle_error(
                validation_error,
                component="PoolCollector",
                operation="validate_pools",
                context={
                    "valid_data": valid_pools,
                    "invalid_data": invalid_pools
                }
            )
            
            if recovery_result.partial_success:
                self.logger.warning(
                    f"Partial validation success: {len(valid_pools)} valid, "
                    f"{len(invalid_pools)} invalid pools"
                )
                return recovery_result.recovered_data
            elif not valid_pools:
                raise validation_error
        
        return valid_pools
    
    async def _store_pools_with_error_handling(self, pools: List[Dict[str, Any]]) -> int:
        """Store pools with database error handling."""
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Simulate database storage
                await asyncio.sleep(0.1)  # Simulate processing time
                
                # Simulate occasional database errors
                import random
                if random.random() < 0.15:  # 15% chance of database error
                    if retry_count < 2:
                        raise Exception("Database connection timeout")
                    else:
                        raise Exception("Database constraint violation")
                
                # Successful storage
                return len(pools)
                
            except Exception as e:
                context = {"retry_count": retry_count}
                recovery_result = await self.error_handler.handle_error(
                    e,
                    component="PoolCollector",
                    operation="store_pools",
                    context=context,
                    max_retries=max_retries
                )
                
                if recovery_result.success and recovery_result.retry_after:
                    self.logger.info(f"Retrying database operation after {recovery_result.retry_after} seconds")
                    await asyncio.sleep(recovery_result.retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception(f"Failed to store pools after {max_retries} retries")


class EnhancedOHLCVCollector(EnhancedBaseCollector):
    """Enhanced OHLCV collector with error handling integration."""
    
    @handle_errors(component="OHLCVCollector", operation="collect_ohlcv")
    async def collect_ohlcv_data(
        self,
        pool_id: str,
        timeframe: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect OHLCV data with comprehensive error handling."""
        self.logger.info(f"Collecting OHLCV data for pool {pool_id}, timeframe {timeframe}")
        
        try:
            # Fetch OHLCV data from API
            ohlcv_data = await self._fetch_ohlcv_from_api(pool_id, timeframe, limit)
            
            # Parse and validate OHLCV data
            parsed_data = await self._parse_and_validate_ohlcv(ohlcv_data, pool_id, timeframe)
            
            # Store in database
            stored_count = await self._store_ohlcv_with_error_handling(parsed_data)
            
            self.logger.info(f"Successfully collected {stored_count} OHLCV records for {pool_id}")
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Error collecting OHLCV data for {pool_id}: {e}")
            raise
    
    async def _fetch_ohlcv_from_api(
        self,
        pool_id: str,
        timeframe: str,
        limit: int
    ) -> Dict[str, Any]:
        """Fetch OHLCV data from API with error simulation."""
        import random
        
        # Simulate API errors
        error_chance = random.random()
        if error_chance < 0.15:  # 15% chance of rate limit
            raise Exception("HTTP 429: Too Many Requests")
        elif error_chance < 0.18:  # 3% chance of not found
            raise Exception(f"HTTP 404: Pool {pool_id} not found")
        
        # Return mock OHLCV data
        return {
            "data": {
                "attributes": {
                    "ohlcv_list": [
                        [
                            int(datetime.now().timestamp()) - (i * 3600),  # timestamp
                            random.uniform(0.1, 10.0),  # open
                            random.uniform(0.1, 10.0),  # high
                            random.uniform(0.1, 10.0),  # low
                            random.uniform(0.1, 10.0),  # close
                            random.uniform(1000, 100000)  # volume
                        ]
                        for i in range(limit)
                    ]
                }
            }
        }
    
    async def _parse_and_validate_ohlcv(
        self,
        response: Dict[str, Any],
        pool_id: str,
        timeframe: str
    ) -> List[Dict[str, Any]]:
        """Parse and validate OHLCV response with error handling."""
        try:
            ohlcv_list = response.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
            
            if not ohlcv_list:
                raise Exception(f"No OHLCV data found for pool {pool_id}")
            
            valid_records = []
            invalid_records = []
            
            for ohlcv_entry in ohlcv_list:
                try:
                    if len(ohlcv_entry) != 6:
                        invalid_records.append(ohlcv_entry)
                        continue
                    
                    timestamp, open_price, high_price, low_price, close_price, volume = ohlcv_entry
                    
                    # Validate data quality
                    if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
                        invalid_records.append(ohlcv_entry)
                        continue
                    
                    record = {
                        "pool_id": pool_id,
                        "timestamp": int(timestamp),
                        "timeframe": timeframe,
                        "open_price": float(open_price),
                        "high_price": float(high_price),
                        "low_price": float(low_price),
                        "close_price": float(close_price),
                        "volume_usd": float(volume),
                        "datetime": datetime.fromtimestamp(timestamp)
                    }
                    
                    valid_records.append(record)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse OHLCV entry: {e}")
                    invalid_records.append(ohlcv_entry)
            
            # Handle validation errors with partial success
            if invalid_records:
                validation_error = Exception("OHLCV validation failed")
                
                recovery_result = await self.error_handler.handle_error(
                    validation_error,
                    component="OHLCVCollector",
                    operation="parse_ohlcv",
                    context={
                        "valid_data": valid_records,
                        "invalid_data": invalid_records
                    }
                )
                
                if recovery_result.partial_success:
                    self.logger.warning(
                        f"Partial OHLCV parsing success: {len(valid_records)} valid, "
                        f"{len(invalid_records)} invalid records"
                    )
                    return recovery_result.recovered_data
                elif not valid_records:
                    raise validation_error
            
            return valid_records
            
        except Exception as e:
            self.logger.error(f"Error parsing OHLCV response for {pool_id}: {e}")
            raise
    
    async def _store_ohlcv_with_error_handling(self, ohlcv_data: List[Dict[str, Any]]) -> int:
        """Store OHLCV data with database error handling."""
        if not ohlcv_data:
            return 0
        
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Simulate database storage with bulk operations
                await asyncio.sleep(0.2)  # Simulate processing time
                
                # Simulate database errors
                import random
                if random.random() < 0.1:  # 10% chance of database error
                    if retry_count < 2:
                        raise Exception("Database connection failed")
                    else:
                        raise Exception("Bulk insert constraint violation")
                
                # Successful storage
                return len(ohlcv_data)
                
            except Exception as e:
                context = {"retry_count": retry_count}
                recovery_result = await self.error_handler.handle_error(
                    e,
                    component="OHLCVCollector",
                    operation="store_ohlcv",
                    context=context,
                    max_retries=max_retries
                )
                
                if recovery_result.success and recovery_result.retry_after:
                    self.logger.info(f"Retrying OHLCV storage after {recovery_result.retry_after} seconds")
                    await asyncio.sleep(recovery_result.retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception(f"Failed to store OHLCV data after {max_retries} retries")


async def demonstrate_collector_integration():
    """Demonstrate collector integration with error handling."""
    logger.info("=== Collector Error Handling Integration Demo ===")
    
    # Initialize components (mock for demo)
    db_manager = None  # Would be EnhancedDatabaseManager in real usage
    rate_limiter = None  # Would be EnhancedRateLimiter in real usage
    error_handler = ErrorHandler()  # No DB manager for demo
    
    # Initialize collectors
    pool_collector = EnhancedPoolCollector(db_manager, rate_limiter, error_handler)
    ohlcv_collector = EnhancedOHLCVCollector(db_manager, rate_limiter, error_handler)
    
    # Test pool collection
    logger.info("\n--- Testing Pool Collection ---")
    try:
        result = await pool_collector.collect_with_error_handling(
            "collect_pools_by_network",
            "solana"
        )
        logger.info(f"Pool collection result: {result['success']}")
        if result.get('partial_success'):
            logger.info(f"Partial success: {result['recovery_message']}")
    except Exception as e:
        logger.error(f"Pool collection failed: {e}")
    
    # Test OHLCV collection
    logger.info("\n--- Testing OHLCV Collection ---")
    try:
        result = await ohlcv_collector.collect_with_error_handling(
            "collect_ohlcv_data",
            "test_pool_id",
            "1h",
            50
        )
        logger.info(f"OHLCV collection result: {result['success']}")
        if result.get('partial_success'):
            logger.info(f"Partial success: {result['recovery_message']}")
    except Exception as e:
        logger.error(f"OHLCV collection failed: {e}")
    
    # Display error statistics
    error_stats = error_handler.get_error_statistics()
    logger.info(f"\nTotal errors handled: {error_stats['total_errors']}")
    
    if error_stats['most_frequent_errors']:
        logger.info("Most frequent errors:")
        for error_key, count in error_stats['most_frequent_errors'][:3]:
            logger.info(f"  {error_key}: {count} occurrences")


async def main():
    """Main demonstration function."""
    try:
        await demonstrate_collector_integration()
        logger.info("\n=== Integration Demonstration Complete ===")
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())