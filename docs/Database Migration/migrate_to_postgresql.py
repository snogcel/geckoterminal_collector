#!/usr/bin/env python3
"""
Migration script to move from SQLite to PostgreSQL with data preservation.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.postgresql_manager import PostgreSQLDatabaseManager
from gecko_terminal_collector.database.models import (
    Pool as PoolModel, Token as TokenModel, Trade as TradeModel,
    OHLCVData as OHLCVDataModel, DEX as DEXModel, WatchlistEntry as WatchlistEntryModel
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handle migration from SQLite to PostgreSQL."""
    
    def __init__(self, sqlite_path: str, postgresql_url: str):
        """Initialize the migrator."""
        self.sqlite_path = sqlite_path
        self.postgresql_url = postgresql_url
        
        # Initialize database managers
        self.sqlite_config = DatabaseConfig(
            url=f"sqlite:///{sqlite_path}",
            echo=False
        )
        
        self.postgresql_config = DatabaseConfig(
            url=postgresql_url,
            async_url=postgresql_url.replace("postgresql://", "postgresql+asyncpg://"),
            echo=False
        )
        
        self.sqlite_manager = None
        self.postgresql_manager = None
        
        # Migration statistics
        self.migration_stats = {
            'start_time': None,
            'end_time': None,
            'tables_migrated': 0,
            'total_records': 0,
            'errors': []
        }
    
    async def initialize_managers(self):
        """Initialize both database managers."""
        logger.info("Initializing database managers...")
        
        # Initialize SQLite manager
        self.sqlite_manager = SQLAlchemyDatabaseManager(self.sqlite_config)
        await self.sqlite_manager.initialize()
        
        # Initialize PostgreSQL manager
        self.postgresql_manager = PostgreSQLDatabaseManager(self.postgresql_config)
        await self.postgresql_manager.initialize()
        
        logger.info("Database managers initialized")
    
    async def close_managers(self):
        """Close database managers."""
        if self.sqlite_manager:
            await self.sqlite_manager.close()
        
        if self.postgresql_manager:
            await self.postgresql_manager.close()
    
    async def verify_postgresql_setup(self) -> bool:
        """Verify PostgreSQL is properly set up."""
        try:
            health_metrics = await self.postgresql_manager.get_database_health_metrics()
            
            if health_metrics.get('connection_status') == 'healthy':
                logger.info("✓ PostgreSQL connection verified")
                logger.info(f"  Database size: {health_metrics.get('database_size', 'unknown')}")
                logger.info(f"  Active connections: {health_metrics.get('active_connections', 0)}")
                return True
            else:
                logger.error("✗ PostgreSQL connection failed")
                return False
                
        except Exception as e:
            logger.error(f"PostgreSQL verification failed: {e}")
            return False
    
    async def analyze_sqlite_data(self) -> Dict[str, int]:
        """Analyze SQLite database to understand data volume."""
        logger.info("Analyzing SQLite database...")
        
        tables = ['pools', 'tokens', 'trades', 'ohlcv_data', 'dexes', 'watchlist']
        table_counts = {}
        
        for table in tables:
            try:
                count = await self.sqlite_manager.count_records(table)
                table_counts[table] = count
                logger.info(f"  {table}: {count:,} records")
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")
                table_counts[table] = 0
        
        total_records = sum(table_counts.values())
        logger.info(f"Total records to migrate: {total_records:,}")
        
        return table_counts
    
    async def migrate_table_data(self, table_name: str, batch_size: int = 1000) -> int:
        """Migrate data from a specific table."""
        logger.info(f"Migrating {table_name} data...")
        
        migrated_count = 0
        
        try:
            if table_name == 'dexes':
                migrated_count = await self._migrate_dexes(batch_size)
            elif table_name == 'tokens':
                migrated_count = await self._migrate_tokens(batch_size)
            elif table_name == 'pools':
                migrated_count = await self._migrate_pools(batch_size)
            elif table_name == 'trades':
                migrated_count = await self._migrate_trades(batch_size)
            elif table_name == 'ohlcv_data':
                migrated_count = await self._migrate_ohlcv_data(batch_size)
            elif table_name == 'watchlist':
                migrated_count = await self._migrate_watchlist(batch_size)
            else:
                logger.warning(f"Unknown table: {table_name}")
                return 0
            
            logger.info(f"✓ Migrated {migrated_count:,} records from {table_name}")
            return migrated_count
            
        except Exception as e:
            error_msg = f"Error migrating {table_name}: {e}"
            logger.error(error_msg)
            self.migration_stats['errors'].append(error_msg)
            return 0
    
    async def _migrate_dexes(self, batch_size: int) -> int:
        """Migrate DEX data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            dexes = session.query(DEXModel).all()
            
            if dexes:
                # Convert to list of dicts for PostgreSQL
                dex_data = []
                for dex in dexes:
                    dex_data.append({
                        'id': dex.id,
                        'name': dex.name,
                        'network': dex.network,
                        'created_at': dex.created_at or datetime.utcnow(),
                        'last_updated': dex.last_updated or datetime.utcnow(),
                    })
                
                # Batch insert into PostgreSQL
                async with self.postgresql_manager.get_async_session() as pg_session:
                    from sqlalchemy.dialects.postgresql import insert
                    
                    stmt = insert(DEXModel).values(dex_data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            'name': stmt.excluded.name,
                            'network': stmt.excluded.network,
                            'last_updated': stmt.excluded.last_updated,
                        }
                    )
                    
                    await pg_session.execute(stmt)
                    await pg_session.commit()
                    
                    migrated_count = len(dex_data)
        
        return migrated_count
    
    async def _migrate_tokens(self, batch_size: int) -> int:
        """Migrate token data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            total_tokens = session.query(TokenModel).count()
            
            for offset in range(0, total_tokens, batch_size):
                tokens = session.query(TokenModel).offset(offset).limit(batch_size).all()
                
                if tokens:
                    token_data = []
                    for token in tokens:
                        token_data.append({
                            'id': token.id,
                            'address': token.address,
                            'name': token.name,
                            'symbol': token.symbol,
                            'decimals': token.decimals,
                            'network': token.network,
                            'created_at': token.created_at or datetime.utcnow(),
                            'last_updated': token.last_updated or datetime.utcnow(),
                        })
                    
                    # Batch insert into PostgreSQL
                    async with self.postgresql_manager.get_async_session() as pg_session:
                        from sqlalchemy.dialects.postgresql import insert
                        
                        stmt = insert(TokenModel).values(token_data)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['id'],
                            set_={
                                'name': stmt.excluded.name,
                                'symbol': stmt.excluded.symbol,
                                'decimals': stmt.excluded.decimals,
                                'last_updated': stmt.excluded.last_updated,
                            }
                        )
                        
                        await pg_session.execute(stmt)
                        await pg_session.commit()
                        
                        migrated_count += len(token_data)
                        
                        if migrated_count % 10000 == 0:
                            logger.info(f"  Migrated {migrated_count:,} tokens...")
        
        return migrated_count
    
    async def _migrate_pools(self, batch_size: int) -> int:
        """Migrate pool data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            total_pools = session.query(PoolModel).count()
            
            for offset in range(0, total_pools, batch_size):
                pools = session.query(PoolModel).offset(offset).limit(batch_size).all()
                
                if pools:
                    pool_data = []
                    for pool in pools:
                        pool_data.append({
                            'id': pool.id,
                            'address': pool.address,
                            'name': pool.name,
                            'dex_id': pool.dex_id,
                            'base_token_id': pool.base_token_id,
                            'quote_token_id': pool.quote_token_id,
                            'reserve_usd': pool.reserve_usd,
                            'created_at': pool.created_at or datetime.utcnow(),
                            'last_updated': pool.last_updated or datetime.utcnow(),
                            'activity_score': pool.activity_score,
                            'discovery_source': pool.discovery_source,
                            'collection_priority': pool.collection_priority,
                            'auto_discovered_at': pool.auto_discovered_at,
                            'last_activity_check': pool.last_activity_check,
                        })
                    
                    # Batch insert into PostgreSQL
                    async with self.postgresql_manager.get_async_session() as pg_session:
                        from sqlalchemy.dialects.postgresql import insert
                        
                        stmt = insert(PoolModel).values(pool_data)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['id'],
                            set_={
                                'address': stmt.excluded.address,
                                'name': stmt.excluded.name,
                                'reserve_usd': stmt.excluded.reserve_usd,
                                'last_updated': stmt.excluded.last_updated,
                                'activity_score': stmt.excluded.activity_score,
                                'collection_priority': stmt.excluded.collection_priority,
                                'last_activity_check': stmt.excluded.last_activity_check,
                            }
                        )
                        
                        await pg_session.execute(stmt)
                        await pg_session.commit()
                        
                        migrated_count += len(pool_data)
                        
                        if migrated_count % 1000 == 0:
                            logger.info(f"  Migrated {migrated_count:,} pools...")
        
        return migrated_count
    
    async def _migrate_trades(self, batch_size: int) -> int:
        """Migrate trade data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            total_trades = session.query(TradeModel).count()
            
            logger.info(f"Migrating {total_trades:,} trades in batches of {batch_size:,}...")
            
            for offset in range(0, total_trades, batch_size):
                trades = session.query(TradeModel).offset(offset).limit(batch_size).all()
                
                if trades:
                    trade_data = []
                    for trade in trades:
                        trade_data.append({
                            'id': trade.id,
                            'pool_id': trade.pool_id,
                            'block_number': trade.block_number,
                            'tx_hash': trade.tx_hash,
                            'tx_from_address': trade.tx_from_address,
                            'from_token_amount': trade.from_token_amount,
                            'to_token_amount': trade.to_token_amount,
                            'price_usd': trade.price_usd,
                            'volume_usd': trade.volume_usd,
                            'side': trade.side,
                            'block_timestamp': trade.block_timestamp,
                        })
                    
                    # Use PostgreSQL optimized storage
                    from gecko_terminal_collector.models.core import TradeRecord
                    
                    trade_records = []
                    for data in trade_data:
                        record = TradeRecord(
                            id=data['id'],
                            pool_id=data['pool_id'].split('_', 1)[1] if '_' in data['pool_id'] else data['pool_id'],
                            block_number=data['block_number'],
                            tx_hash=data['tx_hash'],
                            tx_from_address=data['tx_from_address'],
                            from_token_amount=data['from_token_amount'],
                            to_token_amount=data['to_token_amount'],
                            price_usd=data['price_usd'],
                            volume_usd=data['volume_usd'],
                            side=data['side'],
                            block_timestamp=data['block_timestamp'],
                        )
                        trade_records.append(record)
                    
                    stored_count = await self.postgresql_manager.store_trade_data_optimized(trade_records)
                    migrated_count += stored_count
                    
                    if migrated_count % 50000 == 0:
                        logger.info(f"  Migrated {migrated_count:,} trades...")
        
        return migrated_count
    
    async def _migrate_ohlcv_data(self, batch_size: int) -> int:
        """Migrate OHLCV data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            total_ohlcv = session.query(OHLCVDataModel).count()
            
            logger.info(f"Migrating {total_ohlcv:,} OHLCV records in batches of {batch_size:,}...")
            
            for offset in range(0, total_ohlcv, batch_size):
                ohlcv_records = session.query(OHLCVDataModel).offset(offset).limit(batch_size).all()
                
                if ohlcv_records:
                    from gecko_terminal_collector.models.core import OHLCVRecord
                    
                    ohlcv_data = []
                    for record in ohlcv_records:
                        ohlcv_record = OHLCVRecord(
                            pool_id=record.pool_id,
                            timeframe=record.timeframe,
                            timestamp=record.timestamp,
                            open_price=record.open_price,
                            high_price=record.high_price,
                            low_price=record.low_price,
                            close_price=record.close_price,
                            volume_usd=record.volume_usd,
                            datetime=record.datetime,
                        )
                        ohlcv_data.append(ohlcv_record)
                    
                    stored_count = await self.postgresql_manager.store_ohlcv_data_optimized(ohlcv_data)
                    migrated_count += stored_count
                    
                    if migrated_count % 10000 == 0:
                        logger.info(f"  Migrated {migrated_count:,} OHLCV records...")
        
        return migrated_count
    
    async def _migrate_watchlist(self, batch_size: int) -> int:
        """Migrate watchlist data."""
        migrated_count = 0
        
        with self.sqlite_manager.connection.get_session() as session:
            watchlist_entries = session.query(WatchlistEntryModel).all()
            
            if watchlist_entries:
                watchlist_data = []
                for entry in watchlist_entries:
                    watchlist_data.append({
                        'pool_id': entry.pool_id,
                        'token_symbol': entry.token_symbol,
                        'token_name': entry.token_name,
                        'network_address': entry.network_address,
                        'is_active': entry.is_active,
                        'created_at': entry.created_at or datetime.utcnow(),
                        'updated_at': entry.updated_at or datetime.utcnow(),
                    })
                
                # Batch insert into PostgreSQL
                async with self.postgresql_manager.get_async_session() as pg_session:
                    from sqlalchemy.dialects.postgresql import insert
                    
                    stmt = insert(WatchlistEntryModel).values(watchlist_data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['pool_id'],
                        set_={
                            'token_symbol': stmt.excluded.token_symbol,
                            'token_name': stmt.excluded.token_name,
                            'is_active': stmt.excluded.is_active,
                            'updated_at': stmt.excluded.updated_at,
                        }
                    )
                    
                    await pg_session.execute(stmt)
                    await pg_session.commit()
                    
                    migrated_count = len(watchlist_data)
        
        return migrated_count
    
    async def verify_migration(self) -> Dict[str, Any]:
        """Verify migration by comparing record counts."""
        logger.info("Verifying migration...")
        
        verification_results = {
            'success': True,
            'table_comparisons': {},
            'total_sqlite_records': 0,
            'total_postgresql_records': 0,
        }
        
        tables = ['pools', 'tokens', 'trades', 'ohlcv_data', 'dexes', 'watchlist']
        
        for table in tables:
            try:
                sqlite_count = await self.sqlite_manager.count_records(table)
                postgresql_count = await self.postgresql_manager.count_records(table)
                
                verification_results['table_comparisons'][table] = {
                    'sqlite': sqlite_count,
                    'postgresql': postgresql_count,
                    'match': sqlite_count == postgresql_count
                }
                
                verification_results['total_sqlite_records'] += sqlite_count
                verification_results['total_postgresql_records'] += postgresql_count
                
                if sqlite_count != postgresql_count:
                    verification_results['success'] = False
                    logger.warning(f"❌ {table}: SQLite={sqlite_count:,}, PostgreSQL={postgresql_count:,}")
                else:
                    logger.info(f"✓ {table}: {sqlite_count:,} records match")
                    
            except Exception as e:
                logger.error(f"Error verifying {table}: {e}")
                verification_results['success'] = False
        
        return verification_results
    
    async def run_migration(self) -> bool:
        """Run the complete migration process."""
        self.migration_stats['start_time'] = datetime.now()
        
        try:
            logger.info("=== Starting PostgreSQL Migration ===")
            
            # Initialize managers
            await self.initialize_managers()
            
            # Verify PostgreSQL setup
            if not await self.verify_postgresql_setup():
                return False
            
            # Analyze SQLite data
            table_counts = await self.analyze_sqlite_data()
            
            # Migration order (respecting foreign key dependencies)
            migration_order = ['dexes', 'tokens', 'pools', 'watchlist', 'trades', 'ohlcv_data']
            
            total_migrated = 0
            
            for table in migration_order:
                if table_counts.get(table, 0) > 0:
                    migrated = await self.migrate_table_data(table)
                    total_migrated += migrated
                    self.migration_stats['tables_migrated'] += 1
                else:
                    logger.info(f"Skipping {table} (no data)")
            
            self.migration_stats['total_records'] = total_migrated
            
            # Verify migration
            verification = await self.verify_migration()
            
            if verification['success']:
                logger.info("✓ Migration completed successfully!")
                logger.info(f"  Total records migrated: {total_migrated:,}")
                logger.info(f"  Tables migrated: {self.migration_stats['tables_migrated']}")
                return True
            else:
                logger.error("❌ Migration verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.migration_stats['errors'].append(str(e))
            return False
        
        finally:
            self.migration_stats['end_time'] = datetime.now()
            await self.close_managers()
    
    def print_migration_summary(self):
        """Print migration summary."""
        logger.info("\n=== Migration Summary ===")
        
        if self.migration_stats['start_time'] and self.migration_stats['end_time']:
            duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
            logger.info(f"Duration: {duration}")
        
        logger.info(f"Tables migrated: {self.migration_stats['tables_migrated']}")
        logger.info(f"Total records: {self.migration_stats['total_records']:,}")
        
        if self.migration_stats['errors']:
            logger.info(f"Errors encountered: {len(self.migration_stats['errors'])}")
            for error in self.migration_stats['errors']:
                logger.error(f"  - {error}")


async def main():
    """Main migration function."""
    if len(sys.argv) < 3:
        print("Usage: python migrate_to_postgresql.py <sqlite_path> <postgresql_url>")
        print("Example: python migrate_to_postgresql.py gecko_data.db postgresql://user:pass@localhost/gecko_db")
        sys.exit(1)
    
    sqlite_path = sys.argv[1]
    postgresql_url = sys.argv[2]
    
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    logger.info(f"Migrating from SQLite: {sqlite_path}")
    logger.info(f"Migrating to PostgreSQL: {postgresql_url}")
    
    # Confirm migration
    try:
        confirm = input("Are you sure you want to proceed with migration? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Migration cancelled")
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        logger.info("Migration cancelled")
        sys.exit(0)
    
    # Run migration
    migrator = DatabaseMigrator(sqlite_path, postgresql_url)
    
    success = await migrator.run_migration()
    migrator.print_migration_summary()
    
    if success:
        logger.info("\n🎉 Migration completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Update your configuration to use PostgreSQL")
        logger.info("2. Test your collectors with the new database")
        logger.info("3. Monitor performance improvements")
        sys.exit(0)
    else:
        logger.error("\n❌ Migration failed!")
        logger.error("Please check the errors above and try again")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())