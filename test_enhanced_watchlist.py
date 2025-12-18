#!/usr/bin/env python3
"""
Test script for enhanced watchlist functionality.

Tests address parsing, case correction, and API integration.
"""

import asyncio
import logging
from pathlib import Path

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector
from gecko_terminal_collector.utils.address_parser import SolanaAddressParser, EnhancedWatchlistParser
from gecko_terminal_collector.clients import create_gecko_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_address_parsing():
    """Test address parsing functionality."""
    print("\n=== Testing Address Parsing ===")
    
    parser = SolanaAddressParser()
    
    # Test cases from your data
    test_urls = [
        "/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o",
        "/solana/3ismqtviyuhggvmbxoui7h5fwq5ktjwaeonvcnq1uqds",
        "/solana/ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9"
    ]
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        
        # Extract address
        address = parser.extract_pool_address_from_url(url)
        print(f"  Extracted: {address}")
        
        # Test validation
        is_valid = parser.is_valid_solana_address(address) if address else False
        print(f"  Valid: {is_valid}")
        
        if address:
            # Test case correction (this is heuristic)
            corrected = parser.correct_case_sensitivity(address.lower())
            print(f"  Case corrected: {corrected}")


async def test_enhanced_parser():
    """Test enhanced watchlist parser with API calls."""
    print("\n=== Testing Enhanced Parser (with API) ===")
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Create client
    client = create_gecko_client(config.api, config.error_handling, use_mock=True)
    
    # Create parser
    parser = EnhancedWatchlistParser(client)
    
    # Test data row
    test_row = {
        'timestamp': '12/17/2025 21:20',
        'ranking': '1',
        'tokenSymbol': 'DINO',
        'tokenName': 'DINOSOL',
        'chain': 'SOL',
        'dex': 'PumpSwap',
        'price': '0.001132',
        'age': '12d',
        'transactions': '29560',
        'volume': '1100000',
        'makers': '3838',
        'priceChange5m': '1.05',
        'priceChange1h': '-10.78',
        'priceChange6h': '5.94',
        'priceChange24h': '77.11',
        'liquidity': '134000',
        'marketCap': '996000',
        'detailUrl': '/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o'
    }
    
    print(f"Testing row: {test_row['tokenSymbol']}")
    
    try:
        # Parse the entry (this will make API calls)
        entry = await parser.parse_watchlist_entry(test_row)
        
        if entry:
            print("✓ Successfully parsed entry:")
            print(f"  Token: {entry['tokenSymbol']} ({entry['tokenName']})")
            print(f"  Pool Address: {entry['poolAddress']}")
            print(f"  Base Token: {entry.get('baseTokenAddress', 'Not resolved')}")
            print(f"  Quote Token: {entry.get('quoteTokenAddress', 'Not resolved')}")
            print(f"  Ranking: {entry['ranking']}")
            print(f"  Price: ${entry['price']}")
            print(f"  24h Change: {entry['priceChange24h']}%")
            print(f"  Volume: ${entry['volume']:,}")
            print(f"  Liquidity: ${entry['liquidity']:,}")
        else:
            print("✗ Failed to parse entry")
            
    except Exception as e:
        print(f"✗ Error parsing entry: {e}")


async def test_enhanced_collector():
    """Test the full enhanced watchlist collector."""
    print("\n=== Testing Enhanced Watchlist Collector ===")
    
    # Check if enhanced watchlist file exists
    source_file = Path("enhanced_watchlist.csv")
    expected_file = Path("watchlist_updated_reference.csv")
    
    if not source_file.exists():
        print(f"✗ Enhanced watchlist file not found: {source_file}")
        return
    
    # Copy the file to the expected name for the collector
    import shutil
    shutil.copy2(source_file, expected_file)
    
    print(f"✓ Found enhanced watchlist file: {source_file}")
    print(f"✓ Created expected file: {expected_file}")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Create collector
        collector = EnhancedWatchlistCollector(
            config=config,
            db_manager=db_manager,
            use_mock=True,  # Use mock for testing
            watchlist_sources=['reference']  # Use single source for this test
        )
        
        print("✓ Created enhanced watchlist collector")
        
        # Run collection
        print("Running collection...")
        result = await collector.collect()
        
        # Display results
        print(f"\n=== Collection Results ===")
        print(f"Success: {result.success}")
        print(f"Records Collected: {result.records_collected}")
        print(f"Collection Time: {result.collection_time}")
        
        if result.metadata:
            print(f"Entries Processed: {result.metadata.get('entries_processed', 0)}")
            print(f"Addresses Resolved: {result.metadata.get('addresses_resolved', 0)}")
            print(f"API Calls Made: {result.metadata.get('api_calls_made', 0)}")
        
        if result.errors:
            print(f"Errors: {result.errors}")
        
        # Get statistics
        stats = await collector.get_collection_statistics()
        print(f"\n=== Collector Statistics ===")
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        await db_manager.close()
        
        # Cleanup
        if expected_file.exists():
            expected_file.unlink()
            print(f"✓ Cleaned up: {expected_file}")
        
    except Exception as e:
        print(f"✗ Error testing collector: {e}")
        logger.error("Collector test failed", exc_info=True)
        
        # Cleanup on error
        expected_file = Path("watchlist_updated_reference.csv")
        if expected_file.exists():
            expected_file.unlink()
            print(f"✓ Cleaned up: {expected_file}")


async def main():
    """Run all tests."""
    print("🧪 Enhanced Watchlist Testing Suite")
    print("=" * 50)
    
    # Test 1: Address parsing
    await test_address_parsing()
    
    # Test 2: Enhanced parser with API
    await test_enhanced_parser()
    
    # Test 3: Full collector
    await test_enhanced_collector()
    
    print("\n" + "=" * 50)
    print("✅ Testing completed!")


if __name__ == "__main__":
    asyncio.run(main())