"""
Test the original issue that was failing.
"""

import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager


async def test_original_issue():
    """Test the original pool lookup that was failing."""
    
    # Initialize database
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # This was the original failing command
        pool_id = "solana_mkoTBcJtnBSndA86mexkJu8c9aPjjSSNgkXCoBAtmAm"
        print(f"Testing lookup for: {pool_id}")
        
        pool = await db_manager.get_pool_by_id(pool_id)
        
        if pool:
            print(f"✅ Pool found!")
            print(f"   ID: {pool.id}")
            print(f"   Name: {pool.name}")
            print(f"   DEX: {pool.dex_id}")
        else:
            print("❌ Pool not found")
            print("This is expected if this specific pool hasn't been collected yet.")
            
            # Let's try with just the address part
            address_only = "mkoTBcJtnBSndA86mexkJu8c9aPjjSSNgkXCoBAtmAm"
            print(f"\nTrying with address only: {address_only}")
            pool2 = await db_manager.get_pool_by_id(address_only)
            
            if pool2:
                print(f"✅ Pool found with address-only lookup!")
                print(f"   ID: {pool2.id}")
                print(f"   Name: {pool2.name}")
            else:
                print("❌ Pool not found with address-only lookup either")
                print("This pool likely hasn't been collected into your database yet.")
                
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_original_issue())