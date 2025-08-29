"""
Error handling utilities with exponential backoff and circuit breaker patterns.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Type, Union
from datetime import datetime, timedelta

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
    for resilient error handling in data collection operations.
    """
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
    
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
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic and optional circuit breaker.
        
        Args:
            func: Function to execute
            context: Context description for logging
            circuit_breaker_name: Name of circuit breaker to use (optional)
            retry_config: Override retry configuration (optional)
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
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
                
                if attempt == config.max_retries:
                    logger.error(
                        f"All retry attempts exhausted for {context}. "
                        f"Final error: {e}"
                    )
                    break
                
                delay = config.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed for {context}: {e}. "
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