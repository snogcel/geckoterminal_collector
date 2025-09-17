#!/usr/bin/env python3
"""
Quick script to test watchlist database operations directly.
"""

import asyncio
import yaml
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager


async def test_watchlist_db():
    """Test watchlist database operations."""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config['database'])
    
    try:
        # Test database connection
        print("🔌 Testing database connection...")
        await db_manager.initialize()
        print("✅ Database connected successfully")
        
        # Get all watchlist entries
        print("\n📋 Current watchlist entries:")
        all_entries = await db_manager.get_all_watchlist_entries()
        
        if not all_entries:
            print("   No entries found")
        else:
            for entry in all_entries:
                status = "🟢 Active" if entry.is_active else "🔴 Inactive"
                print(f"   {status} {entry.symbol} ({entry.pool_id})")
                print(f"      Name: {entry.name or 'N/A'}")
                print(f"      Added: {entry.added_at}")
                print()
        
        # Get only active entries
        print("🟢 Active watchlist entries:")
        active_entries = await db_manager.get_active_watchlist_entries()
        
        if not active_entries:
            print("   No active entries found")
        else:
            for entry in active_entries:
                print(f"   {entry.symbol} - {entry.name or 'N/A'}")
        
        print(f"\n📊 Summary:")
        print(f"   Total entries: {len(all_entries)}")
        print(f"   Active entries: {len(active_entries)}")
        print(f"   Inactive entries: {len(all_entries) - len(active_entries)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_watchlist_db())