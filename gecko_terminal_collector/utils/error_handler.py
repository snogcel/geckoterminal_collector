"""
Comprehensive error handling framework for the GeckoTerminal data collection system.

This module provides enhanced error recovery strategies, system alert generation,
detailed logging, and partial success handling for data validation failures.
"""

import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
import json

from ..database.enhanced_manager import EnhancedDatabaseManager


class ErrorType(Enum):
    """Classification of error types for appropriate handling."""
    API_RATE_LIMIT = "api_rate_limit"
    API_CONNECTION = "api_connection"
    API_TIMEOUT = "api_timeout"
    API_AUTHENTICATION = "api_authentication"
    API_SERVER_ERROR = "api_server_error"
    DATA_VALIDATION = "data_validation"
    DATA_PARSING = "data_parsing"
    DATABASE_CONNECTION = "database_connection"
    DATABASE_CONSTRAINT = "database_constraint"
    DATABASE_TIMEOUT = "database_timeout"
    CONFIGURATION = "configuration"
    SYSTEM_RESOURCE = "system_resource"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels for alert generation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    component: str = ""
    operation: str = ""
    retry_count: int = 0
    max_retries: int = 3
    backoff_seconds: float = 1.0
    recoverable: bool = True


@dataclass
class RecoveryResult:
    """Result of error recovery attempt."""
    success: bool
    message: str
    retry_after: Optional[float] = None
    should_alert: bool = False
    partial_success: bool = False
    recovered_data: Optional[Any] = None


class ErrorRecoveryStrategy:
    """Base class for error recovery strategies."""
    
    def __init__(self, error_type: ErrorType):
        self.error_type = error_type
        self.logger = logging.getLogger(f"{__name__}.{error_type.value}")
    
    async def can_recover(self, context: ErrorContext) -> bool:
        """Check if this strategy can handle the error."""
        return context.error_type == self.error_type
    
    async def recover(self, context: ErrorContext, original_exception: Exception) -> RecoveryResult:
        """Attempt to recover from the error."""
        raise NotImplementedError("Subclasses must implement recover method")


class RateLimitRecoveryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for API rate limit errors."""
    
    def __init__(self):
        super().__init__(ErrorType.API_RATE_LIMIT)
    
    async def recover(self, context: ErrorContext, original_exception: Exception) -> RecoveryResult:
        """Handle rate limit errors with exponential backoff."""
        retry_after = context.details.get('retry_after', 60)
        
        # Calculate exponential backoff with jitter
        backoff_time = min(retry_after * (2 ** context.retry_count), 300)
        jitter = backoff_time * 0.1  # 10% jitter
        total_wait = backoff_time + jitter
        
        self.logger.warning(
            f"Rate limit hit for {context.component}.{context.operation}. "
            f"Waiting {total_wait:.1f} seconds before retry {context.retry_count + 1}/{context.max_retries}"
        )
        
        # Create system alert for persistent rate limiting
        should_alert = context.retry_count >= 2
        
        return RecoveryResult(
            success=context.retry_count < context.max_retries,
            message=f"Rate limit recovery: waiting {total_wait:.1f}s",
            retry_after=total_wait,
            should_alert=should_alert
        )


class DataValidationRecoveryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for data validation errors with partial success handling."""
    
    def __init__(self):
        super().__init__(ErrorType.DATA_VALIDATION)
    
    async def recover(self, context: ErrorContext, original_exception: Exception) -> RecoveryResult:
        """Handle data validation errors with partial success."""
        invalid_data = context.details.get('invalid_data', [])
        valid_data = context.details.get('valid_data', [])
        
        if valid_data:
            self.logger.warning(
                f"Partial validation success for {context.component}.{context.operation}: "
                f"{len(valid_data)} valid records, {len(invalid_data)} invalid records"
            )
            
            # Alert if invalid data is more than 10% of total
            total_records = len(valid_data) + len(invalid_data)
            invalid_percentage = len(invalid_data) / total_records if total_records > 0 else 0
            
            return RecoveryResult(
                success=True,
                message=f"Partial success: {len(valid_data)} valid records processed",
                partial_success=True,
                recovered_data=valid_data,
                should_alert=invalid_percentage > 0.1  # Alert if >10% invalid
            )
        else:
            self.logger.error(
                f"Complete validation failure for {context.component}.{context.operation}: "
                f"All {len(invalid_data)} records invalid"
            )
            
            return RecoveryResult(
                success=False,
                message="Complete validation failure: no valid records",
                should_alert=True
            )


class DatabaseRecoveryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for database errors."""
    
    def __init__(self):
        super().__init__(ErrorType.DATABASE_CONNECTION)
    
    async def recover(self, context: ErrorContext, original_exception: Exception) -> RecoveryResult:
        """Handle database connection errors with retry logic."""
        if context.retry_count < context.max_retries:
            wait_time = context.backoff_seconds * (2 ** context.retry_count)
            
            self.logger.warning(
                f"Database connection error for {context.component}.{context.operation}. "
                f"Retrying in {wait_time} seconds (attempt {context.retry_count + 1}/{context.max_retries})"
            )
            
            return RecoveryResult(
                success=True,
                message=f"Database retry scheduled in {wait_time}s",
                retry_after=wait_time,
                should_alert=context.retry_count >= 2
            )
        else:
            self.logger.error(
                f"Database connection failed after {context.max_retries} attempts for "
                f"{context.component}.{context.operation}"
            )
            
            return RecoveryResult(
                success=False,
                message="Database connection failed after all retries",
                should_alert=True
            )


class ErrorHandler:
    """Comprehensive error handling framework."""
    
    def __init__(self, db_manager: Optional[EnhancedDatabaseManager] = None):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.recovery_strategies: Dict[ErrorType, ErrorRecoveryStrategy] = {}
        self.error_counts: Dict[str, int] = {}
        
        # Register default recovery strategies
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register default error recovery strategies."""
        strategies = [
            RateLimitRecoveryStrategy(),
            DataValidationRecoveryStrategy(),
            DatabaseRecoveryStrategy()
        ]
        
        for strategy in strategies:
            self.recovery_strategies[strategy.error_type] = strategy
    
    def register_strategy(self, strategy: ErrorRecoveryStrategy):
        """Register a custom error recovery strategy."""
        self.recovery_strategies[strategy.error_type] = strategy
    
    def classify_error(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorType:
        """Classify an exception into an error type."""
        context = context or {}
        exception_str = str(exception).lower()
        
        # API-related errors
        if "429" in exception_str or "rate limit" in exception_str:
            return ErrorType.API_RATE_LIMIT
        elif "timeout" in exception_str and ("api" in exception_str or "http" in exception_str):
            return ErrorType.API_TIMEOUT
        elif "connection" in exception_str and ("api" in exception_str or "http" in exception_str):
            return ErrorType.API_CONNECTION
        elif "401" in exception_str or "403" in exception_str or "unauthorized" in exception_str:
            return ErrorType.API_AUTHENTICATION
        elif any(code in exception_str for code in ["500", "502", "503", "504"]):
            return ErrorType.API_SERVER_ERROR
        
        # Data-related errors
        elif "validation" in exception_str or "invalid" in exception_str:
            return ErrorType.DATA_VALIDATION
        elif "parse" in exception_str or "json" in exception_str:
            return ErrorType.DATA_PARSING
        
        # Database-related errors
        elif ("database" in exception_str or "sql" in exception_str or 
              "constraint" in exception_str or "integrity" in exception_str):
            if "timeout" in exception_str:
                return ErrorType.DATABASE_TIMEOUT
            elif "constraint" in exception_str or "integrity" in exception_str:
                return ErrorType.DATABASE_CONSTRAINT
            else:
                return ErrorType.DATABASE_CONNECTION
        
        # System-related errors
        elif "memory" in exception_str or "resource" in exception_str:
            return ErrorType.SYSTEM_RESOURCE
        elif "config" in exception_str:
            return ErrorType.CONFIGURATION
        
        return ErrorType.UNKNOWN
    
    def determine_severity(self, error_type: ErrorType, context: Dict[str, Any] = None) -> ErrorSeverity:
        """Determine error severity based on type and context."""
        context = context or {}
        
        # Critical errors that require immediate attention
        if error_type in [ErrorType.API_AUTHENTICATION, ErrorType.CONFIGURATION]:
            return ErrorSeverity.CRITICAL
        
        # High severity errors that significantly impact functionality
        elif error_type in [ErrorType.DATABASE_CONNECTION, ErrorType.SYSTEM_RESOURCE]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors that may impact some operations
        elif error_type in [ErrorType.API_RATE_LIMIT, ErrorType.DATA_VALIDATION]:
            # Escalate to high if persistent
            retry_count = context.get('retry_count', 0)
            if retry_count >= 3:
                return ErrorSeverity.HIGH
            return ErrorSeverity.MEDIUM
        
        # Low severity errors that are typically recoverable
        else:
            return ErrorSeverity.LOW
    
    async def handle_error(
        self,
        exception: Exception,
        component: str,
        operation: str,
        context: Dict[str, Any] = None,
        max_retries: int = 3
    ) -> RecoveryResult:
        """Handle an error with appropriate recovery strategy."""
        context = context or {}
        
        # Classify the error
        error_type = self.classify_error(exception, context)
        severity = self.determine_severity(error_type, context)
        
        # Create error context
        error_context = ErrorContext(
            error_type=error_type,
            severity=severity,
            message=str(exception),
            details=context,
            component=component,
            operation=operation,
            retry_count=context.get('retry_count', 0),
            max_retries=max_retries
        )
        
        # Log the error with detailed context
        await self._log_error(error_context, exception)
        
        # Track error frequency
        error_key = f"{component}.{operation}.{error_type.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Attempt recovery
        recovery_result = await self._attempt_recovery(error_context, exception)
        
        # Generate system alert if needed
        if recovery_result.should_alert:
            await self._create_system_alert(error_context, recovery_result)
        
        return recovery_result
    
    async def _attempt_recovery(self, context: ErrorContext, exception: Exception) -> RecoveryResult:
        """Attempt to recover from the error using appropriate strategy."""
        strategy = self.recovery_strategies.get(context.error_type)
        
        if strategy and await strategy.can_recover(context):
            try:
                return await strategy.recover(context, exception)
            except Exception as recovery_error:
                self.logger.error(
                    f"Recovery strategy failed for {context.error_type.value}: {recovery_error}"
                )
                return RecoveryResult(
                    success=False,
                    message=f"Recovery strategy failed: {recovery_error}",
                    should_alert=True
                )
        else:
            # No specific strategy available
            self.logger.warning(
                f"No recovery strategy available for {context.error_type.value}"
            )
            return RecoveryResult(
                success=False,
                message=f"No recovery strategy for {context.error_type.value}",
                should_alert=context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
            )
    
    async def _log_error(self, context: ErrorContext, exception: Exception):
        """Log error with detailed context and actionable messages."""
        # Create detailed log message (avoid 'message' key conflict)
        log_data = {
            "error_type": context.error_type.value,
            "severity": context.severity.value,
            "component": context.component,
            "operation": context.operation,
            "error_message": context.message,
            "retry_count": context.retry_count,
            "max_retries": context.max_retries,
            "timestamp": context.timestamp.isoformat(),
            "details": context.details,
            "traceback": traceback.format_exc() if context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else None
        }
        
        # Generate actionable message
        actionable_message = self._generate_actionable_message(context)
        
        # Log based on severity
        if context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {actionable_message}", extra=log_data)
        elif context.severity == ErrorSeverity.HIGH:
            self.logger.error(f"HIGH SEVERITY: {actionable_message}", extra=log_data)
        elif context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"MEDIUM SEVERITY: {actionable_message}", extra=log_data)
        else:
            self.logger.info(f"LOW SEVERITY: {actionable_message}", extra=log_data)
    
    def _generate_actionable_message(self, context: ErrorContext) -> str:
        """Generate actionable error messages based on error type."""
        base_msg = f"{context.component}.{context.operation} failed: {context.message}"
        
        if context.error_type == ErrorType.API_RATE_LIMIT:
            return f"{base_msg}. Action: Reduce API call frequency or implement longer delays."
        
        elif context.error_type == ErrorType.API_AUTHENTICATION:
            return f"{base_msg}. Action: Check API credentials and permissions."
        
        elif context.error_type == ErrorType.DATABASE_CONNECTION:
            return f"{base_msg}. Action: Verify database connectivity and credentials."
        
        elif context.error_type == ErrorType.DATA_VALIDATION:
            invalid_count = len(context.details.get('invalid_data', []))
            return f"{base_msg}. Action: Review data quality - {invalid_count} invalid records detected."
        
        elif context.error_type == ErrorType.CONFIGURATION:
            return f"{base_msg}. Action: Review configuration settings and environment variables."
        
        elif context.error_type == ErrorType.SYSTEM_RESOURCE:
            return f"{base_msg}. Action: Check system resources (memory, disk space, CPU)."
        
        else:
            return f"{base_msg}. Action: Review logs and contact support if issue persists."
    
    async def _create_system_alert(self, context: ErrorContext, recovery_result: RecoveryResult):
        """Create system alert for significant errors."""
        if not self.db_manager:
            self.logger.warning("Cannot create system alert: no database manager configured")
            return
        
        try:
            alert_message = self._generate_actionable_message(context)
            if recovery_result.partial_success:
                alert_message += f" Partial recovery: {recovery_result.message}"
            
            # Create alert data for the database manager
            alert_data = {
                "alert_id": f"{context.component}_{context.operation}_{context.error_type.value}_{int(context.timestamp.timestamp())}",
                "level": context.severity.value,
                "collector_type": context.component,
                "message": alert_message,
                "timestamp": context.timestamp,
                "acknowledged": False,
                "resolved": False,
                "alert_metadata": json.dumps({
                    "component": context.component,
                    "operation": context.operation,
                    "retry_count": context.retry_count,
                    "error_frequency": self.error_counts.get(
                        f"{context.component}.{context.operation}.{context.error_type.value}", 1
                    ),
                    "recovery_attempted": True,
                    "recovery_success": recovery_result.success,
                    "partial_success": recovery_result.partial_success
                })
            }
            
            await self.db_manager.create_system_alert(alert_data)
            self.logger.info(f"System alert created for {context.error_type.value}")
            
        except Exception as alert_error:
            self.logger.error(f"Failed to create system alert: {alert_error}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_breakdown": dict(self.error_counts),
            "most_frequent_errors": sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


# Decorator for automatic error handling
def handle_errors(
    component: str,
    operation: str = None,
    max_retries: int = 3,
    error_handler: ErrorHandler = None
):
    """Decorator for automatic error handling in functions."""
    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            nonlocal operation
            if operation is None:
                operation = func.__name__
            
            handler = error_handler or ErrorHandler()
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = {"retry_count": retry_count}
                    recovery_result = await handler.handle_error(
                        e, component, operation, context, max_retries
                    )
                    
                    if recovery_result.success and recovery_result.retry_after:
                        await asyncio.sleep(recovery_result.retry_after)
                        retry_count += 1
                        continue
                    elif recovery_result.partial_success:
                        return recovery_result.recovered_data
                    else:
                        raise e
            
            raise Exception(f"Operation failed after {max_retries} retries")
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, convert to async temporarily
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, we can't use asyncio.run
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_wrapper(*args, **kwargs))
                        return future.result()
                else:
                    return asyncio.run(async_wrapper(*args, **kwargs))
            except RuntimeError:
                return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator