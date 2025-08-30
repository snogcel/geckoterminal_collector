"""
Error handling utilities with exponential backoff and circuit breaker patterns.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Type, Union, Dict
from datetime import datetime, timedelta

from .error_classification import (
    ErrorClassifier, ErrorContext, RecoveryAction, 
    ErrorCategory, ErrorSeverity, error_classifier
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
        
        if self.jitter:
            # Add jitter to prevent thundering herd
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascading failures.
    
    Tracks failure rate and opens circuit when threshold is exceeded,
    preventing further calls until recovery is detected.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitBreakerState.CLOSED
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self._state != CircuitBreakerState.OPEN:
            return False
        
        if self._last_failure_time is None:
            return True
        
        return datetime.now() - self._last_failure_time > timedelta(seconds=self.recovery_timeout)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Original exception: When function fails
        """
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker reset to CLOSED state")
            
            self._failure_count = 0
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    def _record_failure(self) -> None:
        """Record a failure and update circuit state."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker OPENED after {self._failure_count} failures. "
                f"Will retry after {self.recovery_timeout} seconds."
            )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class ErrorHandler:
    """
    Comprehensive error handling with retry logic and circuit breaker.
    
    Provides exponential backoff, jitter, and circuit breaker patterns
    for resilient error handling in data collection operations with
    intelligent error classification and recovery strategies.
    """
    
    def __init__(
        self, 
        retry_config: Optional[RetryConfig] = None,
        error_classifier: Optional[ErrorClassifier] = None
    ):
        self.retry_config = retry_config or RetryConfig()
        self.error_classifier = error_classifier or ErrorClassifier()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._error_history: dict[str, list[ErrorContext]] = {}
        self._escalation_counts: dict[str, int] = {}
    
    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 300
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for the given name."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return self._circuit_breakers[name]
    
    async def with_retry(
        self,
        func: Callable,
        context: str,
        circuit_breaker_name: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        collector_type: str = "unknown",
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with intelligent retry logic and optional circuit breaker.
        
        Uses error classification to determine the best recovery strategy
        for each type of failure, including adaptive retry behavior.
        
        Args:
            func: Function to execute
            context: Context description for logging
            circuit_breaker_name: Name of circuit breaker to use (optional)
            retry_config: Override retry configuration (optional)
            collector_type: Type of collector for error tracking
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted or recovery strategy indicates failure
        """
        config = retry_config or self.retry_config
        circuit_breaker = None
        
        if circuit_breaker_name:
            circuit_breaker = self.get_circuit_breaker(circuit_breaker_name)
        
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                if circuit_breaker:
                    return await circuit_breaker.call(func, *args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
            except CircuitBreakerOpenError:
                logger.warning(f"Circuit breaker open for {context}, skipping retry")
                raise
                
            except Exception as e:
                last_exception = e
                
                # Create error context for classification
                error_context = ErrorContext(
                    error=e,
                    operation=context,
                    collector_type=collector_type,
                    timestamp=datetime.now(),
                    attempt_number=attempt + 1,
                    additional_context={"args": args, "kwargs": kwargs}
                )
                
                # Record error in history
                self._record_error(error_context)
                
                # Classify error and determine recovery strategy
                recovery_action = self.error_classifier.get_recovery_action(error_context)
                
                # Handle different recovery actions
                if recovery_action == RecoveryAction.FAIL_FAST:
                    logger.error(f"Fail-fast error in {context}: {e}")
                    raise e
                elif recovery_action == RecoveryAction.SKIP_AND_CONTINUE:
                    logger.warning(f"Skipping operation {context} due to: {e}")
                    return None
                elif recovery_action == RecoveryAction.ESCALATE:
                    self._handle_escalation(error_context)
                    raise e
                
                # Check if we should retry based on error classification
                if not self.error_classifier.should_retry(error_context):
                    logger.error(f"Error not eligible for retry in {context}: {e}")
                    raise e
                
                if attempt == config.max_retries:
                    logger.error(
                        f"All retry attempts exhausted for {context}. "
                        f"Final error: {e}"
                    )
                    break
                
                # Calculate delay based on recovery action and error type
                delay = self._calculate_adaptive_delay(error_context, attempt, config)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed for {context}: {e}. "
                    f"Recovery action: {recovery_action.value}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                await asyncio.sleep(delay)
        
        # Re-raise the last exception if all retries failed
        if last_exception:
            raise last_exception
    
    def handle_error(
        self,
        error: Exception,
        context: str,
        collector_type: str
    ) -> None:
        """
        Handle and log errors with appropriate context.
        
        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
            collector_type: Type of collector that encountered the error
        """
        error_msg = f"Error in {collector_type} - {context}: {error}"
        
        # Log different error types with appropriate levels
        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {error_msg}")
        elif isinstance(error, ValueError):
            logger.error(f"Data validation error: {error_msg}")
        elif isinstance(error, CircuitBreakerOpenError):
            logger.warning(f"Circuit breaker error: {error_msg}")
        else:
            logger.error(f"Unexpected error: {error_msg}")
    
    def _record_error(self, error_context: ErrorContext) -> None:
        """Record error in history for analysis and escalation tracking."""
        operation_key = f"{error_context.collector_type}:{error_context.operation}"
        
        if operation_key not in self._error_history:
            self._error_history[operation_key] = []
        
        self._error_history[operation_key].append(error_context)
        
        # Keep only recent errors (last 100 per operation)
        if len(self._error_history[operation_key]) > 100:
            self._error_history[operation_key] = self._error_history[operation_key][-100:]
    
    def _calculate_adaptive_delay(
        self, 
        error_context: ErrorContext, 
        attempt: int, 
        config: RetryConfig
    ) -> float:
        """Calculate adaptive delay based on error type and recovery action."""
        classification = self.error_classifier.classify_error(error_context)
        recovery_action = classification.recovery_action
        
        # Base delay calculation
        base_delay = config.get_delay(attempt)
        
        # Adjust delay based on error type
        if classification.category == ErrorCategory.API_RATE_LIMIT:
            # Longer delays for rate limiting
            base_delay *= 3
        elif classification.category == ErrorCategory.RESOURCE_EXHAUSTION:
            # Even longer delays for resource issues
            base_delay *= 5
        elif classification.severity == ErrorSeverity.CRITICAL:
            # Shorter delays for critical issues to fail fast
            base_delay *= 0.5
        
        # Apply recovery action modifiers
        if recovery_action == RecoveryAction.RETRY_WITH_BACKOFF:
            # Standard exponential backoff
            pass
        elif recovery_action == RecoveryAction.REDUCE_LOAD:
            # Longer delays to reduce system load
            base_delay *= 2
        
        return min(base_delay, config.max_delay)
    
    def _handle_escalation(self, error_context: ErrorContext) -> None:
        """Handle error escalation when threshold is reached."""
        operation_key = f"{error_context.collector_type}:{error_context.operation}"
        
        self._escalation_counts[operation_key] = self._escalation_counts.get(operation_key, 0) + 1
        
        escalation_threshold = self.error_classifier.get_escalation_threshold(error_context)
        
        if self._escalation_counts[operation_key] >= escalation_threshold:
            logger.critical(
                f"Error escalation threshold reached for {operation_key}. "
                f"Count: {self._escalation_counts[operation_key]}, "
                f"Threshold: {escalation_threshold}, "
                f"Error: {error_context.error}"
            )
            
            # Reset escalation count after escalation
            self._escalation_counts[operation_key] = 0
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics and analysis."""
        stats = {
            "total_operations": len(self._error_history),
            "total_errors": sum(len(errors) for errors in self._error_history.values()),
            "escalation_counts": dict(self._escalation_counts),
            "error_by_category": {},
            "error_by_severity": {},
            "recent_errors": []
        }
        
        # Analyze errors by category and severity
        for operation, errors in self._error_history.items():
            for error_context in errors[-10:]:  # Last 10 errors per operation
                classification = self.error_classifier.classify_error(error_context)
                
                # Count by category
                category = classification.category.value
                stats["error_by_category"][category] = stats["error_by_category"].get(category, 0) + 1
                
                # Count by severity
                severity = classification.severity.value
                stats["error_by_severity"][severity] = stats["error_by_severity"].get(severity, 0) + 1
                
                # Add to recent errors
                stats["recent_errors"].append({
                    "operation": operation,
                    "error_type": type(error_context.error).__name__,
                    "error_message": str(error_context.error),
                    "category": category,
                    "severity": severity,
                    "timestamp": error_context.timestamp.isoformat(),
                    "attempt": error_context.attempt_number
                })
        
        # Sort recent errors by timestamp
        stats["recent_errors"].sort(key=lambda x: x["timestamp"], reverse=True)
        stats["recent_errors"] = stats["recent_errors"][:50]  # Keep last 50
        
        return stats
    
    def get_circuit_breaker_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers."""
        status = {}
        for name, breaker in self._circuit_breakers.items():
            status[name] = {
                "state": breaker.state.value,
                "failure_count": breaker._failure_count,
                "last_failure": breaker._last_failure_time.isoformat() if breaker._last_failure_time else None
            }
        return status
    
    def reset_error_history(self, operation_key: Optional[str] = None) -> None:
        """Reset error history for debugging or maintenance."""
        if operation_key:
            if operation_key in self._error_history:
                del self._error_history[operation_key]
            if operation_key in self._escalation_counts:
                del self._escalation_counts[operation_key]
            logger.info(f"Reset error history for {operation_key}")
        else:
            self._error_history.clear()
            self._escalation_counts.clear()
            logger.info("Reset all error history")
    
    def get_health_score(self) -> float:
        """Calculate overall health score based on recent error patterns."""
        if not self._error_history:
            return 1.0
        
        total_operations = len(self._error_history)
        total_errors = sum(len(errors) for errors in self._error_history.values())
        
        if total_errors == 0:
            return 1.0
        
        # Calculate error rate
        error_rate = total_errors / max(total_operations * 10, 1)  # Assume 10 attempts per operation
        
        # Adjust for error severity
        severity_weight = 0
        for errors in self._error_history.values():
            for error_context in errors[-5:]:  # Recent errors
                classification = self.error_classifier.classify_error(error_context)
                if classification.severity == ErrorSeverity.CRITICAL:
                    severity_weight += 0.4
                elif classification.severity == ErrorSeverity.HIGH:
                    severity_weight += 0.3
                elif classification.severity == ErrorSeverity.MEDIUM:
                    severity_weight += 0.2
                else:
                    severity_weight += 0.1
        
        # Calculate health score (0.0 to 1.0)
        health_score = max(0.0, 1.0 - error_rate - (severity_weight / 100))
        return min(1.0, health_score)