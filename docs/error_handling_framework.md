# Error Handling Framework Documentation

## Overview

The comprehensive error handling framework provides robust error recovery, system alerting, and detailed logging for the GeckoTerminal data collection system. It addresses critical issues with API rate limiting, data validation failures, database errors, and provides actionable error messages for system operators.

## Key Features

- **Automatic Error Classification**: Intelligently classifies errors into specific types for appropriate handling
- **Recovery Strategies**: Implements specific recovery strategies for different error types
- **Exponential Backoff**: Handles API rate limits with exponential backoff and jitter
- **Partial Success Handling**: Processes valid data even when some records fail validation
- **System Alerts**: Generates alerts for critical errors and persistent issues
- **Detailed Logging**: Provides actionable error messages with context
- **Error Statistics**: Tracks error frequency and patterns for monitoring
- **Decorator Support**: Easy integration with existing functions via decorators

## Architecture

### Core Components

1. **ErrorHandler**: Main orchestrator for error handling
2. **ErrorRecoveryStrategy**: Base class for implementing recovery strategies
3. **ErrorContext**: Contains error information and context
4. **RecoveryResult**: Result of recovery attempts
5. **System Alert Integration**: Creates alerts in the database for monitoring

### Error Types

The framework classifies errors into the following types:

- `API_RATE_LIMIT`: HTTP 429 errors and rate limiting
- `API_CONNECTION`: API connection failures
- `API_TIMEOUT`: API request timeouts
- `API_AUTHENTICATION`: HTTP 401/403 authentication errors
- `API_SERVER_ERROR`: HTTP 5xx server errors
- `DATA_VALIDATION`: Data validation failures
- `DATA_PARSING`: JSON/data parsing errors
- `DATABASE_CONNECTION`: Database connection issues
- `DATABASE_CONSTRAINT`: Database constraint violations
- `DATABASE_TIMEOUT`: Database operation timeouts
- `CONFIGURATION`: Configuration-related errors
- `SYSTEM_RESOURCE`: Memory/resource exhaustion
- `UNKNOWN`: Unclassified errors

### Error Severity Levels

- `CRITICAL`: Requires immediate attention (auth, config errors)
- `HIGH`: Significantly impacts functionality (database, resources)
- `MEDIUM`: May impact operations (rate limits, validation)
- `LOW`: Typically recoverable (unknown errors)

## Usage

### Basic Error Handling

```python
from gecko_terminal_collector.utils.error_handler import ErrorHandler

# Initialize error handler
error_handler = ErrorHandler(db_manager)  # Optional database manager

# Handle an error
try:
    # Some operation that might fail
    result = await api_call()
except Exception as e:
    recovery_result = await error_handler.handle_error(
        e,
        component="my_collector",
        operation="fetch_data",
        context={"retry_after": 30},
        max_retries=3
    )
    
    if recovery_result.success:
        if recovery_result.partial_success:
            # Use partially recovered data
            data = recovery_result.recovered_data
        elif recovery_result.retry_after:
            # Wait and retry
            await asyncio.sleep(recovery_result.retry_after)
    else:
        # Handle failure
        raise e
```

### Using the Decorator

```python
from gecko_terminal_collector.utils.error_handler import handle_errors

@handle_errors(component="data_collector", operation="collect_pools", max_retries=3)
async def collect_pools_data():
    # Function implementation
    # Errors will be automatically handled with retry logic
    return await fetch_pools_from_api()

# Usage
try:
    result = await collect_pools_data()
except Exception as e:
    # Only unrecoverable errors reach here
    logger.error(f"Collection failed: {e}")
```

### Custom Recovery Strategies

```python
from gecko_terminal_collector.utils.error_handler import ErrorRecoveryStrategy, ErrorType

class CustomAPIRecoveryStrategy(ErrorRecoveryStrategy):
    def __init__(self):
        super().__init__(ErrorType.API_SERVER_ERROR)
    
    async def recover(self, context, original_exception):
        # Custom recovery logic
        if "500" in str(original_exception):
            return RecoveryResult(
                success=context.retry_count < 2,
                message="Custom server error recovery",
                retry_after=30 * (context.retry_count + 1),
                should_alert=context.retry_count >= 1
            )
        
        return RecoveryResult(success=False, message="Cannot recover")

# Register custom strategy
error_handler.register_strategy(CustomAPIRecoveryStrategy())
```

### Integration with Collectors

```python
class EnhancedCollector:
    def __init__(self, db_manager, rate_limiter):
        self.db_manager = db_manager
        self.rate_limiter = rate_limiter
        self.error_handler = ErrorHandler(db_manager)
    
    async def collect_data(self, endpoint):
        try:
            # Apply rate limiting
            await self.rate_limiter.acquire()
            
            # Fetch data
            data = await self._fetch_from_api(endpoint)
            
            # Validate data with partial success handling
            validated_data = await self._validate_with_error_handling(data)
            
            # Store data
            return await self._store_with_retry(validated_data)
            
        except Exception as e:
            recovery_result = await self.error_handler.handle_error(
                e, "collector", "collect_data"
            )
            
            if recovery_result.partial_success:
                return recovery_result.recovered_data
            else:
                raise e
    
    async def _validate_with_error_handling(self, data):
        try:
            return self._validate_data(data)
        except Exception as e:
            # Separate valid and invalid data
            valid_data, invalid_data = self._separate_data(data)
            
            context = {
                "valid_data": valid_data,
                "invalid_data": invalid_data
            }
            
            recovery_result = await self.error_handler.handle_error(
                e, "collector", "validate_data", context
            )
            
            if recovery_result.partial_success:
                return recovery_result.recovered_data
            else:
                raise e
```

## Recovery Strategies

### Rate Limit Recovery

- **Exponential Backoff**: Implements exponential backoff with jitter
- **Retry Logic**: Respects `Retry-After` headers from API responses
- **Alert Threshold**: Creates alerts after multiple consecutive rate limits
- **Circuit Breaker**: Prevents excessive API calls during persistent rate limiting

### Data Validation Recovery

- **Partial Success**: Processes valid records even when some fail validation
- **Quality Thresholds**: Alerts when invalid data exceeds 10% of total
- **Detailed Logging**: Logs specific validation failures with data samples
- **Recovery Data**: Returns valid data for partial success scenarios

### Database Recovery

- **Connection Retry**: Retries database operations with exponential backoff
- **Transaction Safety**: Ensures data consistency during failures
- **Deadlock Handling**: Handles database deadlocks gracefully
- **Connection Pooling**: Manages database connections efficiently

## System Alerts

The framework automatically creates system alerts for:

- **Persistent Rate Limiting**: Multiple consecutive rate limit hits
- **High Invalid Data Rates**: When >10% of data fails validation
- **Database Connection Failures**: After multiple retry attempts
- **Critical Errors**: Authentication and configuration failures

### Alert Structure

```python
{
    "alert_id": "unique_identifier",
    "level": "error|warning|critical",
    "collector_type": "component_name",
    "message": "actionable_error_message",
    "timestamp": "2025-09-10T20:54:20.579Z",
    "acknowledged": false,
    "resolved": false,
    "alert_metadata": {
        "component": "collector_name",
        "operation": "operation_name",
        "retry_count": 3,
        "error_frequency": 5,
        "recovery_attempted": true,
        "recovery_success": false,
        "partial_success": false
    }
}
```

## Logging

### Log Levels

- **CRITICAL**: Authentication failures, configuration errors
- **ERROR**: Database failures, high-severity issues
- **WARNING**: Rate limits, validation issues, medium-severity problems
- **INFO**: Low-severity issues, general information

### Log Format

```
2025-09-10 20:54:20,579 - gecko_terminal_collector.utils.error_handler - WARNING - MEDIUM SEVERITY: collector.operation failed: Error message. Action: Specific actionable advice.
```

### Structured Logging

The framework includes structured logging data:

```python
{
    "error_type": "api_rate_limit",
    "severity": "medium",
    "component": "pool_collector",
    "operation": "fetch_pools",
    "error_message": "HTTP 429: Too Many Requests",
    "retry_count": 2,
    "max_retries": 3,
    "timestamp": "2025-09-10T20:54:20.579Z",
    "details": {"retry_after": 60},
    "traceback": "..." // Only for high/critical errors
}
```

## Monitoring and Statistics

### Error Statistics

```python
# Get error statistics
stats = error_handler.get_error_statistics()

# Example output:
{
    "total_errors": 25,
    "error_breakdown": {
        "collector.fetch_data.api_rate_limit": 15,
        "collector.validate_data.data_validation": 8,
        "collector.store_data.database_connection": 2
    },
    "most_frequent_errors": [
        ("collector.fetch_data.api_rate_limit", 15),
        ("collector.validate_data.data_validation", 8),
        ("collector.store_data.database_connection", 2)
    ]
}
```

### Health Monitoring

The framework tracks:

- **Error Frequency**: How often errors occur per component/operation
- **Recovery Success Rate**: Percentage of successful error recoveries
- **Alert Generation**: When and why alerts are created
- **Performance Impact**: How errors affect system performance

## Configuration

### Error Handler Configuration

```python
# Initialize with custom settings
error_handler = ErrorHandler(
    db_manager=enhanced_db_manager,  # For alert creation
)

# Register custom recovery strategies
error_handler.register_strategy(CustomRecoveryStrategy())
```

### Recovery Strategy Configuration

```python
# Rate limit strategy configuration
rate_limit_strategy = RateLimitRecoveryStrategy()
# Strategies use context from ErrorContext for configuration

# Database strategy configuration  
db_strategy = DatabaseRecoveryStrategy()
# Uses backoff_seconds and max_retries from ErrorContext
```

## Best Practices

### 1. Use Appropriate Error Context

```python
# Provide relevant context for better error handling
context = {
    "retry_after": response_headers.get("Retry-After", 60),
    "endpoint": "/api/pools",
    "request_id": "req_123",
    "valid_data": valid_records,
    "invalid_data": invalid_records
}

await error_handler.handle_error(e, "collector", "operation", context)
```

### 2. Handle Partial Success

```python
recovery_result = await error_handler.handle_error(...)

if recovery_result.partial_success:
    # Process the valid data that was recovered
    await process_data(recovery_result.recovered_data)
    
    # Log the partial success
    logger.info(f"Partial success: {recovery_result.message}")
```

### 3. Implement Circuit Breakers

```python
# Track consecutive failures
consecutive_failures = 0

while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
    try:
        result = await operation()
        consecutive_failures = 0  # Reset on success
        return result
    except Exception as e:
        recovery_result = await error_handler.handle_error(e, ...)
        
        if not recovery_result.success:
            consecutive_failures += 1
            
        if recovery_result.retry_after:
            await asyncio.sleep(recovery_result.retry_after)
```

### 4. Monitor Error Patterns

```python
# Regularly check error statistics
stats = error_handler.get_error_statistics()

# Alert on unusual error patterns
if stats["total_errors"] > THRESHOLD:
    logger.warning(f"High error rate detected: {stats['total_errors']} errors")
    
# Identify problematic components
for error_key, count in stats["most_frequent_errors"][:5]:
    if count > COMPONENT_THRESHOLD:
        logger.warning(f"Component {error_key} has {count} errors")
```

## Testing

### Unit Testing

```python
import pytest
from gecko_terminal_collector.utils.error_handler import ErrorHandler, ErrorType

@pytest.mark.asyncio
async def test_rate_limit_handling():
    handler = ErrorHandler()
    
    error = Exception("HTTP 429: Too Many Requests")
    result = await handler.handle_error(
        error, "test_component", "test_operation",
        context={"retry_after": 30}
    )
    
    assert result.success is True
    assert result.retry_after is not None
    assert "Rate limit recovery" in result.message
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_collector_error_integration():
    # Test complete error handling workflow
    collector = EnhancedCollector(db_manager, rate_limiter)
    
    # Simulate various error conditions
    with patch('api_client.fetch_data') as mock_fetch:
        mock_fetch.side_effect = Exception("HTTP 429: Too Many Requests")
        
        result = await collector.collect_data("/api/pools")
        
        # Verify error was handled appropriately
        assert result is not None  # Should recover or provide partial data
```

## Troubleshooting

### Common Issues

1. **Logging Conflicts**: Avoid using 'message' key in log extras
2. **Async Context**: Use proper async/await patterns with the decorator
3. **Database Alerts**: Ensure database manager is configured for alert creation
4. **Recovery Strategy Registration**: Register custom strategies before use

### Debug Mode

```python
import logging

# Enable debug logging for error handler
logging.getLogger('gecko_terminal_collector.utils.error_handler').setLevel(logging.DEBUG)

# This will show detailed error handling flow
```

### Performance Considerations

- **Error Frequency**: High error rates may indicate system issues
- **Recovery Overhead**: Frequent retries can impact performance
- **Alert Volume**: Too many alerts can overwhelm monitoring systems
- **Database Load**: Alert creation adds database operations

## Examples

See the following example files for complete usage demonstrations:

- `examples/error_handling_demo.py`: Basic error handling scenarios
- `examples/collector_error_integration.py`: Integration with collectors
- `tests/test_error_handler.py`: Comprehensive test suite

## Migration Guide

### From Basic Exception Handling

```python
# Before
try:
    result = await api_call()
except Exception as e:
    logger.error(f"API call failed: {e}")
    raise e

# After
try:
    result = await api_call()
except Exception as e:
    recovery_result = await error_handler.handle_error(
        e, "component", "operation"
    )
    
    if recovery_result.success:
        if recovery_result.retry_after:
            await asyncio.sleep(recovery_result.retry_after)
            # Retry logic here
    else:
        raise e
```

### Adding to Existing Collectors

1. Initialize ErrorHandler in collector constructor
2. Wrap critical operations with error handling
3. Use decorator for simple retry scenarios
4. Implement partial success handling for data validation
5. Add system alert monitoring

This framework provides comprehensive error handling capabilities that improve system reliability, provide better observability, and enable graceful degradation under various failure conditions.