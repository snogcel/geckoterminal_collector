"""
Demonstration of the comprehensive error handling framework.

This script shows how to use the error handling framework in various scenarios
including API rate limiting, data validation, and database errors.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import List, Dict, Any

from gecko_terminal_collector.utils.error_handler import (
    ErrorHandler,
    ErrorType,
    ErrorSeverity,
    handle_errors
)
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockAPIClient:
    """Mock API client that simulates various error conditions."""
    
    def __init__(self):
        self.call_count = 0
        self.rate_limit_threshold = 5
    
    async def fetch_data(self, endpoint: str) -> Dict[str, Any]:
        """Simulate API calls with various error conditions."""
        self.call_count += 1
        
        # Simulate rate limiting
        if self.call_count > self.rate_limit_threshold:
            if random.random() < 0.7:  # 70% chance of rate limit
                raise Exception("HTTP 429: Too Many Requests")
        
        # Simulate other API errors
        error_chance = random.random()
        if error_chance < 0.1:  # 10% chance of server error
            raise Exception("HTTP 500: Internal Server Error")
        elif error_chance < 0.15:  # 5% chance of timeout
            raise Exception("API timeout occurred")
        elif error_chance < 0.18:  # 3% chance of auth error
            raise Exception("HTTP 401: Unauthorized")
        
        # Return mock data
        return {
            "data": [
                {"id": f"item_{i}", "value": random.randint(1, 100)}
                for i in range(random.randint(5, 15))
            ],
            "timestamp": datetime.now().isoformat()
        }


class MockDataValidator:
    """Mock data validator that simulates validation errors."""
    
    @staticmethod
    def validate_data(data: List[Dict[str, Any]]) -> Dict[str, List]:
        """Validate data and return valid/invalid splits."""
        valid_data = []
        invalid_data = []
        
        for item in data:
            # Simulate validation logic
            if (
                isinstance(item.get("id"), str) and
                isinstance(item.get("value"), int) and
                item.get("value", 0) > 0
            ):
                valid_data.append(item)
            else:
                invalid_data.append(item)
        
        # Randomly corrupt some valid data to simulate validation issues
        if valid_data and random.random() < 0.2:  # 20% chance of corruption
            corrupted_count = min(2, len(valid_data) // 3)
            for _ in range(corrupted_count):
                if valid_data:
                    corrupted_item = valid_data.pop()
                    corrupted_item["value"] = "invalid_value"  # Corrupt the data
                    invalid_data.append(corrupted_item)
        
        return {"valid_data": valid_data, "invalid_data": invalid_data}


class MockDatabaseManager:
    """Mock database manager that simulates database errors."""
    
    def __init__(self):
        self.connection_failures = 0
        self.max_connection_failures = 2
    
    async def store_data(self, data: List[Dict[str, Any]]) -> int:
        """Simulate database storage with potential errors."""
        
        # Simulate connection failures
        if self.connection_failures < self.max_connection_failures:
            if random.random() < 0.3:  # 30% chance of connection failure
                self.connection_failures += 1
                raise Exception("Database connection failed")
        
        # Simulate constraint violations
        if random.random() < 0.1:  # 10% chance of constraint error
            raise Exception("Integrity constraint violation: duplicate key")
        
        # Simulate successful storage
        await asyncio.sleep(0.1)  # Simulate processing time
        return len(data)


class DataCollector:
    """Example data collector using the error handling framework."""
    
    def __init__(self, error_handler: ErrorHandler):
        self.api_client = MockAPIClient()
        self.validator = MockDataValidator()
        self.db_manager = MockDatabaseManager()
        self.error_handler = error_handler
    
    @handle_errors(component="data_collector", operation="collect_and_store")
    async def collect_and_store_data(self, endpoint: str) -> Dict[str, Any]:
        """Collect data from API and store in database with error handling."""
        logger.info(f"Starting data collection from {endpoint}")
        
        # Step 1: Fetch data from API
        api_data = await self._fetch_with_retry(endpoint)
        
        # Step 2: Validate data
        validation_result = await self._validate_with_partial_success(api_data["data"])
        
        # Step 3: Store valid data
        stored_count = await self._store_with_retry(validation_result["valid_data"])
        
        return {
            "endpoint": endpoint,
            "total_fetched": len(api_data["data"]),
            "valid_records": len(validation_result["valid_data"]),
            "invalid_records": len(validation_result["invalid_data"]),
            "stored_records": stored_count,
            "timestamp": api_data["timestamp"]
        }
    
    async def _fetch_with_retry(self, endpoint: str) -> Dict[str, Any]:
        """Fetch data with automatic retry on rate limits."""
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                return await self.api_client.fetch_data(endpoint)
            except Exception as e:
                context = {"retry_count": retry_count, "retry_after": 30}
                recovery_result = await self.error_handler.handle_error(
                    e, "data_collector", "fetch_data", context, max_retries
                )
                
                if recovery_result.success and recovery_result.retry_after:
                    logger.info(f"Retrying after {recovery_result.retry_after} seconds")
                    await asyncio.sleep(recovery_result.retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception(f"Failed to fetch data after {max_retries} retries")
    
    async def _validate_with_partial_success(self, data: List[Dict[str, Any]]) -> Dict[str, List]:
        """Validate data with partial success handling."""
        try:
            return self.validator.validate_data(data)
        except Exception as e:
            # In a real scenario, you might have more sophisticated validation
            # that can recover partial results
            context = {
                "valid_data": [],
                "invalid_data": data  # Assume all data is invalid on validation error
            }
            
            recovery_result = await self.error_handler.handle_error(
                e, "data_collector", "validate_data", context
            )
            
            if recovery_result.partial_success:
                return {
                    "valid_data": recovery_result.recovered_data,
                    "invalid_data": []
                }
            else:
                raise e
    
    async def _store_with_retry(self, data: List[Dict[str, Any]]) -> int:
        """Store data with database error retry."""
        if not data:
            return 0
        
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                return await self.db_manager.store_data(data)
            except Exception as e:
                context = {"retry_count": retry_count}
                recovery_result = await self.error_handler.handle_error(
                    e, "data_collector", "store_data", context, max_retries
                )
                
                if recovery_result.success and recovery_result.retry_after:
                    logger.info(f"Retrying database operation after {recovery_result.retry_after} seconds")
                    await asyncio.sleep(recovery_result.retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception(f"Failed to store data after {max_retries} retries")


async def demonstrate_error_handling():
    """Demonstrate various error handling scenarios."""
    logger.info("Starting error handling demonstration")
    
    # Initialize error handler (without database for demo)
    error_handler = ErrorHandler()
    
    # Initialize data collector
    collector = DataCollector(error_handler)
    
    # Simulate multiple collection runs
    endpoints = [
        "/api/pools",
        "/api/tokens", 
        "/api/trades",
        "/api/ohlcv",
        "/api/dexes"
    ]
    
    results = []
    
    for i, endpoint in enumerate(endpoints):
        try:
            logger.info(f"\n--- Collection Run {i+1}: {endpoint} ---")
            result = await collector.collect_and_store_data(endpoint)
            results.append(result)
            
            logger.info(f"Collection successful: {result}")
            
        except Exception as e:
            logger.error(f"Collection failed for {endpoint}: {e}")
            results.append({
                "endpoint": endpoint,
                "error": str(e),
                "success": False
            })
        
        # Add delay between runs
        await asyncio.sleep(1)
    
    # Display summary
    logger.info("\n--- Collection Summary ---")
    successful_runs = sum(1 for r in results if r.get("success", True))
    total_runs = len(results)
    
    logger.info(f"Successful runs: {successful_runs}/{total_runs}")
    
    # Display error statistics
    error_stats = error_handler.get_error_statistics()
    logger.info(f"Total errors handled: {error_stats['total_errors']}")
    
    if error_stats['most_frequent_errors']:
        logger.info("Most frequent errors:")
        for error_key, count in error_stats['most_frequent_errors'][:5]:
            logger.info(f"  {error_key}: {count} occurrences")


async def demonstrate_decorator_usage():
    """Demonstrate using the error handling decorator."""
    logger.info("\n--- Decorator Usage Demonstration ---")
    
    @handle_errors(component="demo_service", operation="process_data", max_retries=2)
    async def process_data_with_errors():
        """Function that may encounter various errors."""
        error_type = random.choice([
            "rate_limit",
            "validation", 
            "database",
            "success"
        ])
        
        if error_type == "rate_limit":
            raise Exception("HTTP 429: Too Many Requests")
        elif error_type == "validation":
            raise Exception("Data validation failed")
        elif error_type == "database":
            raise Exception("Database connection timeout")
        else:
            return {"status": "success", "processed": 100}
    
    # Try the function multiple times
    for i in range(5):
        try:
            result = await process_data_with_errors()
            logger.info(f"Attempt {i+1}: {result}")
        except Exception as e:
            logger.error(f"Attempt {i+1} failed: {e}")


async def demonstrate_custom_recovery_strategy():
    """Demonstrate creating and using custom recovery strategies."""
    logger.info("\n--- Custom Recovery Strategy Demonstration ---")
    
    from gecko_terminal_collector.utils.error_handler import ErrorRecoveryStrategy
    
    class CustomAPIRecoveryStrategy(ErrorRecoveryStrategy):
        """Custom recovery strategy for specific API errors."""
        
        def __init__(self):
            super().__init__(ErrorType.API_SERVER_ERROR)
        
        async def recover(self, context, original_exception):
            """Custom recovery logic for server errors."""
            if "500" in str(original_exception):
                # For 500 errors, wait longer and try fewer times
                wait_time = 30 * (context.retry_count + 1)
                
                return RecoveryResult(
                    success=context.retry_count < 2,  # Only 2 retries for server errors
                    message=f"Server error recovery: waiting {wait_time}s",
                    retry_after=wait_time,
                    should_alert=context.retry_count >= 1
                )
            
            return RecoveryResult(
                success=False,
                message="Cannot recover from this server error"
            )
    
    # Create error handler with custom strategy
    error_handler = ErrorHandler()
    custom_strategy = CustomAPIRecoveryStrategy()
    error_handler.register_strategy(custom_strategy)
    
    # Test the custom strategy
    try:
        server_error = Exception("HTTP 500: Internal Server Error")
        result = await error_handler.handle_error(
            server_error,
            component="custom_demo",
            operation="test_custom_recovery"
        )
        
        logger.info(f"Custom recovery result: {result.message}")
        
    except Exception as e:
        logger.error(f"Custom recovery failed: {e}")


async def main():
    """Main demonstration function."""
    logger.info("=== Error Handling Framework Demonstration ===")
    
    try:
        # Run all demonstrations
        await demonstrate_error_handling()
        await demonstrate_decorator_usage()
        await demonstrate_custom_recovery_strategy()
        
        logger.info("\n=== Demonstration Complete ===")
        
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())