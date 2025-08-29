"""
SQLAlchemy implementation of the DatabaseManager interface.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.connection import DatabaseConnection
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import (
    CollectionMetadata as CollectionMetadataModel,
    DEX as DEXModel,
    OHLCVData as OHLCVDataModel,
    Pool as PoolModel,
    Token as TokenModel,
    Trade as TradeModel,
    WatchlistEntry as WatchlistEntryModel,
)
from gecko_terminal_collector.models.core import (
    Gap,
    OHLCVRecord,
    Pool,
    Token,
    TradeRecord,
)

logger = logging.getLogger(__name__)


class SQLAlchemyDatabaseManager(DatabaseManager):
    """
    SQLAlchemy implementation of the DatabaseManager interface.
    
    Provides concrete implementation for all database operations
    using SQLAlchemy ORM with connection pooling and error handling.
    """
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize SQLAlchemy database manager.
        
        Args:
            config: Database configuration settings
        """
        super().__init__(config)
        self.connection = DatabaseConnection(config)
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables if needed."""
        self.connection.initialize()
        
        # Create tables if they don't exist
        self.connection.create_tables()
        
        logger.info("SQLAlchemy database manager initialized")
    
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        self.connection.close()
        logger.info("SQLAlchemy database manager closed")
    
    # Pool operations
    async def store_pools(self, pools: List[Pool]) -> int:
        """Store pool data with upsert logic."""
        if not pools:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                for pool in pools:
                    # Check if DEX exists, create if not
                    dex = session.query(DEXModel).filter_by(id=pool.dex_id).first()
                    if not dex:
                        # Create a basic DEX entry - this should ideally be handled by DEX collector
                        dex = DEXModel(
                            id=pool.dex_id,
                            name=pool.dex_id.title(),  # Use ID as name for now
                            network="solana"  # Default to Solana
                        )
                        session.add(dex)
                    
                    # Upsert pool
                    existing_pool = session.query(PoolModel).filter_by(id=pool.id).first()
                    if existing_pool:
                        # Update existing pool
                        existing_pool.address = pool.address
                        existing_pool.name = pool.name
                        existing_pool.base_token_id = pool.base_token_id
                        existing_pool.quote_token_id = pool.quote_token_id
                        existing_pool.reserve_usd = pool.reserve_usd
                        existing_pool.last_updated = datetime.utcnow()
                    else:
                        # Create new pool
                        new_pool = PoolModel(
                            id=pool.id,
                            address=pool.address,
                            name=pool.name,
                            dex_id=pool.dex_id,
                            base_token_id=pool.base_token_id,
                            quote_token_id=pool.quote_token_id,
                            reserve_usd=pool.reserve_usd,
                            created_at=pool.created_at,
                        )
                        session.add(new_pool)
                        stored_count += 1
                
                session.commit()
                logger.info(f"Stored {stored_count} new pools, updated {len(pools) - stored_count} existing pools")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing pools: {e}")
                raise
        
        return stored_count
    
    async def get_pool(self, pool_id: str) -> Optional[Pool]:
        """Get a pool by ID."""
        with self.connection.get_session() as session:
            pool_model = session.query(PoolModel).filter_by(id=pool_id).first()
            if pool_model:
                return Pool(
                    id=pool_model.id,
                    address=pool_model.address,
                    name=pool_model.name,
                    dex_id=pool_model.dex_id,
                    base_token_id=pool_model.base_token_id,
                    quote_token_id=pool_model.quote_token_id,
                    reserve_usd=pool_model.reserve_usd,
                    created_at=pool_model.created_at,
                )
        return None
    
    async def get_pools_by_dex(self, dex_id: str) -> List[Pool]:
        """Get all pools for a specific DEX."""
        pools = []
        
        with self.connection.get_session() as session:
            pool_models = session.query(PoolModel).filter_by(dex_id=dex_id).all()
            
            for pool_model in pool_models:
                pools.append(Pool(
                    id=pool_model.id,
                    address=pool_model.address,
                    name=pool_model.name,
                    dex_id=pool_model.dex_id,
                    base_token_id=pool_model.base_token_id,
                    quote_token_id=pool_model.quote_token_id,
                    reserve_usd=pool_model.reserve_usd,
                    created_at=pool_model.created_at,
                ))
        
        return pools
    
    # Token operations
    async def store_tokens(self, tokens: List[Token]) -> int:
        """Store token data with upsert logic."""
        if not tokens:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                for token in tokens:
                    existing_token = session.query(TokenModel).filter_by(id=token.id).first()
                    if existing_token:
                        # Update existing token
                        existing_token.address = token.address
                        existing_token.name = token.name
                        existing_token.symbol = token.symbol
                        existing_token.decimals = token.decimals
                        existing_token.network = token.network
                        existing_token.last_updated = datetime.utcnow()
                    else:
                        # Create new token
                        new_token = TokenModel(
                            id=token.id,
                            address=token.address,
                            name=token.name,
                            symbol=token.symbol,
                            decimals=token.decimals,
                            network=token.network,
                        )
                        session.add(new_token)
                        stored_count += 1
                
                session.commit()
                logger.info(f"Stored {stored_count} new tokens, updated {len(tokens) - stored_count} existing tokens")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing tokens: {e}")
                raise
        
        return stored_count
    
    async def get_token(self, token_id: str) -> Optional[Token]:
        """Get a token by ID."""
        with self.connection.get_session() as session:
            token_model = session.query(TokenModel).filter_by(id=token_id).first()
            if token_model:
                return Token(
                    id=token_model.id,
                    address=token_model.address,
                    name=token_model.name,
                    symbol=token_model.symbol,
                    decimals=token_model.decimals,
                    network=token_model.network,
                    price_usd=None,  # Price not stored in token table
                )
        return None
    
    # OHLCV operations
    async def store_ohlcv_data(self, data: List[OHLCVRecord]) -> int:
        """Store OHLCV data with duplicate prevention."""
        if not data:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                for record in data:
                    # Check if record already exists
                    existing = session.query(OHLCVDataModel).filter(
                        and_(
                            OHLCVDataModel.pool_id == record.pool_id,
                            OHLCVDataModel.timeframe == record.timeframe,
                            OHLCVDataModel.timestamp == record.timestamp
                        )
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.open_price = record.open_price
                        existing.high_price = record.high_price
                        existing.low_price = record.low_price
                        existing.close_price = record.close_price
                        existing.volume_usd = record.volume_usd
                        existing.datetime = record.datetime
                    else:
                        # Create new record
                        new_record = OHLCVDataModel(
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
                        session.add(new_record)
                        stored_count += 1
                
                session.commit()
                logger.info(f"Stored/updated {stored_count} OHLCV records")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing OHLCV data: {e}")
                raise
        
        return stored_count
    
    async def get_ohlcv_data(
        self,
        pool_id: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[OHLCVRecord]:
        """Get OHLCV data for a pool and timeframe."""
        records = []
        
        with self.connection.get_session() as session:
            query = session.query(OHLCVDataModel).filter(
                and_(
                    OHLCVDataModel.pool_id == pool_id,
                    OHLCVDataModel.timeframe == timeframe
                )
            )
            
            if start_time:
                query = query.filter(OHLCVDataModel.datetime >= start_time)
            if end_time:
                query = query.filter(OHLCVDataModel.datetime <= end_time)
            
            query = query.order_by(OHLCVDataModel.datetime)
            
            for record_model in query.all():
                records.append(OHLCVRecord(
                    pool_id=record_model.pool_id,
                    timeframe=record_model.timeframe,
                    timestamp=record_model.timestamp,
                    open_price=record_model.open_price,
                    high_price=record_model.high_price,
                    low_price=record_model.low_price,
                    close_price=record_model.close_price,
                    volume_usd=record_model.volume_usd,
                    datetime=record_model.datetime,
                ))
        
        return records
    
    async def get_data_gaps(
        self,
        pool_id: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> List[Gap]:
        """Identify gaps in OHLCV data for a pool/timeframe."""
        gaps = []
        
        with self.connection.get_session() as session:
            # Get all records in the time range, ordered by datetime
            records = session.query(OHLCVDataModel).filter(
                and_(
                    OHLCVDataModel.pool_id == pool_id,
                    OHLCVDataModel.timeframe == timeframe,
                    OHLCVDataModel.datetime >= start,
                    OHLCVDataModel.datetime <= end
                )
            ).order_by(OHLCVDataModel.datetime).all()
            
            if not records:
                # No data at all - entire range is a gap
                gaps.append(Gap(
                    start_time=start,
                    end_time=end,
                    pool_id=pool_id,
                    timeframe=timeframe
                ))
                return gaps
            
            # Calculate expected interval in seconds
            interval_seconds = self._get_timeframe_seconds(timeframe)
            
            # Check for gap at the beginning
            if records[0].datetime > start:
                gaps.append(Gap(
                    start_time=start,
                    end_time=records[0].datetime,
                    pool_id=pool_id,
                    timeframe=timeframe
                ))
            
            # Check for gaps between records
            for i in range(len(records) - 1):
                current_time = records[i].datetime
                next_time = records[i + 1].datetime
                expected_next = current_time + timedelta(seconds=interval_seconds)
                
                if next_time > expected_next:
                    gaps.append(Gap(
                        start_time=expected_next,
                        end_time=next_time,
                        pool_id=pool_id,
                        timeframe=timeframe
                    ))
            
            # Check for gap at the end
            if records[-1].datetime < end:
                expected_next = records[-1].datetime + timedelta(seconds=interval_seconds)
                if expected_next <= end:
                    gaps.append(Gap(
                        start_time=expected_next,
                        end_time=end,
                        pool_id=pool_id,
                        timeframe=timeframe
                    ))
        
        return gaps
    
    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds."""
        if timeframe.endswith('m'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 86400
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    # Trade operations
    async def store_trade_data(self, data: List[TradeRecord]) -> int:
        """Store trade data with duplicate prevention."""
        if not data:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                for record in data:
                    # Check if trade already exists
                    existing_trade = session.query(TradeModel).filter_by(id=record.id).first()
                    if not existing_trade:
                        new_trade = TradeModel(
                            id=record.id,
                            pool_id=record.pool_id,
                            block_number=record.block_number,
                            tx_hash=record.tx_hash,
                            tx_from_address=getattr(record, 'tx_from_address', None),
                            from_token_amount=record.from_token_amount,
                            to_token_amount=record.to_token_amount,
                            price_usd=record.price_usd,
                            volume_usd=record.volume_usd,
                            side=record.side,
                            block_timestamp=record.block_timestamp,
                        )
                        session.add(new_trade)
                        stored_count += 1
                
                session.commit()
                logger.info(f"Stored {stored_count} new trade records")
                
            except IntegrityError as e:
                session.rollback()
                logger.warning(f"Duplicate trade records detected: {e}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing trade data: {e}")
                raise
        
        return stored_count
    
    async def get_trade_data(
        self,
        pool_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_volume_usd: Optional[float] = None
    ) -> List[TradeRecord]:
        """Get trade data for a pool with optional filtering."""
        records = []
        
        with self.connection.get_session() as session:
            query = session.query(TradeModel).filter(TradeModel.pool_id == pool_id)
            
            if start_time:
                query = query.filter(TradeModel.block_timestamp >= start_time)
            if end_time:
                query = query.filter(TradeModel.block_timestamp <= end_time)
            if min_volume_usd:
                query = query.filter(TradeModel.volume_usd >= min_volume_usd)
            
            query = query.order_by(desc(TradeModel.block_timestamp))
            
            for record_model in query.all():
                records.append(TradeRecord(
                    id=record_model.id,
                    pool_id=record_model.pool_id,
                    block_number=record_model.block_number,
                    tx_hash=record_model.tx_hash,
                    from_token_amount=record_model.from_token_amount,
                    to_token_amount=record_model.to_token_amount,
                    price_usd=record_model.price_usd,
                    volume_usd=record_model.volume_usd,
                    side=record_model.side,
                    block_timestamp=record_model.block_timestamp,
                ))
        
        return records
    
    # Watchlist operations
    async def store_watchlist_entry(self, pool_id: str, metadata: Dict[str, Any]) -> None:
        """Add or update a watchlist entry."""
        with self.connection.get_session() as session:
            try:
                existing_entry = session.query(WatchlistEntryModel).filter_by(pool_id=pool_id).first()
                if existing_entry:
                    # Update existing entry
                    existing_entry.token_symbol = metadata.get('token_symbol')
                    existing_entry.token_name = metadata.get('token_name')
                    existing_entry.network_address = metadata.get('network_address')
                    existing_entry.is_active = True
                else:
                    # Create new entry
                    new_entry = WatchlistEntryModel(
                        pool_id=pool_id,
                        token_symbol=metadata.get('token_symbol'),
                        token_name=metadata.get('token_name'),
                        network_address=metadata.get('network_address'),
                        is_active=True,
                    )
                    session.add(new_entry)
                
                session.commit()
                logger.info(f"Stored watchlist entry for pool {pool_id}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing watchlist entry: {e}")
                raise
    
    async def get_watchlist_pools(self) -> List[str]:
        """Get all active watchlist pool IDs."""
        pool_ids = []
        
        with self.connection.get_session() as session:
            entries = session.query(WatchlistEntryModel).filter_by(is_active=True).all()
            pool_ids = [entry.pool_id for entry in entries]
        
        return pool_ids
    
    async def remove_watchlist_entry(self, pool_id: str) -> None:
        """Remove a pool from the watchlist."""
        with self.connection.get_session() as session:
            try:
                entry = session.query(WatchlistEntryModel).filter_by(pool_id=pool_id).first()
                if entry:
                    entry.is_active = False
                    session.commit()
                    logger.info(f"Deactivated watchlist entry for pool {pool_id}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error removing watchlist entry: {e}")
                raise
    
    # Collection metadata operations
    async def update_collection_metadata(
        self,
        collector_type: str,
        last_run: datetime,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """Update collection run metadata."""
        with self.connection.get_session() as session:
            try:
                metadata = session.query(CollectionMetadataModel).filter_by(
                    collector_type=collector_type
                ).first()
                
                if metadata:
                    # Update existing metadata
                    metadata.last_run = last_run
                    metadata.run_count += 1
                    if success:
                        metadata.last_success = last_run
                    else:
                        metadata.error_count += 1
                        metadata.last_error = error_message
                else:
                    # Create new metadata
                    metadata = CollectionMetadataModel(
                        collector_type=collector_type,
                        last_run=last_run,
                        last_success=last_run if success else None,
                        run_count=1,
                        error_count=0 if success else 1,
                        last_error=error_message if not success else None,
                    )
                    session.add(metadata)
                
                session.commit()
                logger.debug(f"Updated collection metadata for {collector_type}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating collection metadata: {e}")
                raise
    
    async def get_collection_metadata(self, collector_type: str) -> Optional[Dict[str, Any]]:
        """Get collection metadata for a collector type."""
        with self.connection.get_session() as session:
            metadata = session.query(CollectionMetadataModel).filter_by(
                collector_type=collector_type
            ).first()
            
            if metadata:
                return {
                    'collector_type': metadata.collector_type,
                    'last_run': metadata.last_run,
                    'last_success': metadata.last_success,
                    'run_count': metadata.run_count,
                    'error_count': metadata.error_count,
                    'last_error': metadata.last_error,
                }
        
        return None