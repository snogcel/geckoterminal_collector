"""
Enhanced Rate Limiter with exponential backoff, daily limits, and global coordination.

This module provides a sophisticated rate limiting system for the GeckoTerminal API
that handles both per-minute and daily rate limits, implements exponential backoff
with jitter for 429 responses, and provides global coordination across collectors.
"""

import asyncio
import json
import logging
import random
import time
from collections import deque
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Dict, Optional, Any, Deque
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class RateLimitExceededError(Exception):
    """Raised when rate limits are exceeded."""
    pass


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RateLimitMetrics:
    """Metrics for rate limiting behavior."""
    total_requests: int = 0
    daily_requests: int = 0
    rate_limit_hits: int = 0
    backoff_events: int = 0
    circuit_breaker_trips: int = 0
    last_reset: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        data = asdict(self)
        if self.last_reset:
            data['last_reset'] = self.last_reset.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RateLimitMetrics':
        """Create metrics from dictionary."""
        if 'last_reset' in data and data['last_reset']:
            data['last_reset'] = datetime.fromisoformat(data['last_reset'])
        return cls(**data)


@dataclass
class BackoffState:
    """State for exponential backoff."""
    consecutive_failures: int = 0
    backoff_until: Optional[datetime] = None
    base_delay: float = 1.0
    max_delay: float = 300.0
    jitter_factor: float = 0.3


class EnhancedRateLimiter:
    """
    Enhanced rate limiter with exponential backoff and global coordination.
    
    Features:
    - Per-minute and daily rate limits
    - Exponential backoff with jitter for 429 responses
    - Circuit breaker pattern for persistent failures
    - Global coordination across multiple instances
    - Persistent state management
    - Comprehensive metrics tracking
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        daily_limit: int = 10000,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,
        state_file: Optional[str] = None,
        instance_id: str = "default"
    ):
        """
        Initialize the enhanced rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            daily_limit: Maximum requests per day
            circuit_breaker_threshold: Failures before opening circuit
            circuit_breaker_timeout: Seconds to wait before half-open
            state_file: Path to persistent state file
            instance_id: Unique identifier for this instance
        """
        self.requests_per_minute = requests_per_minute
        self.daily_limit = daily_limit
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.instance_id = instance_id
        
        # Request tracking
        self.request_history: Deque[float] = deque()
        self.daily_count = 0
        self.last_reset = date.today()
        
        # Backoff state
        self.backoff_state = BackoffState()
        
        # Circuit breaker state
        self.circuit_state = CircuitBreakerState.CLOSED
        self.circuit_failure_count = 0
        self.circuit_last_failure: Optional[datetime] = None
        self.circuit_next_attempt: Optional[datetime] = None
        
        # Metrics
        self.metrics = RateLimitMetrics(last_reset=datetime.now())
        
        # State persistence
        self.state_file = Path(state_file) if state_file else None
        self._lock = asyncio.Lock()
        
        # Load persistent state if available
        self._load_state()
    
    async def acquire(self, endpoint: str = "default") -> None:
        """
        Acquire permission to make an API request.
        
        Args:
            endpoint: API endpoint identifier for tracking
            
        Raises:
            RateLimitExceededError: If rate limits are exceeded
            CircuitBreakerOpenError: If circuit breaker is open
        """
        async with self._lock:
            # Check circuit breaker
            await self._check_circuit_breaker()
            
            # Check daily limit reset
            if self._check_daily_reset():
                self.daily_count = 0
                self.metrics.daily_requests = 0
                self.metrics.last_reset = datetime.now()
                logger.info("Daily rate limit reset")
            
            # Check daily limit
            if self.daily_count >= self.daily_limit:
                self.metrics.rate_limit_hits += 1
                raise RateLimitExceededError(
                    f"Daily API limit of {self.daily_limit} requests exceeded"
                )
            
            # Check if in backoff period
            if (self.backoff_state.backoff_until and 
                datetime.now() < self.backoff_state.backoff_until):
                wait_time = (self.backoff_state.backoff_until - datetime.now()).total_seconds()
                logger.info(f"Waiting {wait_time:.2f}s due to backoff")
                await asyncio.sleep(wait_time)
            
            # Check per-minute limit
            await self._wait_for_rate_limit()
            
            # Record the request
            now = time.time()
            self.request_history.append(now)
            self.daily_count += 1
            self.metrics.total_requests += 1
            self.metrics.daily_requests += 1
            
            # Save state
            self._save_state()
    
    async def handle_rate_limit_response(
        self, 
        response_headers: Dict[str, str],
        status_code: int = 429
    ) -> None:
        """
        Handle a rate limit response from the API.
        
        Args:
            response_headers: HTTP response headers
            status_code: HTTP status code
        """
        async with self._lock:
            self.metrics.rate_limit_hits += 1
            
            # Extract retry-after header
            retry_after = self._extract_retry_after(response_headers)
            
            # Implement exponential backoff with jitter
            self.backoff_state.consecutive_failures += 1
            base_delay = min(
                retry_after * (2 ** self.backoff_state.consecutive_failures),
                self.backoff_state.max_delay
            )
            
            # Add jitter
            jitter = random.uniform(
                -self.backoff_state.jitter_factor * base_delay,
                self.backoff_state.jitter_factor * base_delay
            )
            total_delay = max(base_delay + jitter, retry_after)
            
            self.backoff_state.backoff_until = datetime.now() + timedelta(seconds=total_delay)
            self.metrics.backoff_events += 1
            
            logger.warning(
                f"Rate limit hit (status: {status_code}). "
                f"Backing off for {total_delay:.2f}s. "
                f"Consecutive failures: {self.backoff_state.consecutive_failures}"
            )
            
            # Update circuit breaker
            await self._record_failure()
            
            # Save state
            self._save_state()
    
    async def handle_success(self) -> None:
        """Handle a successful API response."""
        async with self._lock:
            # Reset backoff on success
            if self.backoff_state.consecutive_failures > 0:
                logger.info("API call successful, resetting backoff")
                self.backoff_state.consecutive_failures = 0
                self.backoff_state.backoff_until = None
            
            # Reset circuit breaker on success
            if self.circuit_state != CircuitBreakerState.CLOSED:
                logger.info("API call successful, closing circuit breaker")
                self.circuit_state = CircuitBreakerState.CLOSED
                self.circuit_failure_count = 0
                self.circuit_last_failure = None
                self.circuit_next_attempt = None
            
            # Save state
            self._save_state()
    
    def get_metrics(self) -> RateLimitMetrics:
        """Get current rate limiting metrics."""
        return self.metrics
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        now = datetime.now()
        return {
            "instance_id": self.instance_id,
            "daily_requests": self.daily_count,
            "daily_limit": self.daily_limit,
            "requests_per_minute": self.requests_per_minute,
            "circuit_state": self.circuit_state.value,
            "consecutive_failures": self.backoff_state.consecutive_failures,
            "backoff_until": self.backoff_state.backoff_until.isoformat() if self.backoff_state.backoff_until else None,
            "next_daily_reset": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(),
            "metrics": self.metrics.to_dict()
        }
    
    async def _check_circuit_breaker(self) -> None:
        """Check and update circuit breaker state."""
        now = datetime.now()
        
        if self.circuit_state == CircuitBreakerState.OPEN:
            if (self.circuit_next_attempt and now >= self.circuit_next_attempt):
                logger.info("Circuit breaker transitioning to half-open")
                self.circuit_state = CircuitBreakerState.HALF_OPEN
            else:
                raise RateLimitExceededError(
                    f"Circuit breaker is open. Next attempt at: {self.circuit_next_attempt}"
                )
    
    async def _record_failure(self) -> None:
        """Record a failure for circuit breaker tracking."""
        self.circuit_failure_count += 1
        self.circuit_last_failure = datetime.now()
        
        if (self.circuit_failure_count >= self.circuit_breaker_threshold and 
            self.circuit_state == CircuitBreakerState.CLOSED):
            logger.error(
                f"Circuit breaker opening after {self.circuit_failure_count} failures"
            )
            self.circuit_state = CircuitBreakerState.OPEN
            self.circuit_next_attempt = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
            self.metrics.circuit_breaker_trips += 1
    
    def _check_daily_reset(self) -> bool:
        """Check if daily limits should be reset."""
        today = date.today()
        if today > self.last_reset:
            self.last_reset = today
            return True
        return False
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect per-minute rate limits."""
        now = time.time()
        
        # Remove old requests (older than 1 minute)
        cutoff = now - 60
        while self.request_history and self.request_history[0] < cutoff:
            self.request_history.popleft()
        
        # Check if we're at the limit
        if len(self.request_history) >= self.requests_per_minute:
            # Calculate wait time until oldest request is > 1 minute old
            oldest_request = self.request_history[0]
            wait_time = 60 - (now - oldest_request)
            
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    def _extract_retry_after(self, headers: Dict[str, str]) -> float:
        """Extract retry-after value from response headers."""
        retry_after = headers.get('Retry-After', headers.get('retry-after', '60'))
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            logger.warning(f"Invalid Retry-After header: {retry_after}, using default 60s")
            return 60.0
    
    def _load_state(self) -> None:
        """Load persistent state from file."""
        if not self.state_file or not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Load metrics
            if 'metrics' in state:
                self.metrics = RateLimitMetrics.from_dict(state['metrics'])
            
            # Load daily count and reset date
            if 'daily_count' in state:
                self.daily_count = state['daily_count']
            if 'last_reset' in state:
                self.last_reset = date.fromisoformat(state['last_reset'])
            
            # Load backoff state
            if 'backoff_state' in state:
                bs = state['backoff_state']
                self.backoff_state.consecutive_failures = bs.get('consecutive_failures', 0)
                if bs.get('backoff_until'):
                    self.backoff_state.backoff_until = datetime.fromisoformat(bs['backoff_until'])
            
            # Load circuit breaker state
            if 'circuit_state' in state:
                self.circuit_state = CircuitBreakerState(state['circuit_state'])
            if 'circuit_failure_count' in state:
                self.circuit_failure_count = state['circuit_failure_count']
            if 'circuit_next_attempt' in state and state['circuit_next_attempt']:
                self.circuit_next_attempt = datetime.fromisoformat(state['circuit_next_attempt'])
            
            logger.info(f"Loaded rate limiter state from {self.state_file}")
            
        except Exception as e:
            logger.warning(f"Failed to load rate limiter state: {e}")
    
    def _save_state(self) -> None:
        """Save persistent state to file."""
        if not self.state_file:
            return
        
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                'instance_id': self.instance_id,
                'daily_count': self.daily_count,
                'last_reset': self.last_reset.isoformat(),
                'metrics': self.metrics.to_dict(),
                'backoff_state': {
                    'consecutive_failures': self.backoff_state.consecutive_failures,
                    'backoff_until': self.backoff_state.backoff_until.isoformat() if self.backoff_state.backoff_until else None
                },
                'circuit_state': self.circuit_state.value,
                'circuit_failure_count': self.circuit_failure_count,
                'circuit_next_attempt': self.circuit_next_attempt.isoformat() if self.circuit_next_attempt else None
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save rate limiter state: {e}")


class GlobalRateLimitCoordinator:
    """
    Coordinates rate limiting across multiple collector instances.
    
    This class provides a shared rate limiting mechanism that can be used
    by multiple collectors to ensure global API usage stays within limits.
    """
    
    _instance: Optional['GlobalRateLimitCoordinator'] = None
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        daily_limit: int = 10000,
        state_dir: Optional[str] = None
    ):
        """Initialize the global coordinator."""
        self.requests_per_minute = requests_per_minute
        self.daily_limit = daily_limit
        self.state_dir = Path(state_dir) if state_dir else Path.cwd() / ".rate_limiter_state"
        self.limiters: Dict[str, EnhancedRateLimiter] = {}
    
    @classmethod
    async def get_instance(
        cls,
        requests_per_minute: int = 60,
        daily_limit: int = 10000,
        state_dir: Optional[str] = None
    ) -> 'GlobalRateLimitCoordinator':
        """Get or create the global coordinator instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(requests_per_minute, daily_limit, state_dir)
            return cls._instance
    
    async def get_limiter(self, collector_id: str) -> EnhancedRateLimiter:
        """Get or create a rate limiter for a specific collector."""
        if collector_id not in self.limiters:
            state_file = self.state_dir / f"{collector_id}_rate_limiter.json"
            self.limiters[collector_id] = EnhancedRateLimiter(
                requests_per_minute=self.requests_per_minute,
                daily_limit=self.daily_limit,
                state_file=str(state_file),
                instance_id=collector_id
            )
        return self.limiters[collector_id]
    
    async def get_global_status(self) -> Dict[str, Any]:
        """Get status of all rate limiters."""
        status = {
            "total_limiters": len(self.limiters),
            "global_limits": {
                "requests_per_minute": self.requests_per_minute,
                "daily_limit": self.daily_limit
            },
            "limiters": {}
        }
        
        total_daily_requests = 0
        for collector_id, limiter in self.limiters.items():
            limiter_status = limiter.get_status()
            status["limiters"][collector_id] = limiter_status
            total_daily_requests += limiter_status["daily_requests"]
        
        status["global_usage"] = {
            "total_daily_requests": total_daily_requests,
            "daily_usage_percentage": (total_daily_requests / self.daily_limit) * 100
        }
        
        return status