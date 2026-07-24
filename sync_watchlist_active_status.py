"""
Synchronize watchlist is_active status from watchlist_state.json file.

This script reads the watchlist_state.json file and updates the is_active
field in the database watchlist table based on the 'active' field in the JSON.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List

from gecko_terminal_collector.config.config_loader import load_config
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_watchlist_state(json_path: str = "watchlist_state.json") -> Dict:
    """Load watchlist state from JSON file."""
    try:
        path = Path(json_path)
        if not path.exists():
            logger.error(f"❌ Watchlist state file not found: {json_path}")
            return {}
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"✅ Loaded watchlist state from {json_path}")
        logger.info(f"📊 Total tokens in state file: {len(data.get('tokens', {}))}")
        
        return data
    except Exception as e:
        logger.error(f"❌ Error loading watchlist state: {e}")
        return {}


async def extract_active_status(watchlist_data: Dict) -> Dict[str, List[str]]:
    """
    Extract active and inactive token addresses from watchlist state.
    
    Args:
        watchlist_data: Loaded watchlist state JSON
    
    Returns:
        Dict with 'active' and 'inactive' lists of token addresses
    """
    tokens = watchlist_data.get('tokens', {})
    
    active_addresses = []
    inactive_addresses = []
    
    for token_address, token_data in tokens.items():
        is_active = token_data.get('active', False)
        
        if is_active:
            active_addresses.append(token_address)
        else:
            inactive_addresses.append(token_address)
    
    logger.info(f"📊 Status breakdown:")
    logger.info(f"   ✅ Active tokens: {len(active_addresses)}")
    logger.info(f"   ❌ Inactive tokens: {len(inactive_addresses)}")
    
    return {
        'active': active_addresses,
        'inactive': inactive_addresses
    }


async def sync_watchlist_active_status(
    json_path: str = "watchlist_state.json",
    config_path: str = "config.yaml"
) -> Dict:
    """
    Synchronize watchlist active status from JSON file to database.
    
    Args:
        json_path: Path to watchlist_state.json file
        config_path: Path to configuration file
    
    Returns:
        Dict with sync statistics
    """
    logger.info("🚀 Starting watchlist active status synchronization...")
    
    # Load watchlist state
    watchlist_data = await load_watchlist_state(json_path)
    if not watchlist_data:
        logger.error("❌ No watchlist data to sync")
        return {'error': 'Failed to load watchlist data'}
    
    # Extract active/inactive addresses
    addresses_by_status = await extract_active_status(watchlist_data)
    
    if not addresses_by_status['active'] and not addresses_by_status['inactive']:
        logger.warning("⚠️ No tokens found in watchlist state")
        return {'warning': 'No tokens to sync'}
    
    # Load config and initialize database
    try:
        config = load_config(config_path)
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        return {'error': f'Database initialization failed: {e}'}
    
    # Perform bulk update
    try:
        logger.info("🔄 Updating watchlist active status in database...")
        stats = await db_manager.bulk_update_watchlist_active_status(addresses_by_status)
        
        logger.info("=" * 60)
        logger.info("✅ Synchronization completed successfully!")
        logger.info(f"📊 Results:")
        logger.info(f"   ✅ Tokens set to active: {stats['active_updated']}")
        logger.info(f"   ❌ Tokens set to inactive: {stats['inactive_updated']}")
        logger.info(f"   ⚠️  Tokens not found in DB: {stats['not_found']}")
        logger.info("=" * 60)
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error during bulk update: {e}")
        return {'error': f'Bulk update failed: {e}'}
    
    finally:
        await db_manager.close()
        logger.info("🔒 Database connection closed")


async def main():
    """Main entry point."""
    import sys
    
    # Get JSON path from command line or use default
    json_path = sys.argv[1] if len(sys.argv) > 1 else "watchlist_state.json"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    
    logger.info(f"📄 Using watchlist state file: {json_path}")
    logger.info(f"⚙️  Using config file: {config_path}")
    logger.info("")
    
    stats = await sync_watchlist_active_status(json_path, config_path)
    
    # Exit with error code if sync failed
    if 'error' in stats:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
