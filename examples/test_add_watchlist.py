from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import WatchlistEntry

def db_manager(temp_db_config):
    """Create and initialize database manager."""
    manager = SQLAlchemyDatabaseManager(temp_db_config)
    # Initialize synchronously for testing
    manager.connection.initialize()
    manager.connection.create_tables()
    
    # Create required DEXes for testing
    from gecko_terminal_collector.database.models import DEX
    with manager.connection.get_session() as session:
        entry = WatchlistEntry(
            pool_id="solana_mkoTBcJtnBSndA86mexkJu8c9aPjjSSNgkXCoBAtmAm",
            token_symbol="YUGE",
            token_name="Yuge Token",
            network_address="mkoTBcJtnBSndA86mexkJu8c9aPjjSSNgkXCoBAtmAm",
            is_active=True
        )
        await db_manager.store_watchlist_entry(entry)
        session.commit()
    
    yield manager
    manager.connection.close()



# tinkering!

# align temp_db_config
temp_db_config




