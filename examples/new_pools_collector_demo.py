"""
Demo script for the NewPoolsCollector.

This script demonstrates how to use the NewPoolsCollector to fetch and store
new pools data from the GeckoTerminal API.
"""

import asyncio
import logging
from datetime import datetime

from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig, DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main demo function."""
    
    # Configuration
    config = CollectionConfig(
        api=APIConfig(
            base_url="https://api.geckoterminal.com/api/v2",
            timeout=30,
            rate_limit_delay=1.0
        ),
        error_handling=ErrorConfig(
            max_retries=3,
            backoff_factor=2.0,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=300
        )
    )
    
    # Database configuration (using SQLite for demo)
    db_config = DatabaseConfig(
        url="sqlite:///new_pools_demo.db",
        pool_size=5,
        max_overflow=10,
        echo=False
    )
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(db_config)
    await db_manager.initialize()
    
    try:
        # Create new pools collector for Solana network
        collector = NewPoolsCollector(
            config=config,
            db_manager=db_manager,
            network="solana",
            use_mock=True  # Set to False to use real API
        )
        
        logger.info("Starting new pools collection for Solana network...")
        
        # Execute collection
        result = await collector.collect()
        
        # Display results
        if result.success:
            logger.info(f"✅ Collection successful!")
            logger.info(f"   Records collected: {result.records_collected}")
            logger.info(f"   Pools created: {result.metadata.get('pools_created', 0)}")
            logger.info(f"   History records: {result.metadata.get('history_records', 0)}")
            logger.info(f"   API pools received: {result.metadata.get('api_pools_received', 0)}")
            
            if result.errors:
                logger.warning(f"   Errors encountered: {len(result.errors)}")
                for error in result.errors:
                    logger.warning(f"     - {error}")
        else:
            logger.error(f"❌ Collection failed!")
            for error in result.errors:
                logger.error(f"   - {error}")
        
        # Display database statistics
        logger.info("\n📊 Database Statistics:")
        pool_count = await db_manager.count_records("pools")
        history_count = await db_manager.count_records("new_pools_history")
        logger.info(f"   Total pools: {pool_count}")
        logger.info(f"   Total history records: {history_count}")
        
        # Show some sample data
        if pool_count > 0:
            logger.info("\n🔍 Sample Pool Data:")
            # Get a sample pool
            with db_manager.connection.get_session() as session:
                from gecko_terminal_collector.database.models import Pool as PoolModel
                sample_pool = session.query(PoolModel).first()
                if sample_pool:
                    logger.info(f"   Pool ID: {sample_pool.id}")
                    logger.info(f"   Name: {sample_pool.name}")
                    logger.info(f"   Address: {sample_pool.address}")
                    logger.info(f"   DEX: {sample_pool.dex_id}")
                    logger.info(f"   Reserve USD: ${sample_pool.reserve_usd}")
        
        if history_count > 0:
            logger.info("\n📈 Sample History Data:")
            # Get a sample history record
            with db_manager.connection.get_session() as session:
                from gecko_terminal_collector.database.models import NewPoolsHistory
                sample_history = session.query(NewPoolsHistory).first()
                if sample_history:
                    logger.info(f"   Pool ID: {sample_history.pool_id}")
                    logger.info(f"   Name: {sample_history.name}")
                    logger.info(f"   Base Token Price USD: ${sample_history.base_token_price_usd}")
                    logger.info(f"   FDV USD: ${sample_history.fdv_usd}")
                    logger.info(f"   24h Volume USD: ${sample_history.volume_usd_h24}")
                    logger.info(f"   Collected At: {sample_history.collected_at}")
        
        # Demonstrate multiple collections
        logger.info("\n🔄 Running second collection to demonstrate duplicate handling...")
        result2 = await collector.collect()
        
        if result2.success:
            logger.info(f"✅ Second collection successful!")
            logger.info(f"   Records collected: {result2.records_collected}")
            logger.info(f"   New pools created: {result2.metadata.get('pools_created', 0)}")
            logger.info(f"   New history records: {result2.metadata.get('history_records', 0)}")
        
        # Final database statistics
        logger.info("\n📊 Final Database Statistics:")
        final_pool_count = await db_manager.count_records("pools")
        final_history_count = await db_manager.count_records("new_pools_history")
        logger.info(f"   Total pools: {final_pool_count}")
        logger.info(f"   Total history records: {final_history_count}")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        raise
    
    finally:
        # Cleanup
        await db_manager.close()
        logger.info("Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())