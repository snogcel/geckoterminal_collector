"""
Test script for new pools pagination functionality.
"""

import asyncio
import logging
from gecko_terminal_collector.clients.gecko_client import GeckoTerminalClient
from gecko_terminal_collector.config.models import APIConfig, ErrorConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_pagination():
    """Test pagination for new pools collection."""
    
    # Create API config
    api_config = APIConfig(
        base_url="https://api.geckoterminal.com/api/v2",
        timeout=30,
        max_concurrent=5,
        rate_limit_delay=1.0
    )
    
    # Create error config
    error_config = ErrorConfig(
        max_retries=3,
        backoff_factor=2.0,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300
    )
    
    # Create client
    async with GeckoTerminalClient(api_config, error_config) as client:
        logger.info("Testing pagination for Solana new pools...")
        
        # Test fetching multiple pages
        all_pools = []
        seen_ids = set()
        
        for page in range(1, 4):  # Test first 3 pages
            logger.info(f"\n{'='*60}")
            logger.info(f"Fetching page {page}...")
            logger.info(f"{'='*60}")
            
            try:
                response = await client.get_new_pools_by_network("solana", page=page)
                
                # Debug: Show response type
                logger.info(f"Response type: {type(response)}")
                
                if response and isinstance(response, dict) and 'data' in response:
                    pools = response['data']
                    logger.info(f"Page {page}: Received {len(pools)} pools")
                    
                    # Check for duplicates
                    page_new = 0
                    for pool in pools:
                        pool_id = pool.get('id')
                        if pool_id:
                            if pool_id not in seen_ids:
                                all_pools.append(pool)
                                seen_ids.add(pool_id)
                                page_new += 1
                    
                    logger.info(f"Page {page}: {page_new} new pools (after deduplication)")
                    
                    # Show sample pool IDs
                    if pools:
                        sample_ids = [p.get('id', 'unknown')[:50] for p in pools[:3]]
                        logger.info(f"Sample pool IDs: {sample_ids}")
                    
                    # Show sample pool data structure
                    if pools and len(pools) > 0:
                        logger.info(f"Sample pool keys: {list(pools[0].keys())}")
                else:
                    logger.warning(f"Page {page}: No data received or unexpected format")
                    logger.warning(f"Response: {str(response)[:200]}")
                    break
                
                # Delay between pages
                if page < 3:
                    await asyncio.sleep(1.5)
                    
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total unique pools collected: {len(all_pools)}")
        logger.info(f"Total pools seen (with duplicates): {sum(1 for _ in all_pools)}")
        logger.info(f"Unique pool IDs: {len(seen_ids)}")


if __name__ == "__main__":
    asyncio.run(test_pagination())
