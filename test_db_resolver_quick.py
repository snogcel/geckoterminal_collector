#!/usr/bin/env python3
"""
Quick test for the database address resolver.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.utils.database_address_resolver import EnhancedWatchlistDatabaseParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_resolver():
    """Test the database resolver."""
    
    print("🧪 Testing Database Address Resolver")
    print("=" * 50)
    
    try:
        # Initialize database
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print("✅ Database connected")
        
        # Initialize parser
        parser = EnhancedWatchlistDatabaseParser(db_manager)
        stats = await parser.initialize()
        
        print(f"📊 Cache Statistics:")
        print(f"  Total mappings: {stats['total_mappings']}")
        print(f"  Pools: {stats['pools_processed']}")
        print(f"  Tokens: {stats['tokens_processed']}")
        print(f"  History: {stats['history_processed']}")
        
        if stats['total_mappings'] > 0:
            print("✅ Database resolver is working!")
            print("🚀 Ready for enhanced watchlist collection")
        else:
            print("⚠️  No data in database - run new pools collection first")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_resolver())