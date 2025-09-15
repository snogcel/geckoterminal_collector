import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

async def check_pools():
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Get some pool IDs to see the format
    with db_manager.connection.get_session() as session:
        from gecko_terminal_collector.database.models import Pool
        pools = session.query(Pool).limit(5).all()
        print('Sample pool IDs:')
        for pool in pools:
            print(f'  {pool.id}')
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(check_pools())