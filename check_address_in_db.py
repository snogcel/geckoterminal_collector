#!/usr/bin/env python3
"""
Check if a specific address exists in the database.
"""

import asyncio
import logging

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_address():
    """Check if address exists in database."""
    
    # The problematic address
    lowercase_addr = 'hgummd4ljnodxgksz1draaokpatmh7ntug2ncdzyat4u'
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.get_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        from sqlalchemy import func, or_
        
        with db_manager.connection.get_session() as session:
            logger.info(f"Searching for address: {lowercase_addr}")
            logger.info(f"Expected proper case: HGumMd4LJNodxGksZ1drAAoKpatmH7NTug2nCdzYAT4U")
            
            # Check pools table
            logger.info("\n=== Checking pools table ===")
            pool_count = session.query(db_manager.PoolModel).filter(
                func.lower(db_manager.PoolModel.address) == lowercase_addr.lower()
            ).count()
            logger.info(f"Pools found: {pool_count}")
            
            if pool_count > 0:
                pool = session.query(db_manager.PoolModel).filter(
                    func.lower(db_manager.PoolModel.address) == lowercase_addr.lower()
                ).first()
                logger.info(f"  Address: {pool.address}")
                logger.info(f"  Pool ID: {pool.id}")
                logger.info(f"  DEX: {pool.dex_id}")
            
            # Check new_pools_history table
            logger.info("\n=== Checking new_pools_history table ===")
            history_count = session.query(db_manager.NewPoolsHistoryModel).filter(
                func.lower(db_manager.NewPoolsHistoryModel.address) == lowercase_addr.lower()
            ).count()
            logger.info(f"History records found: {history_count}")
            
            if history_count > 0:
                history = session.query(db_manager.NewPoolsHistoryModel).filter(
                    func.lower(db_manager.NewPoolsHistoryModel.address) == lowercase_addr.lower()
                ).first()
                logger.info(f"  Address: {history.address}")
                logger.info(f"  Pool ID: {history.pool_id}")
                logger.info(f"  DEX: {history.dex_id}")
                logger.info(f"  Network: {history.network_id}")
                logger.info(f"  Base Token: {history.base_token_id}")
                logger.info(f"  Quote Token: {history.quote_token_id}")
            
            # Check tokens table
            logger.info("\n=== Checking tokens table ===")
            token_count = session.query(db_manager.TokenModel).filter(
                func.lower(db_manager.TokenModel.address) == lowercase_addr.lower()
            ).count()
            logger.info(f"Tokens found: {token_count}")
            
            if token_count > 0:
                token = session.query(db_manager.TokenModel).filter(
                    func.lower(db_manager.TokenModel.address) == lowercase_addr.lower()
                ).first()
                logger.info(f"  Address: {token.address}")
                logger.info(f"  Symbol: {token.symbol}")
                logger.info(f"  Name: {token.name}")
            
            # Try case-sensitive search to see if it's stored differently
            logger.info("\n=== Checking for similar addresses (case-sensitive) ===")
            
            # Search for addresses that start with the same prefix
            prefix = lowercase_addr[:10]
            similar_pools = session.query(db_manager.PoolModel).filter(
                func.lower(db_manager.PoolModel.address).like(f"{prefix}%")
            ).limit(5).all()
            
            if similar_pools:
                logger.info(f"Found {len(similar_pools)} pools with similar prefix:")
                for p in similar_pools:
                    logger.info(f"  {p.address} (ID: {p.id})")
            
            similar_history = session.query(db_manager.NewPoolsHistoryModel).filter(
                func.lower(db_manager.NewPoolsHistoryModel.address).like(f"{prefix}%")
            ).limit(5).all()
            
            if similar_history:
                logger.info(f"Found {len(similar_history)} history records with similar prefix:")
                for h in similar_history:
                    logger.info(f"  {h.address} (Pool ID: {h.pool_id})")
            
            # Summary
            logger.info("\n=== Summary ===")
            total_found = pool_count + history_count + token_count
            if total_found == 0:
                logger.warning("❌ Address NOT found in any table!")
                logger.warning("This address may not have been collected yet.")
            else:
                logger.info(f"✅ Address found in {total_found} record(s)")
    
    finally:
        await db_manager.close()


if __name__ == '__main__':
    asyncio.run(check_address())
