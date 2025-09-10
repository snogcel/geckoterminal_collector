#!/usr/bin/env python3
"""
Enhanced Rate Limiter Demo

This script demonstrates the usage of the EnhancedRateLimiter and GlobalRateLimitCoordinator
for managing API rate limits with exponential backoff and circuit breaker functionality.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from gecko_terminal_collector.utils.enhanced_rate_limiter import (
    EnhancedRateLimiter,
    GlobalRateLimitCoordinator,
    RateLimitExceededError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_basic_rate_limiter():
    """Demonstrate basic rate limiter functionality."""
    logger.info("=== Basic Rate Limiter Demo ===")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        state_file = f.name
    
    try:
        # Create rate limiter with low limits for demo
        limiter = EnhancedRateLimiter(
            requests_per_minute=5,  # Very low for demo
            daily_limit=20,
            state_file=state_file,
            instance_id="demo_limiter"
        )
        
        logger.info("Making 3 requests within limits...")
        for i in range(3):
            await limiter.acquire()
            logger.info(f"Request {i+1} successful")
        
        # Show status
        status = limiter.get_status()
        logger.info(f"Current status: {status['daily_requests']}/{status['daily_limit']} daily requests")
        
        # Simulate rate limit response
        logger.info("Simulating rate limit response...")
        await limiter.handle_rate_limit_response({'Retry-After': '2'}, 429)
        
        logger.info("Attempting request after rate limit (should wait)...")
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire()
        end_time = asyncio.get_event_loop().time()
        logger.info(f"Request completed after {end_time - start_time:.2f}s wait")
        
        # Simulate success to reset backoff
        await limiter.handle_success()
        logger.info("Success handled, backoff reset")
        
    finally:
        Path(state_file).unlink(missing_ok=True)


async def demo_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    logger.info("\n=== Circuit Breaker Demo ===")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        state_file = f.name
    
    try:
        # Create rate limiter with low circuit breaker threshold
        limiter = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=1000,
            circuit_breaker_threshold=2,  # Low threshold for demo
            circuit_breaker_timeout=3,    # Short timeout for demo
            state_file=state_file,
            instance_id="circuit_demo"
        )
        
        logger.info("Triggering circuit breaker with failures...")
        
        # Trigger failures to open circuit breaker
        for i in range(2):
            await limiter.handle_rate_limit_response({'Retry-After': '1'}, 429)
            logger.info(f"Failure {i+1} recorded")
        
        status = limiter.get_status()
        logger.info(f"Circuit breaker state: {status['circuit_state']}")
        
        # Try to make request with open circuit breaker
        try:
            await limiter.acquire()
            logger.error("This should not happen - circuit breaker should be open!")
        except RateLimitExceededError as e:
            logger.info(f"Circuit breaker blocked request: {e}")
        
        # Wait for circuit breaker timeout
        logger.info("Waiting for circuit breaker timeout...")
        await asyncio.sleep(3.5)
        
        # Should be able to make request now (half-open state)
        logger.info("Attempting request after timeout...")
        await limiter.acquire()
        logger.info("Request successful in half-open state")
        
        # Handle success to close circuit breaker
        await limiter.handle_success()
        status = limiter.get_status()
        logger.info(f"Circuit breaker state after success: {status['circuit_state']}")
        
    finally:
        Path(state_file).unlink(missing_ok=True)


async def demo_global_coordination():
    """Demonstrate global rate limit coordination."""
    logger.info("\n=== Global Coordination Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Get global coordinator
        coordinator = await GlobalRateLimitCoordinator.get_instance(
            requests_per_minute=10,
            daily_limit=50,
            state_dir=temp_dir
        )
        
        # Create multiple collectors
        collectors = []
        for i in range(3):
            limiter = await coordinator.get_limiter(f"collector_{i}")
            collectors.append(limiter)
        
        logger.info("Making requests from multiple collectors...")
        
        # Make requests from different collectors
        for i, collector in enumerate(collectors):
            logger.info(f"Making 2 requests from collector_{i}")
            await collector.acquire()
            await collector.acquire()
        
        # Show global status
        status = await coordinator.get_global_status()
        logger.info(f"Global usage: {status['global_usage']['total_daily_requests']} requests")
        logger.info(f"Usage percentage: {status['global_usage']['daily_usage_percentage']:.1f}%")
        
        for collector_id, collector_status in status['limiters'].items():
            logger.info(f"{collector_id}: {collector_status['daily_requests']} requests")


async def demo_persistence():
    """Demonstrate state persistence."""
    logger.info("\n=== State Persistence Demo ===")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        state_file = f.name
    
    try:
        # Create first limiter and make some requests
        logger.info("Creating first limiter and making requests...")
        limiter1 = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=100,
            state_file=state_file,
            instance_id="persistence_demo"
        )
        
        await limiter1.acquire()
        await limiter1.acquire()
        await limiter1.acquire()
        
        status1 = limiter1.get_status()
        logger.info(f"First limiter made {status1['daily_requests']} requests")
        
        # Create second limiter with same state file
        logger.info("Creating second limiter with same state file...")
        limiter2 = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=100,
            state_file=state_file,
            instance_id="persistence_demo"
        )
        
        status2 = limiter2.get_status()
        logger.info(f"Second limiter loaded {status2['daily_requests']} requests from state")
        
        # Make more requests with second limiter
        await limiter2.acquire()
        status2_after = limiter2.get_status()
        logger.info(f"Second limiter now has {status2_after['daily_requests']} requests")
        
    finally:
        Path(state_file).unlink(missing_ok=True)


async def main():
    """Run all demos."""
    logger.info("Enhanced Rate Limiter Demo Starting...")
    
    try:
        await demo_basic_rate_limiter()
        await demo_circuit_breaker()
        await demo_global_coordination()
        await demo_persistence()
        
        logger.info("\n=== All Demos Completed Successfully ===")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())