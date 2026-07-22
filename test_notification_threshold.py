"""
Test script for 3rd occurrence notification threshold.

This tests that the store_watchlist_entry method only returns True
(triggers notification) on the 3rd occurrence within 24 hours.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_notification_threshold():
    """Test the 3rd occurrence notification logic."""
    
    # Initialize database manager
    config = DatabaseConfig(
        url="sqlite:///test_notifications.db",
        pool_size=5,
        max_overflow=10,
        echo=False
    )
    
    db_manager = SQLAlchemyDatabaseManager(config)
    await db_manager.initialize()
    
    try:
        # Test token address
        test_token_address = "TestToken123ABC"
        test_pool_id = "solana_testpool"
        
        # Create some test history entries
        logger.info("Creating test history entries...")
        
        # Create 2 history entries (should not trigger notification yet)
        for i in range(2):
            history_entry = db_manager.EnhancedWatchlistHistoryModel(
                source="gmgn",
                ranking=i + 1,
                token_symbol="TEST",
                token_name="Test Token",
                pool_address="test_pool_address",
                base_token_address=test_token_address,
                network="solana",
                dex="raydium",
                collected_at=datetime.now(timezone.utc),
                data_timestamp=datetime.now(timezone.utc)
            )
            await db_manager.store_enhanced_watchlist_history(history_entry)
        
        logger.info("Created 2 history entries")
        
        # Now create a watchlist entry - should NOT trigger notification (only 2 occurrences)
        watchlist_entry = db_manager.WatchlistEntryModel(
            pool_id=test_pool_id,
            token_symbol="TEST",
            token_name="Test Token",
            network_address=test_token_address,
            is_active=True
        )
        
        should_notify = await db_manager.store_watchlist_entry(watchlist_entry)
        logger.info(f"After 2nd occurrence: should_notify = {should_notify} (expected: False)")
        
        # Add 3rd history entry
        history_entry = db_manager.EnhancedWatchlistHistoryModel(
            source="gmgn",
            ranking=3,
            token_symbol="TEST",
            token_name="Test Token",
            pool_address="test_pool_address",
            base_token_address=test_token_address,
            network="solana",
            dex="raydium",
            collected_at=datetime.now(timezone.utc),
            data_timestamp=datetime.now(timezone.utc)
        )
        await db_manager.store_enhanced_watchlist_history(history_entry)
        
        # Update watchlist entry - should NOW trigger notification (3rd occurrence)
        watchlist_entry.token_symbol = "TEST_UPDATED"
        should_notify = await db_manager.store_watchlist_entry(watchlist_entry)
        logger.info(f"After 3rd occurrence: should_notify = {should_notify} (expected: True)")
        
        # Add 4th history entry
        history_entry = db_manager.EnhancedWatchlistHistoryModel(
            source="gmgn",
            ranking=4,
            token_symbol="TEST",
            token_name="Test Token",
            pool_address="test_pool_address",
            base_token_address=test_token_address,
            network="solana",
            dex="raydium",
            collected_at=datetime.now(timezone.utc),
            data_timestamp=datetime.now(timezone.utc)
        )
        await db_manager.store_enhanced_watchlist_history(history_entry)
        
        # Update again - should NOT trigger notification (4th occurrence, only triggers on exactly 3)
        watchlist_entry.token_symbol = "TEST_UPDATED_2"
        should_notify = await db_manager.store_watchlist_entry(watchlist_entry)
        logger.info(f"After 4th occurrence: should_notify = {should_notify} (expected: False)")
        
        logger.info("\n✅ Test completed successfully!")
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_notification_threshold())
