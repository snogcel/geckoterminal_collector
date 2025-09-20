"""
Quick test of the enhanced pool ID lookup functionality.
"""

import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.utils.pool_id_utils import PoolIDUtils


async def test_pool_lookup():
    """Test the enhanced pool ID lookup functionality."""
    
    # Initialize database
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get a sample pool ID from the database
        with db_manager.connection.get_session() as session:
            from gecko_terminal_collector.database.models import Pool
            sample_pool = session.query(Pool).first()
            
            if not sample_pool:
                print("No pools found in database")
                return
                
            full_id = sample_pool.id
            print(f"Sample pool ID from database: {full_id}")
            
            # Parse the ID
            network, address = PoolIDUtils.parse_pool_id(full_id)
            print(f"Parsed - Network: {network}, Address: {address}")
            
            # Test lookup with full ID
            pool1 = await db_manager.get_pool_by_id(full_id)
            print(f"Lookup with full ID: {'✅ Found' if pool1 else '❌ Not found'}")
            
            # Test lookup with just address (if it has a network prefix)
            if network:
                pool2 = await db_manager.get_pool_by_id(address)
                print(f"Lookup with address only: {'✅ Found' if pool2 else '❌ Not found'}")
            
            # Test with a non-existent ID
            fake_id = "solana_nonexistent123456789"
            pool3 = await db_manager.get_pool_by_id(fake_id)
            print(f"Lookup with fake ID: {'❌ Found (unexpected!)' if pool3 else '✅ Not found (expected)'}")
            
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_pool_lookup())