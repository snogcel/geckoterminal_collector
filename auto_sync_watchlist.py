"""
Automated watchlist synchronization for integration into scheduled workflows.

This script can be imported and used in other scripts or run standalone.
It includes additional features for automation like retry logic and notifications.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from gecko_terminal_collector.config.config_loader import load_config
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Setup logging
logger = logging.getLogger(__name__)


class WatchlistSyncManager:
    """Manager for watchlist active status synchronization."""
    
    def __init__(
        self,
        json_path: str = "watchlist_state.json",
        config_path: str = "config.yaml",
        retry_attempts: int = 3,
        retry_delay: float = 5.0
    ):
        """
        Initialize the sync manager.
        
        Args:
            json_path: Path to watchlist state JSON file
            config_path: Path to configuration file
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds
        """
        self.json_path = json_path
        self.config_path = config_path
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.db_manager: Optional[SQLAlchemyDatabaseManager] = None
    
    async def load_state(self) -> Optional[Dict]:
        """Load watchlist state from JSON file."""
        try:
            path = Path(self.json_path)
            if not path.exists():
                logger.error(f"Watchlist state file not found: {self.json_path}")
                return None
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded watchlist state with {len(data.get('tokens', {}))} tokens")
            return data
        except Exception as e:
            logger.error(f"Error loading watchlist state: {e}")
            return None
    
    def extract_addresses(self, state_data: Dict) -> Dict[str, list]:
        """Extract active and inactive token addresses."""
        tokens = state_data.get('tokens', {})
        
        active = []
        inactive = []
        
        for address, data in tokens.items():
            if data.get('active', False):
                active.append(address)
            else:
                inactive.append(address)
        
        logger.info(f"Extracted {len(active)} active and {len(inactive)} inactive addresses")
        return {'active': active, 'inactive': inactive}
    
    async def initialize_database(self):
        """Initialize database connection."""
        try:
            config = load_config(self.config_path)
            self.db_manager = SQLAlchemyDatabaseManager(config.database)
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    async def close_database(self):
        """Close database connection."""
        if self.db_manager:
            await self.db_manager.close()
            logger.info("Database connection closed")
    
    async def perform_sync(self, addresses: Dict[str, list]) -> Optional[Dict]:
        """Perform the synchronization."""
        try:
            if not self.db_manager:
                logger.error("Database not initialized")
                return None
            
            stats = await self.db_manager.bulk_update_watchlist_active_status(addresses)
            logger.info(f"Sync completed: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            return None
    
    async def sync_with_retry(self) -> Optional[Dict]:
        """
        Perform synchronization with retry logic.
        
        Returns:
            Sync statistics or None on failure
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                logger.info(f"Sync attempt {attempt}/{self.retry_attempts}")
                
                # Load state
                state_data = await self.load_state()
                if not state_data:
                    logger.error("Failed to load state data")
                    if attempt < self.retry_attempts:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return None
                
                # Extract addresses
                addresses = self.extract_addresses(state_data)
                
                # Initialize database if needed
                if not self.db_manager:
                    success = await self.initialize_database()
                    if not success:
                        logger.error("Failed to initialize database")
                        if attempt < self.retry_attempts:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return None
                
                # Perform sync
                stats = await self.perform_sync(addresses)
                
                if stats and 'error' not in stats:
                    logger.info("✅ Synchronization successful")
                    return stats
                else:
                    logger.warning(f"Sync returned no stats or error")
                    if attempt < self.retry_attempts:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return None
                    
            except Exception as e:
                logger.error(f"Sync attempt {attempt} failed: {e}")
                if attempt < self.retry_attempts:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("All retry attempts exhausted")
                    return None
        
        return None
    
    async def sync(self, close_after: bool = True) -> Optional[Dict]:
        """
        Main sync method.
        
        Args:
            close_after: Whether to close database after sync
        
        Returns:
            Sync statistics or None on failure
        """
        try:
            stats = await self.sync_with_retry()
            return stats
        finally:
            if close_after:
                await self.close_database()


async def sync_watchlist_status(
    json_path: str = "watchlist_state.json",
    config_path: str = "config.yaml",
    retry_attempts: int = 3
) -> bool:
    """
    Convenience function for simple synchronization.
    
    Args:
        json_path: Path to watchlist state JSON file
        config_path: Path to configuration file
        retry_attempts: Number of retry attempts
    
    Returns:
        True if sync successful, False otherwise
    """
    manager = WatchlistSyncManager(
        json_path=json_path,
        config_path=config_path,
        retry_attempts=retry_attempts
    )
    
    stats = await manager.sync()
    
    if stats:
        logger.info("=" * 60)
        logger.info("Sync Summary:")
        logger.info(f"  Active updated: {stats.get('active_updated', 0)}")
        logger.info(f"  Inactive updated: {stats.get('inactive_updated', 0)}")
        logger.info(f"  Not found: {stats.get('not_found', 0)}")
        logger.info("=" * 60)
        return True
    else:
        logger.error("Synchronization failed")
        return False


async def main():
    """Main entry point for standalone execution."""
    # Setup logging for standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get paths from command line
    json_path = sys.argv[1] if len(sys.argv) > 1 else "watchlist_state.json"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    
    logger.info(f"Starting watchlist sync...")
    logger.info(f"JSON file: {json_path}")
    logger.info(f"Config file: {config_path}")
    
    success = await sync_watchlist_status(json_path, config_path)
    
    if success:
        logger.info("✅ Synchronization completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Synchronization failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
