#!/usr/bin/env python3
"""
Check active watchlist entries in the database.
"""

import asyncio
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager

async def get_watchlist():
    config = ConfigManager()
    config_obj = config.load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config_obj.database)
    
    # Initialize the database manager
    await db_manager.initialize()
    
    # Get active watchlist entries
    entries = await db_manager.get_active_watchlist_entries()
    
    print('Active Watchlist Entries:')
    print('=' * 50)
    for entry in entries:
        print(f'Pool ID: {entry.pool_id}')
        print(f'Symbol: {entry.token_symbol}')
        print(f'Name: {entry.token_name}')
        print(f'Network Address: {entry.network_address}')
        print(f'Active: {entry.is_active}')
        print('-' * 30)
    
    print(f'Total active entries: {len(entries)}')
    
    # Also get the pool IDs for historical collection
    pool_ids = await db_manager.get_watchlist_pools()
    print(f'\nActive pool IDs for collection: {pool_ids}')
    
    await db_manager.close()
    return entries

if __name__ == "__main__":
    asyncio.run(get_watchlist())