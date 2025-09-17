"""
Database migration to add signal analysis fields to new_pools_history table.
"""

import logging
from sqlalchemy import text
from gecko_terminal_collector.config.loader import ConfigLoader
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

logger = logging.getLogger(__name__)


async def migrate_add_signal_fields():
    """Add signal analysis fields to new_pools_history table."""
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.load_config('config.yaml')
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    print("Adding signal analysis fields to new_pools_history table...")
    
    # SQL commands to add new columns
    migration_sql = [
        # Add signal analysis columns
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS signal_score NUMERIC(10, 4);",
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS volume_trend VARCHAR(20);",
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS liquidity_trend VARCHAR(20);",
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS momentum_indicator NUMERIC(10, 4);",
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS activity_score NUMERIC(10, 4);",
        "ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS volatility_score NUMERIC(10, 4);",
        
        # Add indexes for signal analysis
        "CREATE INDEX IF NOT EXISTS idx_new_pools_history_signal_score ON new_pools_history USING btree (signal_score DESC NULLS LAST);",
        "CREATE INDEX IF NOT EXISTS idx_new_pools_history_volume_trend ON new_pools_history (volume_trend);",
        "CREATE INDEX IF NOT EXISTS idx_new_pools_history_activity_score ON new_pools_history USING btree (activity_score DESC NULLS LAST);",
        "CREATE INDEX IF NOT EXISTS idx_new_pools_history_pool_signal_time ON new_pools_history (pool_id, signal_score, collected_at);",
    ]
    
    try:
        with db_manager.connection.get_session() as session:
            for sql_command in migration_sql:
                print(f"Executing: {sql_command}")
                session.execute(text(sql_command))
            
            session.commit()
            print("✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate_add_signal_fields())