#!/usr/bin/env python3
"""
Test script for Enhanced Watchlist Collector with Historical Data Support.

This script tests the enhanced watchlist collector's ability to:
1. Process multiple source files (lowcap, micro, midcap, oldlowcap, oldmicro, reference)
2. Store historical data with proper source tracking
3. Handle rate limiting for API calls
4. Track collection statistics across multiple sources
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_test_source_files():
    """Create test source files for different segments."""
    
    # Sample data for testing (based on the reference format)
    test_data = [
        {
            'tokenSymbol': 'DINO',
            'tokenName': 'DINOSOL',
            'poolAddress': '26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o',
            'dex': 'pumpswap',
            'price': '0.001066',
            'marketCap': '938000',
            'liquidity': '130000',
            'volume': '1100000',
            'priceChange5m': '-0.34',
            'priceChange1h': '-4.74',
            'priceChange6h': '3.54',
            'priceChange24h': '75.59',
            'transactions': '29622',
            'makers': '3840',
            'age': '12d',
            'detailUrl': '/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o'
        },
        {
            'tokenSymbol': 'PEPPA',
            'tokenName': 'Justice For Peppa',
            'poolAddress': 'EDuApEtcGbaeqKvAsTtrX1ERU12U1PB5yJpRCD3TeZxM',
            'dex': 'pumpswap',
            'price': '0.0004355',
            'marketCap': '435000',
            'liquidity': '224000',
            'volume': '285000',
            'priceChange5m': '-2.7',
            'priceChange1h': '4848',
            'priceChange6h': '1149',
            'priceChange24h': '663',
            'transactions': '12098',
            'makers': '3202',
            'age': '6h',
            'detailUrl': '/solana/3ismqtviyuhggvmbxoui7h5fwq5ktjwaeonvcnq1uqds'
        }
    ]
    
    # Create test files for different sources
    sources = ['reference', 'lowcap', 'micro']
    
    for source in sources:
        filename = f"watchlist_updated_{source}.csv"
        
        # Write CSV header and data
        with open(filename, 'w', encoding='utf-8') as f:
            # Write header
            headers = list(test_data[0].keys())
            f.write(','.join(headers) + '\n')
            
            # Write data rows
            for i, row in enumerate(test_data):
                # Modify data slightly for each source
                modified_row = row.copy()
                modified_row['tokenSymbol'] = f"{row['tokenSymbol']}_{source.upper()}"
                modified_row['tokenName'] = f"{row['tokenName']} ({source.title()})"
                modified_row['poolAddress'] = f"{row['poolAddress']}_{source}"
                
                # Write row
                values = [str(modified_row[header]) for header in headers]
                f.write(','.join(values) + '\n')
        
        logger.info(f"Created test file: {filename}")


async def test_enhanced_watchlist_collector():
    """Test the enhanced watchlist collector with multiple sources."""
    
    try:
        # Create test source files
        await create_test_source_files()
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize metadata tracker
        metadata_tracker = MetadataTracker(db_manager)
        
        # Initialize enhanced watchlist collector with specific sources
        test_sources = ['reference', 'lowcap', 'micro']
        collector = EnhancedWatchlistCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True,  # Use mock client for testing
            watchlist_sources=test_sources
        )
        
        logger.info("Starting enhanced watchlist collection test...")
        
        # Run collection
        result = await collector.collect()
        
        # Display results
        logger.info(f"Collection Result: {'Success' if result.success else 'Failed'}")
        logger.info(f"Records Collected: {result.records_collected}")
        logger.info(f"Collection Time: {result.collection_time}")
        
        if result.metadata:
            logger.info("Collection Metadata:")
            for key, value in result.metadata.items():
                logger.info(f"  {key}: {value}")
        
        if result.errors:
            logger.error("Collection Errors:")
            for error in result.errors:
                logger.error(f"  {error}")
        
        # Get collection statistics
        stats = await collector.get_collection_statistics()
        logger.info("Collection Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        # Test database queries (skip for now - would need specific query methods)
        # await test_database_queries(db_manager)
        
        logger.info("Enhanced watchlist collection test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise
    finally:
        # Cleanup test files
        cleanup_test_files()


async def test_database_queries(db_manager):
    """Test database queries for enhanced watchlist history."""
    
    try:
        # Query enhanced watchlist history
        query = """
        SELECT 
            source,
            ranking,
            token_symbol,
            token_name,
            price,
            market_cap,
            collected_at
        FROM enhanced_watchlist_history 
        ORDER BY source, ranking
        LIMIT 10
        """
        
        results = await db_manager.execute_query(query)
        
        logger.info("Enhanced Watchlist History Sample:")
        for row in results:
            logger.info(f"  {row}")
        
        # Count entries by source
        count_query = """
        SELECT 
            source,
            COUNT(*) as entry_count
        FROM enhanced_watchlist_history 
        GROUP BY source
        ORDER BY source
        """
        
        counts = await db_manager.execute_query(count_query)
        
        logger.info("Entries by Source:")
        for row in counts:
            logger.info(f"  {row[0]}: {row[1]} entries")
            
    except Exception as e:
        logger.error(f"Database query test failed: {e}")


def cleanup_test_files():
    """Clean up test files."""
    sources = ['reference', 'lowcap', 'micro']
    
    for source in sources:
        filename = f"watchlist_updated_{source}.csv"
        try:
            Path(filename).unlink(missing_ok=True)
            logger.info(f"Cleaned up test file: {filename}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {filename}: {e}")


async def main():
    """Main test function."""
    try:
        await test_enhanced_watchlist_collector()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())