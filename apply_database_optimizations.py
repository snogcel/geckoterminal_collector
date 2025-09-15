#!/usr/bin/env python3
"""
Script to apply database optimizations to existing gecko terminal collector setup.
"""

import asyncio
import logging
import os
from pathlib import Path

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def apply_optimizations_to_database(db_path: str):
    """Apply optimizations to an existing database."""
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Backup the database first
    backup_path = f"{db_path}.backup_{int(asyncio.get_event_loop().time())}"
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False
    
    # Initialize database manager with optimizations
    config = DatabaseConfig(
        url=f"sqlite:///{db_path}",
        echo=False
    )
    
    db_manager = SQLAlchemyDatabaseManager(config)
    
    try:
        await db_manager.initialize()
        
        # Check current status
        logger.info("Checking current database configuration...")
        health_metrics = await db_manager.get_database_health_metrics()
        
        logger.info("Current Database Status:")
        for key, value in health_metrics.items():
            logger.info(f"  {key}: {value}")
        
        # Apply optimizations if needed
        if not health_metrics.get('wal_mode_enabled', False):
            logger.info("Applying SQLite optimizations...")
            db_manager._apply_sqlite_optimizations()
            
            # Check again after optimization
            updated_metrics = await db_manager.get_database_health_metrics()
            logger.info("Updated Database Status:")
            for key, value in updated_metrics.items():
                logger.info(f"  {key}: {value}")
            
            if updated_metrics.get('optimization_status') == 'optimized':
                logger.info("✓ Database optimizations applied successfully")
                return True
            else:
                logger.warning("✗ Optimizations may not have been fully applied")
                return False
        else:
            logger.info("✓ Database is already optimized")
            return True
            
    except Exception as e:
        logger.error(f"Error applying optimizations: {e}")
        return False
    finally:
        await db_manager.close()


async def find_and_optimize_databases():
    """Find and optimize all gecko terminal databases."""
    
    # Common database locations
    potential_paths = [
        "gecko_data.db",
        "data/gecko_data.db",
        "database/gecko_data.db",
        "gecko_terminal_collector.db",
    ]
    
    # Look for databases in current directory and subdirectories
    current_dir = Path(".")
    db_files = list(current_dir.glob("**/*.db"))
    
    # Add found databases to potential paths
    for db_file in db_files:
        potential_paths.append(str(db_file))
    
    # Remove duplicates
    potential_paths = list(set(potential_paths))
    
    optimized_count = 0
    
    for db_path in potential_paths:
        if os.path.exists(db_path):
            logger.info(f"\nProcessing database: {db_path}")
            
            if await apply_optimizations_to_database(db_path):
                optimized_count += 1
            else:
                logger.warning(f"Failed to optimize: {db_path}")
    
    logger.info(f"\nOptimization complete: {optimized_count} databases optimized")
    
    if optimized_count == 0:
        logger.info("No databases found or all databases were already optimized")
        logger.info("If you have a database in a different location, run:")
        logger.info("  python apply_database_optimizations.py /path/to/your/database.db")


async def main():
    """Main function to apply database optimizations."""
    import sys
    
    logger.info("=== Gecko Terminal Database Optimization ===")
    
    if len(sys.argv) > 1:
        # Specific database path provided
        db_path = sys.argv[1]
        logger.info(f"Optimizing specific database: {db_path}")
        
        success = await apply_optimizations_to_database(db_path)
        if success:
            logger.info("✓ Optimization completed successfully")
        else:
            logger.error("✗ Optimization failed")
            sys.exit(1)
    else:
        # Auto-discover and optimize databases
        logger.info("Auto-discovering databases to optimize...")
        await find_and_optimize_databases()
    
    logger.info("\n=== Optimization Complete ===")
    logger.info("\nNext steps:")
    logger.info("1. Test your collectors with: python test_lock_optimization.py")
    logger.info("2. Monitor performance improvements in your logs")
    logger.info("3. Consider migrating to PostgreSQL for production use")


if __name__ == "__main__":
    asyncio.run(main())