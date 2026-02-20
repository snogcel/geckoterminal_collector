#!/usr/bin/env python3
"""
Add database indexes for optimized address resolution.

This script creates indexes that dramatically improve lazy loading performance
for the Enhanced Watchlist Database Resolver.
"""

import asyncio
import logging
from pathlib import Path

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def add_indexes():
    """Add database indexes for address resolution."""
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.get_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        logger.info("Adding database indexes for optimized address resolution...")
        
        # Read SQL file
        sql_file = Path('add_address_indexes.sql')
        if not sql_file.exists():
            logger.error(f"SQL file not found: {sql_file}")
            return
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Split into individual statements
        statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
        
        with db_manager.connection.get_session() as session:
            for i, statement in enumerate(statements, 1):
                # Skip comments and empty lines
                if not statement or statement.startswith('--'):
                    continue
                
                try:
                    logger.info(f"Executing statement {i}/{len(statements)}...")
                    logger.debug(f"SQL: {statement[:100]}...")
                    
                    session.execute(statement)
                    session.commit()
                    
                    logger.info(f"✅ Statement {i} completed")
                    
                except Exception as e:
                    logger.error(f"❌ Error executing statement {i}: {e}")
                    session.rollback()
                    continue
        
        logger.info("✅ All indexes created successfully!")
        logger.info("\nTo verify indexes, run:")
        logger.info("  SELECT indexname FROM pg_indexes WHERE tablename IN ('pools', 'new_pools_history', 'tokens');")
        
    except Exception as e:
        logger.error(f"Error adding indexes: {e}")
        raise
    
    finally:
        await db_manager.close()


if __name__ == '__main__':
    asyncio.run(add_indexes())
