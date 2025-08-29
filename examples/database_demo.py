#!/usr/bin/env python3
"""
Database demonstration script for GeckoTerminal collector.

This script demonstrates how to use the database layer to store and retrieve
cryptocurrency trading data.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database import SQLAlchemyDatabaseManager
from gecko_terminal_collector.models.core import Pool, Token, OHLCVRecord, TradeRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Demonstrate database operations."""
    
    # Create database configuration
    db_config = DatabaseConfig(
        url="sqlite:///demo_gecko_data.db",
        echo=True  # Show SQL queries
    )
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(db_config)
    
    try:
        # Initialize database (creates tables)
        await db_manager.initialize()
        logger.info("Database initialized successfully")
        
        # Create sample pool data
        pools = [
            Pool(
                id="solana_heaven_pool_1",
                address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
                name="SOL/USDC Pool",
                dex_id="heaven",
                base_token_id="So11111111111111111111111111111111111111112",
                quote_token_id="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                reserve_usd=Decimal("1500000.50"),
                created_at=datetime.utcnow()
            ),
            Pool(
                id="solana_pumpswap_pool_1",
                address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                name="PUMP/SOL Pool",
                dex_id="pumpswap",
                base_token_id="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump",
                quote_token_id="So11111111111111111111111111111111111111112",
                reserve_usd=Decimal("750000.25"),
                created_at=datetime.utcnow()
            )
        ]
        
        # Store pools
        stored_count = await db_manager.store_pools(pools)
        logger.info(f"Stored {stored_count} pools")
        
        # Create sample token data
        tokens = [
            Token(
                id="So11111111111111111111111111111111111111112",
                address="So11111111111111111111111111111111111111112",
                name="Wrapped SOL",
                symbol="SOL",
                decimals=9,
                network="solana"
            ),
            Token(
                id="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                name="USD Coin",
                symbol="USDC",
                decimals=6,
                network="solana"
            ),
            Token(
                id="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump",
                address="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump",
                name="Pump Token",
                symbol="PUMP",
                decimals=6,
                network="solana"
            )
        ]
        
        # Store tokens
        stored_count = await db_manager.store_tokens(tokens)
        logger.info(f"Stored {stored_count} tokens")
        
        # Create sample OHLCV data
        ohlcv_records = [
            OHLCVRecord(
                pool_id="solana_heaven_pool_1",
                timeframe="1h",
                timestamp=1640995200,  # 2022-01-01 00:00:00
                open_price=Decimal("100.50"),
                high_price=Decimal("105.75"),
                low_price=Decimal("98.25"),
                close_price=Decimal("103.00"),
                volume_usd=Decimal("50000.00"),
                datetime=datetime(2022, 1, 1, 0, 0, 0)
            ),
            OHLCVRecord(
                pool_id="solana_heaven_pool_1",
                timeframe="1h",
                timestamp=1640998800,  # 2022-01-01 01:00:00
                open_price=Decimal("103.00"),
                high_price=Decimal("108.50"),
                low_price=Decimal("101.75"),
                close_price=Decimal("106.25"),
                volume_usd=Decimal("75000.00"),
                datetime=datetime(2022, 1, 1, 1, 0, 0)
            )
        ]
        
        # Store OHLCV data
        stored_count = await db_manager.store_ohlcv_data(ohlcv_records)
        logger.info(f"Stored {stored_count} OHLCV records")
        
        # Create sample trade data
        trade_records = [
            TradeRecord(
                id="trade_1_heaven_pool",
                pool_id="solana_heaven_pool_1",
                block_number=150000000,
                tx_hash="5j7s8K9mN2pQ3rT4uV5wX6yZ7aB8cD9eF0gH1iJ2kL3mN4oP5qR6sT7uV8wX9yZ0",
                from_token_amount=Decimal("1000.000000000"),
                to_token_amount=Decimal("103000.000000"),
                price_usd=Decimal("103.00"),
                volume_usd=Decimal("103000.00"),
                side="buy",
                block_timestamp=datetime(2022, 1, 1, 0, 30, 0)
            ),
            TradeRecord(
                id="trade_2_heaven_pool",
                pool_id="solana_heaven_pool_1",
                block_number=150000001,
                tx_hash="6k8t9L0oP1qR2sT3uV4wX5yZ6aB7cD8eF9gH0iJ1kL2mN3oP4qR5sT6uV7wX8yZ9",
                from_token_amount=Decimal("500.000000000"),
                to_token_amount=Decimal("52500.000000"),
                price_usd=Decimal("105.00"),
                volume_usd=Decimal("52500.00"),
                side="buy",
                block_timestamp=datetime(2022, 1, 1, 0, 45, 0)
            )
        ]
        
        # Store trade data
        stored_count = await db_manager.store_trade_data(trade_records)
        logger.info(f"Stored {stored_count} trade records")
        
        # Add to watchlist
        await db_manager.store_watchlist_entry(
            "solana_heaven_pool_1",
            {
                'token_symbol': 'SOL',
                'token_name': 'Wrapped SOL',
                'network_address': 'So11111111111111111111111111111111111111112'
            }
        )
        logger.info("Added pool to watchlist")
        
        # Update collection metadata
        await db_manager.update_collection_metadata(
            "demo_collector",
            datetime.utcnow(),
            success=True
        )
        logger.info("Updated collection metadata")
        
        # Demonstrate data retrieval
        logger.info("\n--- Data Retrieval Demo ---")
        
        # Get pool
        pool = await db_manager.get_pool("solana_heaven_pool_1")
        if pool:
            logger.info(f"Retrieved pool: {pool.name} (DEX: {pool.dex_id})")
        
        # Get token
        token = await db_manager.get_token("So11111111111111111111111111111111111111112")
        if token:
            logger.info(f"Retrieved token: {token.name} ({token.symbol})")
        
        # Get OHLCV data
        ohlcv_data = await db_manager.get_ohlcv_data(
            "solana_heaven_pool_1", 
            "1h"
        )
        logger.info(f"Retrieved {len(ohlcv_data)} OHLCV records")
        for record in ohlcv_data:
            logger.info(f"  {record.datetime}: O={record.open_price} H={record.high_price} L={record.low_price} C={record.close_price} V=${record.volume_usd}")
        
        # Get trade data
        trade_data = await db_manager.get_trade_data(
            "solana_heaven_pool_1",
            min_volume_usd=50000.0
        )
        logger.info(f"Retrieved {len(trade_data)} trade records (min volume $50k)")
        for trade in trade_data:
            logger.info(f"  {trade.block_timestamp}: {trade.side} ${trade.volume_usd} @ ${trade.price_usd}")
        
        # Get watchlist
        watchlist_pools = await db_manager.get_watchlist_pools()
        logger.info(f"Watchlist contains {len(watchlist_pools)} pools: {watchlist_pools}")
        
        # Get collection metadata
        metadata = await db_manager.get_collection_metadata("demo_collector")
        if metadata:
            logger.info(f"Collection metadata: {metadata['run_count']} runs, last success: {metadata['last_success']}")
        
        logger.info("\nDatabase demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Database demo failed: {e}")
        raise
    finally:
        # Clean up
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())