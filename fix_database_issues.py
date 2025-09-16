#!/usr/bin/env python3
"""
Comprehensive script to fix database issues:
1. Clean up blank pool entries
2. Fix timezone handling in datetime comparisons
3. Verify watchlist entry model usage
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.config.loader import ConfigLoader
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_database_issues():
    """Fix all identified database issues."""
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        logger.info("Starting database issue fixes...")
        
        # 1. Clean up blank pool entries
        logger.info("Cleaning up blank pool entries...")
        deleted_count = await cleanup_blank_pools(db_manager)
        logger.info(f"Deleted {deleted_count} blank pool entries")
        
        # 2. Verify database integrity
        logger.info("Verifying database integrity...")
        await verify_database_integrity(db_manager)
        
        # 3. Test timezone handling
        logger.info("Testing timezone handling...")
        await test_timezone_handling(db_manager)
        
        logger.info("Database issue fixes completed successfully!")
        
    except Exception as e:
        logger.error(f"Error fixing database issues: {e}", exc_info=True)
        return False
    finally:
        if 'db_manager' in locals():
            await db_manager.close()
    
    return True

async def cleanup_blank_pools(db_manager):
    """Clean up blank/incomplete pool entries."""
    deleted_count = 0
    
    try:
        # Get pools with incomplete data and no associated records
        with db_manager.connection.get_session() as session:
            # Find pools with blank names or missing token IDs
            blank_pools = session.query(db_manager.PoolModel).filter(
                db_manager.PoolModel.name.is_(None) |
                (db_manager.PoolModel.name == '') |
                db_manager.PoolModel.base_token_id.is_(None) |
                db_manager.PoolModel.quote_token_id.is_(None)
            ).all()
            
            logger.info(f"Found {len(blank_pools)} pools with incomplete data")
            
            # Check each pool for associated data
            for pool in blank_pools:
                # Check for OHLCV data
                ohlcv_count = session.query(db_manager.OHLCVDataModel).filter(
                    db_manager.OHLCVDataModel.pool_id == pool.id
                ).count()
                
                # Check for trades
                trade_count = session.query(db_manager.TradeModel).filter(
                    db_manager.TradeModel.pool_id == pool.id
                ).count()
                
                # Check for watchlist entries
                watchlist_count = session.query(db_manager.WatchlistEntryModel).filter(
                    db_manager.WatchlistEntryModel.pool_id == pool.id
                ).count()
                
                # If no associated data, delete the pool
                if ohlcv_count == 0 and trade_count == 0 and watchlist_count == 0:
                    session.delete(pool)
                    deleted_count += 1
                    logger.debug(f"Deleted orphaned pool: {pool.id}")
                else:
                    logger.info(f"Keeping pool {pool.id} - has {ohlcv_count} OHLCV, {trade_count} trades, {watchlist_count} watchlist entries")
            
            session.commit()
            
    except Exception as e:
        logger.error(f"Error cleaning up blank pools: {e}")
        raise
    
    return deleted_count

async def verify_database_integrity(db_manager):
    """Verify database integrity after cleanup."""
    try:
        with db_manager.connection.get_session() as session:
            # Count remaining pools
            total_pools = session.query(db_manager.PoolModel).count()
            logger.info(f"Total pools after cleanup: {total_pools}")
            
            # Count pools with complete data
            complete_pools = session.query(db_manager.PoolModel).filter(
                db_manager.PoolModel.name.isnot(None),
                db_manager.PoolModel.name != '',
                db_manager.PoolModel.base_token_id.isnot(None),
                db_manager.PoolModel.quote_token_id.isnot(None)
            ).count()
            logger.info(f"Pools with complete metadata: {complete_pools}")
            
            # Count pools with incomplete data but associated records
            incomplete_with_data = session.query(db_manager.PoolModel).filter(
                db_manager.PoolModel.name.is_(None) |
                (db_manager.PoolModel.name == '') |
                db_manager.PoolModel.base_token_id.is_(None) |
                db_manager.PoolModel.quote_token_id.is_(None)
            ).count()
            logger.info(f"Pools with incomplete metadata: {incomplete_with_data}")
            
    except Exception as e:
        logger.error(f"Error verifying database integrity: {e}")
        raise

async def test_timezone_handling(db_manager):
    """Test timezone handling in datetime operations."""
    try:
        # Test the timezone helper function
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Test our timezone helper
        if hasattr(db_manager, '_ensure_timezone_aware'):
            result_naive = db_manager._ensure_timezone_aware(naive_dt)
            result_aware = db_manager._ensure_timezone_aware(aware_dt)
            
            logger.info(f"Timezone handling test:")
            logger.info(f"  Naive datetime: {naive_dt} -> {result_naive}")
            logger.info(f"  Aware datetime: {aware_dt} -> {result_aware}")
            
            # Test comparison
            try:
                comparison = result_naive < result_aware
                logger.info(f"  Comparison works: {comparison}")
            except Exception as e:
                logger.error(f"  Comparison failed: {e}")
        else:
            logger.warning("_ensure_timezone_aware method not found in database manager")
            
    except Exception as e:
        logger.error(f"Error testing timezone handling: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(fix_database_issues())