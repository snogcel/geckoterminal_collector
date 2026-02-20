#!/usr/bin/env python3
"""
Test script for lazy loading address resolver.

This tests that lowercase addresses can be properly resolved to their
correct mixed-case versions using the database.
"""

import asyncio
import logging

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.utils.database_address_resolver import EnhancedWatchlistDatabaseParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_lazy_loading():
    """Test lazy loading address resolution."""
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.get_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        logger.info("Testing lazy loading address resolver...")
        
        # Create parser with lazy loading (default)
        parser = EnhancedWatchlistDatabaseParser(db_manager)
        
        # Initialize - should be instant with lazy loading
        import time
        start = time.time()
        stats = await parser.initialize(use_lazy_loading=True)
        init_time = time.time() - start
        
        logger.info(f"✅ Initialization completed in {init_time:.3f} seconds")
        logger.info(f"   Mode: {stats.get('mode', 'cached')}")
        logger.info(f"   Mappings loaded: {stats['total_mappings']}")
        
        # Test with lowercase addresses
        test_cases = [
            {
                'lowercase': 'hgummd4ljnodxgksz1draaokpatmh7ntug2ncdzyat4u',
                'expected': 'HGumMd4LJNodxGksZ1drAAoKpatmH7NTug2nCdzYAT4U',
                'description': 'Mixed case Solana address'
            },
            {
                'lowercase': '26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o',
                'expected': None,  # We don't know the expected value
                'description': 'Another Solana address'
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\nTest {i}: {test_case['description']}")
            logger.info(f"  Lowercase input: {test_case['lowercase']}")
            
            start = time.time()
            resolved = parser.address_resolver.resolve_pool_address(test_case['lowercase'])
            query_time = time.time() - start
            
            if resolved:
                logger.info(f"  ✅ Resolved in {query_time*1000:.1f}ms")
                logger.info(f"     Proper case: {resolved['address']}")
                logger.info(f"     Source: {resolved['source']}")
                logger.info(f"     Pool ID: {resolved.get('pool_id', 'N/A')}")
                
                if test_case['expected']:
                    if resolved['address'] == test_case['expected']:
                        logger.info(f"     ✅ Matches expected value")
                    else:
                        logger.warning(f"     ⚠️  Expected: {test_case['expected']}")
                        logger.warning(f"     ⚠️  Got: {resolved['address']}")
            else:
                logger.warning(f"  ❌ Not found in database (query took {query_time*1000:.1f}ms)")
                
                # Try to find similar addresses
                similar = parser.address_resolver.search_similar_addresses(
                    test_case['lowercase'], 
                    max_results=3
                )
                if similar:
                    logger.info(f"     Similar addresses found:")
                    for sim in similar:
                        logger.info(f"       - {sim['address']} (similarity: {sim['similarity']:.2f})")
        
        # Test caching - second lookup should be instant
        logger.info("\nTesting cache performance...")
        if test_cases[0]['lowercase']:
            start = time.time()
            resolved = parser.address_resolver.resolve_pool_address(test_cases[0]['lowercase'])
            cached_time = time.time() - start
            
            if resolved:
                logger.info(f"✅ Cached lookup: {cached_time*1000:.3f}ms (should be <1ms)")
        
        # Get final statistics
        final_stats = await parser.get_resolution_statistics()
        logger.info(f"\nFinal Statistics:")
        logger.info(f"  Cache built: {final_stats['cache_built']}")
        logger.info(f"  Total mappings cached: {final_stats['total_mappings']}")
        logger.info(f"  Cache size: {final_stats['cache_size_mb']:.2f} MB")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    
    finally:
        await db_manager.close()


if __name__ == '__main__':
    asyncio.run(test_lazy_loading())
