import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Pool as PoolModel
from sqlalchemy.orm import sessionmaker

async def test_pool_details():
    # Load config
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    
    # Initialize database
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    expected_pool_id = '7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP'
    print(f"Looking for pool ID: {expected_pool_id}")
    print(f"Pool ID length: {len(expected_pool_id)}")
    
    # Access the session directly
    with db_manager.connection.get_session() as session:
        # Get all pools
        all_pools = session.query(PoolModel).all()
        print(f"\nTotal pools in database: {len(all_pools)}")
        
        for i, pool in enumerate(all_pools):
            print(f"\nPool {i+1}:")
            print(f"  ID: '{pool.id}' (length: {len(pool.id)})")
            print(f"  Address: '{pool.address}'")
            print(f"  Name: '{pool.name}'")
            print(f"  DEX ID: '{pool.dex_id}'")
            
            # Check if this matches our expected ID
            if pool.id == expected_pool_id:
                print(f"  ✓ MATCHES expected pool ID")
            else:
                print(f"  ✗ Does NOT match expected pool ID")
                # Show character-by-character comparison
                print(f"  Expected: {repr(expected_pool_id)}")
                print(f"  Actual:   {repr(pool.id)}")
    
    # Test the get_pool method
    print(f"\nTesting get_pool method:")
    pool = await db_manager.get_pool(expected_pool_id)
    if pool:
        print(f"✓ get_pool found: {pool.id}")
    else:
        print(f"✗ get_pool returned None")
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(test_pool_details())