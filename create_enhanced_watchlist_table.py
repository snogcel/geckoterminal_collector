#!/usr/bin/env python3
"""
Create the enhanced_watchlist_history table in the database.

This script ensures the new EnhancedWatchlistHistory table is created
in the existing database without affecting other tables.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Base, EnhancedWatchlistHistory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_enhanced_watchlist_table():
    """Create the enhanced watchlist history table."""
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        logger.info("Database manager initialized successfully")
        
        # Get the database engine
        engine = db_manager.connection.engine
        
        # Create only the enhanced_watchlist_history table
        logger.info("Creating enhanced_watchlist_history table...")
        
        # Create the table if it doesn't exist
        EnhancedWatchlistHistory.__table__.create(engine, checkfirst=True)
        
        logger.info("Enhanced watchlist history table created successfully!")
        
        # Verify the table exists
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'enhanced_watchlist_history' in tables:
            logger.info("✅ Table 'enhanced_watchlist_history' confirmed to exist")
            
            # Get column information
            columns = inspector.get_columns('enhanced_watchlist_history')
            logger.info(f"Table has {len(columns)} columns:")
            for col in columns:
                logger.info(f"  - {col['name']}: {col['type']}")
        else:
            logger.error("❌ Table 'enhanced_watchlist_history' was not created")
            
    except Exception as e:
        logger.error(f"Failed to create enhanced watchlist table: {e}", exc_info=True)
        sys.exit(1)


async def main():
    """Main function."""
    try:
        await create_enhanced_watchlist_table()
        logger.info("Enhanced watchlist table creation completed successfully!")
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())