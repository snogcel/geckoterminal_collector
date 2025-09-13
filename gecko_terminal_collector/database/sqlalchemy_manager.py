"""
SQLAlchemy implementation of the DatabaseManager interface.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.connection import DatabaseConnection
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import (
    CollectionMetadata as CollectionMetadataModel,
    DEX as DEXModel,
    DiscoveryMetadata as DiscoveryMetadataModel,
    NewPoolsHistory as NewPoolsHistoryModel,
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
    
    async def get_pools_needing_activity_update(self, cutoff_time: datetime) -> List[PoolModel]:
        """
        Get pools that need activity score updates.
        
        Returns pools that:
        - Are auto-discovered (discovery_source = 'auto' or 'auto_new')
        - Haven't been checked since cutoff_time
        - Are not paused
        
        Args:
            cutoff_time: Only return pools not checked since this time
            
        Returns:
            List of PoolModel objects needing updates
        """
        pools = []
        
        with self.connection.get_session() as session:
            try:
                # Query for pools needing activity updates
                query = session.query(PoolModel).filter(
                    and_(
                        # Only auto-discovered pools
                        or_(
                            PoolModel.discovery_source == 'auto',
                            PoolModel.discovery_source == 'auto_new'
                        ),
                        # Not paused
                        PoolModel.collection_priority != 'paused',
                        # Not checked recently or never checked
                        or_(
                            PoolModel.last_activity_check.is_(None),
                            PoolModel.last_activity_check < cutoff_time
                        )
                    )
                ).limit(100)  # Limit to prevent overwhelming the system
                
                pools = query.all()
                
                logger.debug(f"Found {len(pools)} pools needing activity updates")
                
            except Exception as e:
                logger.error(f"Error querying pools needing activity update: {e}")
                
        return pools
    
    # Token operations
    async def store_tokens(self, tokens: List[Token]) -> int:
        """Store token data with upsert logic."""
        if not tokens:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                
                # apply token_id fix?
                print("-store_tokens--")
                print(datetime.utcnow())
                print("---")
                
                for token in tokens:
                    print("-token_id--")
                    print(token.id)
                    print("---")

                    existing_token = session.query(TokenModel).filter_by(id=token.id).first()

                    print("---")
                    print("existing_token: ", vars(existing_token) if existing_token else None)
                    print("---")

                    if existing_token:
                        # Update existing token
                        existing_token.address = token.address
                        existing_token.name = token.name
                        existing_token.symbol = token.symbol
                        existing_token.decimals = token.decimals
                        existing_token.network = token.network
                        existing_token.last_updated = datetime.utcnow()

                        print("---")
                        print("updated_token: ", vars(existing_token))
                        print("---")
                        # actually perform query?

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
    
    async def get_token(self, pool_id: str, token_id: str) -> Optional[Token]:
        """Get a token by ID."""

        #print("-retreiving token by token_id: ", token_id) # missing network identifier
        #print("-pool_id: ", pool_id)

        prefix, _, _ = pool_id.partition('_')
        lookup_id = prefix + '_' + token_id

        with self.connection.get_session() as session:
            token_model = session.query(TokenModel).filter_by(id=lookup_id).first()
            
            #print("--retrieved token_model: ")
            #print(vars(token_model))

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
    
    async def get_token_by_id(self, token_id: str) -> Optional[TokenModel]:
        """
        Get a token by ID (database model).
        
        Args:
            token_id: Token identifier
            
        Returns:
            Token model instance or None if not found
        """
        try:
            with self.connection.get_session() as session:
                return session.query(TokenModel).filter_by(id=token_id).first()
        except Exception as e:
            logger.error(f"Error getting token by ID {token_id}: {e}")
            return None
    
    async def store_token(self, token: TokenModel) -> None:
        """
        Store a single token record.
        
        Args:
            token: Token model instance to store
        """
        with self.connection.get_session() as session:
            try:
                session.add(token)
                session.commit()
                logger.debug(f"Stored token {token.id}")
            except IntegrityError:
                session.rollback()
                # Token already exists, update it
                existing = session.query(TokenModel).filter_by(id=token.id).first()
                if existing:
                    existing.address = token.address
                    existing.name = token.name
                    existing.symbol = token.symbol
                    existing.decimals = token.decimals
                    existing.network = token.network
                    existing.last_updated = token.last_updated
                    session.commit()
                    logger.debug(f"Updated existing token {token.id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing token {token.id}: {e}")
                raise
    
    # DEX operations
    async def store_dex_data(self, dexes: List[DEXModel]) -> int:
        """Store DEX data with upsert logic."""
        if not dexes:
            return 0
        
        stored_count = 0
        
        with self.connection.get_session() as session:
            try:
                for dex in dexes:
                    existing_dex = session.query(DEXModel).filter_by(id=dex.id).first()
                    if existing_dex:
                        # Update existing DEX
                        existing_dex.name = dex.name
                        existing_dex.network = dex.network
                        existing_dex.last_updated = datetime.utcnow()
                    else:
                        # Create new DEX
                        session.add(dex)
                        stored_count += 1
                
                session.commit()
                logger.info(f"Stored {stored_count} new DEXes, updated {len(dexes) - stored_count} existing DEXes")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing DEX data: {e}")
                raise
        
        return stored_count
    
    async def get_dex_by_id(self, dex_id: str) -> Optional[DEXModel]:
        """Get a DEX by ID."""
        with self.connection.get_session() as session:
            return session.query(DEXModel).filter_by(id=dex_id).first()
    
    async def store_dex(self, dex: DEXModel) -> None:
        """
        Store a single DEX record.
        
        Args:
            dex: DEX model instance to store
        """
        with self.connection.get_session() as session:
            try:
                session.add(dex)
                session.commit()
                logger.debug(f"Stored DEX {dex.id}")
            except IntegrityError:
                session.rollback()
                # DEX already exists, update it
                existing = session.query(DEXModel).filter_by(id=dex.id).first()
                if existing:
                    existing.name = dex.name
                    existing.network = dex.network
                    existing.last_updated = dex.last_updated
                    session.commit()
                    logger.debug(f"Updated existing DEX {dex.id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing DEX {dex.id}: {e}")
                raise
    
    async def get_dexes_by_network(self, network: str) -> List[DEXModel]:
        """Get all DEXes for a specific network."""
        with self.connection.get_session() as session:
            return session.query(DEXModel).filter_by(network=network).all()
    
    # OHLCV operations
    async def store_ohlcv_data(self, data: List[OHLCVRecord]) -> int:
        """
        Store OHLCV data with duplicate prevention using composite keys.
        
        Uses SQLite's INSERT OR REPLACE for efficient upsert operations.
        The unique constraint on (pool_id, timeframe, timestamp) prevents duplicates.
        """
        if not data:
            return 0
        
        stored_count = 0
        updated_count = 0
        
        with self.connection.get_session() as session:
            try:
                # Validate data integrity before storing
                validated_data = []
                for record in data:
                    validation_errors = self._validate_ohlcv_record(record)
                    if validation_errors:
                        logger.warning(f"Skipping invalid OHLCV record for pool {record.pool_id}: {validation_errors}")
                        continue
                    validated_data.append(record)
                
                # Use batch upsert for better performance
                for record in validated_data:
                    
                    database_id = "solana_"+record.pool_id
                    
                    # Use SQLite's INSERT OR REPLACE for atomic upsert
                    stmt = sqlite_insert(OHLCVDataModel).values(
                        pool_id=database_id,
                        timeframe=record.timeframe,
                        timestamp=record.timestamp,
                        open_price=record.open_price,
                        high_price=record.high_price,
                        low_price=record.low_price,
                        close_price=record.close_price,
                        volume_usd=record.volume_usd,
                        datetime=record.datetime,
                    )
                    
                    # Check if record exists to determine if it's an insert or update
                    existing = session.query(OHLCVDataModel).filter(
                        and_(
                            OHLCVDataModel.pool_id == database_id,
                            OHLCVDataModel.timeframe == record.timeframe,
                            OHLCVDataModel.timestamp == record.timestamp
                        )
                    ).first()
                    
                    if existing:
                        # Update existing record
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['pool_id', 'timeframe', 'timestamp'],
                            set_=dict(
                                open_price=stmt.excluded.open_price,
                                high_price=stmt.excluded.high_price,
                                low_price=stmt.excluded.low_price,
                                close_price=stmt.excluded.close_price,
                                volume_usd=stmt.excluded.volume_usd,
                                datetime=stmt.excluded.datetime,
                            )
                        )
                        updated_count += 1
                    else:
                        stored_count += 1
                    
                    session.execute(stmt)
                
                session.commit()
                logger.info(f"Stored {stored_count} new OHLCV records, updated {updated_count} existing records")
                
            except IntegrityError as e:
                session.rollback()
                logger.error(f"Integrity constraint violation in OHLCV data: {e}")
                raise
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing OHLCV data: {e}")
                raise
        
        # Return total processed records (new + updated)
        return stored_count + updated_count
    
    def _validate_ohlcv_record(self, record: OHLCVRecord) -> List[str]:
        """
        Validate OHLCV record for data integrity.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check price relationships
        if record.high_price < record.low_price:
            errors.append("High price cannot be less than low price")
        
        if record.open_price < 0 or record.close_price < 0:
            errors.append("Prices cannot be negative")
        
        if not (record.low_price <= record.open_price <= record.high_price):
            errors.append("Open price must be between low and high prices")
        
        if not (record.low_price <= record.close_price <= record.high_price):
            errors.append("Close price must be between low and high prices")
        
        # Check volume
        if record.volume_usd < 0:
            errors.append("Volume cannot be negative")
        
        # Check timestamp consistency
        if record.timestamp <= 0:
            errors.append("Timestamp must be positive")
        
        return errors
    
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
        """
        Identify gaps in OHLCV data for a pool/timeframe with enhanced detection.
        
        This method performs comprehensive gap analysis including:
        - Missing data at the beginning and end of the range
        - Gaps between consecutive records
        - Validation of expected intervals based on timeframe
        """
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
            try:
                interval_seconds = self._get_timeframe_seconds(timeframe)
            except ValueError as e:
                logger.error(f"Invalid timeframe {timeframe}: {e}")
                return gaps
            
            # Align start time to timeframe boundary for accurate gap detection
            aligned_start = self._align_to_timeframe(start, timeframe)
            aligned_end = self._align_to_timeframe(end, timeframe)
            
            # Check for gap at the beginning
            first_expected = aligned_start
            if records[0].datetime > first_expected:
                gaps.append(Gap(
                    start_time=first_expected,
                    end_time=records[0].datetime,
                    pool_id=pool_id,
                    timeframe=timeframe
                ))
            
            # Check for gaps between records with tolerance for minor timing differences
            tolerance_seconds = min(60, interval_seconds // 10)  # 1 minute or 10% of interval
            
            for i in range(len(records) - 1):
                current_time = records[i].datetime
                next_time = records[i + 1].datetime
                expected_next = current_time + timedelta(seconds=interval_seconds)
                
                # Allow for small timing differences
                if next_time > expected_next + timedelta(seconds=tolerance_seconds):
                    gaps.append(Gap(
                        start_time=expected_next,
                        end_time=next_time,
                        pool_id=pool_id,
                        timeframe=timeframe
                    ))
            
            # Check for gap at the end
            last_record_time = records[-1].datetime
            expected_next = last_record_time + timedelta(seconds=interval_seconds)
            
            if expected_next <= aligned_end:
                gaps.append(Gap(
                    start_time=expected_next,
                    end_time=aligned_end,
                    pool_id=pool_id,
                    timeframe=timeframe
                ))
        
        # Filter out very small gaps (less than one interval)
        significant_gaps = []
        for gap in gaps:
            gap_duration = (gap.end_time - gap.start_time).total_seconds()
            if gap_duration >= interval_seconds:
                significant_gaps.append(gap)
        
        return significant_gaps
    
    def _align_to_timeframe(self, dt: datetime, timeframe: str) -> datetime:
        """
        Align datetime to timeframe boundary for accurate gap detection.
        
        Args:
            dt: Datetime to align
            timeframe: Timeframe string (e.g., '1h', '5m', '1d')
            
        Returns:
            Aligned datetime
        """
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            # Align to minute boundary
            aligned_minute = (dt.minute // minutes) * minutes
            return dt.replace(minute=aligned_minute, second=0, microsecond=0)
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            # Align to hour boundary
            aligned_hour = (dt.hour // hours) * hours
            return dt.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
        elif timeframe.endswith('d'):
            # Align to day boundary
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return dt
    
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
        """
        Store trade data with enhanced duplicate prevention.
        
        Uses primary key constraints and additional validation to prevent
        duplicate trades while handling edge cases gracefully.
        """
        if not data:
            return 0
        
        stored_count = 0
        duplicate_count = 0

        print("-store_trade_data--")

        with self.connection.get_session() as session:
            try:
                # Validate and deduplicate input data
                validated_data = []
                seen_ids = set()

                # optimized method
                
                
                ids_to_check = []                

                #existing_ids = session.query(TradeModel.id).filter(TradeModel.id.in_(ids_to_check)).all()
                #existing_ids_set = {id_tuple[0] for id_tuple in existing_ids}
                
                for record in data:
                    ids_to_check.append(record.id)
                
                existing_ids = session.query(TradeModel.id).filter(TradeModel.id.in_(ids_to_check)).all()
                existing_ids_set = {id_tuple[0] for id_tuple in existing_ids}
                non_existent_ids = [id_val for id_val in ids_to_check if id_val not in existing_ids_set]

                unique_records = []
                for record in data:
                    if record.id in non_existent_ids:
                        unique_records.append(record)
                
                print("-unique_records:")
                for record in unique_records:
                    print(record.id)
                    
                    # Validate trade data
                    validation_errors = self._validate_trade_record(record)
                    if validation_errors:
                        logger.warning(f"Skipping invalid trade record {record.id}: {validation_errors}")
                        continue
                    
                    # append network prefix to record.pool_id -- this fun pattern is everywhere!
                    prefix, _, _ = record.id.partition('_')                    
                    pool_id_with_prefix = prefix + '_' + record.pool_id

                    #print("---")
                    #print(pool_id_with_prefix)
                    #print("---")

                    new_trade = TradeModel(
                                id=record.id,
                                pool_id=pool_id_with_prefix,
                                block_number=record.block_number,
                                tx_hash=record.tx_hash,
                                tx_from_address=record.tx_from_address,
                                from_token_amount=record.from_token_amount,
                                to_token_amount=record.to_token_amount,
                                price_usd=record.price_usd,
                                volume_usd=record.volume_usd,
                                side=record.side,
                                block_timestamp=record.block_timestamp,
                            )

                    validated_data.append(new_trade)

                stored_count = len(validated_data) #non_existent_ids
                duplicate_count = len(existing_ids) #existing_ids

                session.bulk_save_objects(validated_data)

                """ try:                    
                    session.bulk_save_objects(validated_data)
                
                except IntegrityError as e:
                    # Handle race condition where record was inserted between check and insert
                    print("Integrity Error: ")
                    print(e)
                    session.rollback() # this is causing none of the records to be written """                    

                # records_to_insert.append(new_trade)
                # session.bulk_save_objects(unique_records)

                # seen_ids.add(record.id) # this is being called when a race condition is met, causing the record to not insert at all

                """ 
                for record in data:                    
                    # Skip duplicates within the batch
                    if record.id in seen_ids:
                        duplicate_count += 1
                        continue
                    seen_ids.add(record.id) # this is being called when a race condition is met, causing the record to not insert at all
                    
                    # Validate trade data
                    validation_errors = self._validate_trade_record(record)
                    if validation_errors:
                        logger.warning(f"Skipping invalid trade record {record.id}: {validation_errors}")
                        continue
                    
                    validated_data.append(record)
                
                # Batch insert with duplicate handling
                records_to_insert = []
                for record in validated_data:
                    try:
                        # Check if trade already exists
                        
                        # causing issues by overloading SQLite
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
                            records_to_insert.append(new_trade)
                            #session.add(new_trade)
                            stored_count += 1
                        else:
                            duplicate_count += 1
                    
                    except IntegrityError:
                        # Handle race condition where record was inserted between check and insert
                        print("--- race condition ---")
                        duplicate_count += 1
                        session.rollback() # this is causing none of the records to be written
                        continue
                
                session.bulk_save_objects(records_to_insert) """

                session.commit()
                logger.info(f"Stored {stored_count} new trade records, skipped {duplicate_count} duplicates")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing trade data: {e}")
                raise
        
        return stored_count
    
    def _validate_trade_record(self, record: TradeRecord) -> List[str]:
        """
        Validate trade record for data integrity.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check required fields
        if not record.id:
            errors.append("Trade ID is required")
        
        if not record.pool_id:
            errors.append("Pool ID is required")
        
        # Check amounts
        if record.from_token_amount is not None and record.from_token_amount < 0:
            errors.append("From token amount cannot be negative")
        
        if record.to_token_amount is not None and record.to_token_amount < 0:
            errors.append("To token amount cannot be negative")
        
        if record.price_usd is not None and record.price_usd < 0:
            errors.append("Price USD cannot be negative")
        
        if record.volume_usd is not None and record.volume_usd < 0:
            errors.append("Volume USD cannot be negative")
        
        # Check side
        if record.side and record.side not in ['buy', 'sell']:
            errors.append("Trade side must be 'buy' or 'sell'")
        
        return errors
    
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
                    tx_from_address=record_model.tx_from_address,
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
                        is_active=True
                    )
                    session.add(new_entry)
                
                session.commit()
                logger.info(f"Stored watchlist entry for pool: {pool_id}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing watchlist entry: {e}")
                raise
    
    async def add_watchlist_entry(self, entry: WatchlistEntryModel) -> None:
        """Add a new watchlist entry."""
        with self.connection.get_session() as session:
            try:
                session.add(entry)
                session.commit()
                logger.info(f"Added watchlist entry for pool: {entry.pool_id}")
                
            except IntegrityError as e:
                session.rollback()
                logger.warning(f"Watchlist entry already exists for pool {entry.pool_id}: {e}")
                raise
            except Exception as e:
                session.rollback()
                logger.error(f"Error adding watchlist entry: {e}")
                raise
    
    async def get_watchlist_entry_by_pool_id(self, pool_id: str) -> Optional[WatchlistEntryModel]:
        """Get a watchlist entry by pool ID."""
        with self.connection.get_session() as session:
            return session.query(WatchlistEntryModel).filter_by(pool_id=pool_id).first()
    
    async def update_watchlist_entry_status(self, pool_id: str, is_active: bool) -> None:
        """Update the active status of a watchlist entry."""
        with self.connection.get_session() as session:
            try:
                entry = session.query(WatchlistEntryModel).filter_by(pool_id=pool_id).first()
                if entry:
                    entry.is_active = is_active
                    session.commit()
                    logger.info(f"Updated watchlist entry status for pool {pool_id}: active={is_active}")
                else:
                    logger.warning(f"Watchlist entry not found for pool: {pool_id}")
                    
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating watchlist entry status: {e}")
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
    
    # Enhanced data integrity and continuity methods
    async def check_data_integrity(self, pool_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive data integrity checks for a pool.
        
        Returns:
            Dictionary containing integrity check results
        """
        integrity_report = {
            'pool_id': pool_id,
            'checks_performed': [],
            'issues_found': [],
            'data_quality_score': 1.0
        }
        
        with self.connection.get_session() as session:
            # Check if pool exists
            pool = session.query(PoolModel).filter_by(id=pool_id).first()
            if not pool:
                integrity_report['issues_found'].append(f"Pool {pool_id} not found")
                integrity_report['data_quality_score'] = 0.0
                return integrity_report
            
            integrity_report['checks_performed'].append('pool_existence')
            
            # Check OHLCV data integrity
            ohlcv_issues = await self._check_ohlcv_integrity(session, pool_id)
            integrity_report['issues_found'].extend(ohlcv_issues)
            integrity_report['checks_performed'].append('ohlcv_integrity')
            
            # Check trade data integrity
            trade_issues = await self._check_trade_integrity(session, pool_id)
            integrity_report['issues_found'].extend(trade_issues)
            integrity_report['checks_performed'].append('trade_integrity')
            
            # Calculate overall data quality score
            total_issues = len(integrity_report['issues_found'])
            if total_issues == 0:
                integrity_report['data_quality_score'] = 1.0
            else:
                # Reduce score based on number of issues (capped at 0.0)
                integrity_report['data_quality_score'] = max(0.0, 1.0 - (total_issues * 0.1))
        
        return integrity_report
    
    async def _check_ohlcv_integrity(self, session: Session, pool_id: str) -> List[str]:
        """Check OHLCV data integrity for a pool."""
        issues = []
        
        # Check for invalid price relationships
        invalid_prices = session.query(OHLCVDataModel).filter(
            and_(
                OHLCVDataModel.pool_id == pool_id,
                or_(
                    OHLCVDataModel.high_price < OHLCVDataModel.low_price,
                    OHLCVDataModel.open_price < 0,
                    OHLCVDataModel.close_price < 0,
                    OHLCVDataModel.volume_usd < 0
                )
            )
        ).count()
        
        if invalid_prices > 0:
            issues.append(f"Found {invalid_prices} OHLCV records with invalid price relationships")
        
        # Check for duplicate timestamps
        duplicate_timestamps = session.query(
            OHLCVDataModel.pool_id,
            OHLCVDataModel.timeframe,
            OHLCVDataModel.timestamp,
            func.count(OHLCVDataModel.id).label('count')
        ).filter(
            OHLCVDataModel.pool_id == pool_id
        ).group_by(
            OHLCVDataModel.pool_id,
            OHLCVDataModel.timeframe,
            OHLCVDataModel.timestamp
        ).having(func.count(OHLCVDataModel.id) > 1).all()
        
        if duplicate_timestamps:
            issues.append(f"Found {len(duplicate_timestamps)} duplicate OHLCV timestamps")
        
        return issues
    
    async def _check_trade_integrity(self, session: Session, pool_id: str) -> List[str]:
        """Check trade data integrity for a pool."""
        issues = []
        
        # Check for invalid trade amounts
        invalid_trades = session.query(TradeModel).filter(
            and_(
                TradeModel.pool_id == pool_id,
                or_(
                    TradeModel.volume_usd < 0,
                    TradeModel.price_usd < 0
                )
            )
        ).count()
        
        if invalid_trades > 0:
            issues.append(f"Found {invalid_trades} trade records with invalid amounts")
        
        # Check for trades with missing critical data
        incomplete_trades = session.query(TradeModel).filter(
            and_(
                TradeModel.pool_id == pool_id,
                or_(
                    TradeModel.block_timestamp.is_(None),
                    TradeModel.volume_usd.is_(None)
                )
            )
        ).count()
        
        if incomplete_trades > 0:
            issues.append(f"Found {incomplete_trades} trade records with missing critical data")
        
        return issues
    
    async def get_data_statistics(self, pool_id: str) -> Dict[str, Any]:
        """
        Get comprehensive data statistics for a pool.
        
        Returns:
            Dictionary containing data statistics
        """
        stats = {
            'pool_id': pool_id,
            'ohlcv_stats': {},
            'trade_stats': {},
            'data_coverage': {}
        }
        
        with self.connection.get_session() as session:
            # OHLCV statistics
            ohlcv_count = session.query(OHLCVDataModel).filter_by(pool_id=pool_id).count()
            stats['ohlcv_stats']['total_records'] = ohlcv_count
            
            if ohlcv_count > 0:
                # Get timeframe distribution
                timeframe_dist = session.query(
                    OHLCVDataModel.timeframe,
                    func.count(OHLCVDataModel.id).label('count')
                ).filter_by(pool_id=pool_id).group_by(OHLCVDataModel.timeframe).all()
                
                stats['ohlcv_stats']['timeframe_distribution'] = {
                    tf: count for tf, count in timeframe_dist
                }
                
                # Get date range
                date_range = session.query(
                    func.min(OHLCVDataModel.datetime).label('earliest'),
                    func.max(OHLCVDataModel.datetime).label('latest')
                ).filter_by(pool_id=pool_id).first()
                
                stats['ohlcv_stats']['date_range'] = {
                    'earliest': date_range.earliest,
                    'latest': date_range.latest
                }
            
            # Trade statistics
            trade_count = session.query(TradeModel).filter_by(pool_id=pool_id).count()
            stats['trade_stats']['total_records'] = trade_count
            
            if trade_count > 0:
                # Get volume statistics
                volume_stats = session.query(
                    func.sum(TradeModel.volume_usd).label('total_volume'),
                    func.avg(TradeModel.volume_usd).label('avg_volume'),
                    func.max(TradeModel.volume_usd).label('max_volume')
                ).filter_by(pool_id=pool_id).first()
                
                stats['trade_stats']['volume'] = {
                    'total_usd': float(volume_stats.total_volume or 0),
                    'average_usd': float(volume_stats.avg_volume or 0),
                    'max_usd': float(volume_stats.max_volume or 0)
                }
                
                # Get date range
                trade_date_range = session.query(
                    func.min(TradeModel.block_timestamp).label('earliest'),
                    func.max(TradeModel.block_timestamp).label('latest')
                ).filter_by(pool_id=pool_id).first()
                
                stats['trade_stats']['date_range'] = {
                    'earliest': trade_date_range.earliest,
                    'latest': trade_date_range.latest
                }
        
        return stats
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old data beyond the retention period.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        cleanup_stats = {
            'ohlcv_deleted': 0,
            'trades_deleted': 0,
            'cutoff_date': cutoff_date
        }
        
        with self.connection.get_session() as session:
            try:
                # Delete old OHLCV data
                ohlcv_deleted = session.query(OHLCVDataModel).filter(
                    OHLCVDataModel.datetime < cutoff_date
                ).delete()
                cleanup_stats['ohlcv_deleted'] = ohlcv_deleted
                
                # Delete old trade data
                trades_deleted = session.query(TradeModel).filter(
                    TradeModel.block_timestamp < cutoff_date
                ).delete()
                cleanup_stats['trades_deleted'] = trades_deleted
                
                session.commit()
                logger.info(f"Cleaned up {ohlcv_deleted} OHLCV records and {trades_deleted} trade records older than {cutoff_date}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error during data cleanup: {e}")
                raise
        
        return cleanup_stats
    
    async def get_table_names(self) -> List[str]:
        """
        Get list of existing table names in the database.
        
        Returns:
            List of table names
        """
        try:
            with self.connection.get_session() as session:
                # Get table names from database metadata
                inspector = session.get_bind().dialect.get_table_names(session.get_bind())
                return inspector
        except Exception as e:
            logger.error(f"Error getting table names: {e}")
            return []
    
    async def count_records(self, table_name: str) -> int:
        """
        Count records in a specific table.
        
        Args:
            table_name: Name of the table to count records in
            
        Returns:
            Number of records in the table
        """
        try:
            with self.connection.get_session() as session:
                if table_name == 'pools':
                    return session.query(PoolModel).count()
                elif table_name == 'tokens':
                    return session.query(TokenModel).count()
                elif table_name == 'ohlcv_data':
                    return session.query(OHLCVDataModel).count()
                elif table_name == 'trades':
                    return session.query(TradeModel).count()
                elif table_name == 'watchlist':
                    return session.query(WatchlistEntryModel).count()
                elif table_name == 'dexes':
                    return session.query(DEXModel).count()
                else:
                    logger.warning(f"Unknown table name: {table_name}")
                    return 0
        except Exception as e:
            logger.error(f"Error counting records in table {table_name}: {e}")
            return 0
    
    async def store_watchlist_entry(self, entry: WatchlistEntryModel) -> None:
        """
        Store a watchlist entry.
        
        Args:
            entry: WatchlistEntry object to store
        """
        with self.connection.get_session() as session:
            try:
                session.add(entry)
                session.commit()
                logger.debug(f"Stored watchlist entry for pool {entry.pool_id}")
            except IntegrityError:
                session.rollback()
                # Entry already exists, update it
                existing = session.query(WatchlistEntryModel).filter_by(pool_id=entry.pool_id).first()
                if existing:
                    existing.token_symbol = entry.token_symbol
                    existing.token_name = entry.token_name
                    existing.network_address = entry.network_address
                    existing.is_active = entry.is_active
                    session.commit()
                    logger.debug(f"Updated existing watchlist entry for pool {entry.pool_id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing watchlist entry: {e}")
                raise
    
    async def update_watchlist_entry(self, entry: WatchlistEntryModel) -> None:
        """
        Update an existing watchlist entry.
        
        Args:
            entry: WatchlistEntry object to update
        """
        with self.connection.get_session() as session:
            try:
                session.merge(entry)
                session.commit()
                logger.debug(f"Updated watchlist entry for pool {entry.pool_id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating watchlist entry: {e}")
                raise
    
    async def get_pool_by_id(self, pool_id: str) -> Optional[PoolModel]:
        """
        Get a pool by ID (database model).
        
        Args:
            pool_id: Pool identifier
            
        Returns:
            Pool model instance or None if not found
        """
        try:
            with self.connection.get_session() as session:
                return session.query(PoolModel).filter_by(id=pool_id).first()
        except Exception as e:
            logger.error(f"Error getting pool by ID {pool_id}: {e}")
            return None
    
    async def store_pool(self, pool: PoolModel) -> None:
        """
        Store a single pool record.
        
        Args:
            pool: Pool model instance to store
        """
        with self.connection.get_session() as session:
            try:
                session.add(pool)
                session.commit()
                logger.debug(f"Stored pool {pool.id}")
            except IntegrityError:
                session.rollback()
                # Pool already exists, update it
                existing = session.query(PoolModel).filter_by(id=pool.id).first()
                if existing:
                    existing.address = pool.address
                    existing.name = pool.name
                    existing.dex_id = pool.dex_id
                    existing.base_token_id = pool.base_token_id
                    existing.quote_token_id = pool.quote_token_id
                    existing.reserve_usd = pool.reserve_usd
                    existing.created_at = pool.created_at
                    existing.last_updated = pool.last_updated
                    session.commit()
                    logger.debug(f"Updated existing pool {pool.id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing pool {pool.id}: {e}")
                raise
    
    async def store_new_pools_history(self, history_record: Any) -> None:
        """
        Store a new pools history record.
        
        Args:
            history_record: NewPoolsHistory model instance to store
        """
        from gecko_terminal_collector.database.models import NewPoolsHistory
        
        with self.connection.get_session() as session:
            try:
                session.add(history_record)
                session.commit()
                logger.debug(f"Stored new pools history record for pool {history_record.pool_id}")
            except IntegrityError as e:
                session.rollback()
                # Handle unique constraint violation (duplicate record)
                if "uq_new_pools_history_pool_collected" in str(e):
                    logger.debug(f"Duplicate new pools history record for pool {history_record.pool_id} at {history_record.collected_at}")
                else:
                    logger.error(f"Integrity error storing new pools history: {e}")
                    raise
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing new pools history record: {e}")
                raise
    
    # Discovery metadata operations
    async def store_discovery_metadata(self, discovery_metadata: DiscoveryMetadataModel) -> None:
        """
        Store discovery metadata record.
        
        Args:
            discovery_metadata: DiscoveryMetadata model instance to store
        """
        with self.connection.get_session() as session:
            try:
                session.add(discovery_metadata)
                session.commit()
                logger.debug(f"Stored discovery metadata record: {discovery_metadata.discovery_type} for {discovery_metadata.target_dex}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing discovery metadata: {e}")
                raise
    
    async def get_discovery_metadata(
        self,
        discovery_type: Optional[str] = None,
        target_dex: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[DiscoveryMetadataModel]:
        """
        Get discovery metadata records with optional filtering.
        
        Args:
            discovery_type: Filter by discovery type ("dex", "pool", "token")
            target_dex: Filter by target DEX ID
            start_time: Filter records after this time
            end_time: Filter records before this time
            limit: Maximum number of records to return
            
        Returns:
            List of DiscoveryMetadata records
        """
        with self.connection.get_session() as session:
            query = session.query(DiscoveryMetadataModel)
            
            if discovery_type:
                query = query.filter(DiscoveryMetadataModel.discovery_type == discovery_type)
            
            if target_dex:
                query = query.filter(DiscoveryMetadataModel.target_dex == target_dex)
            
            if start_time:
                query = query.filter(DiscoveryMetadataModel.discovery_time >= start_time)
            
            if end_time:
                query = query.filter(DiscoveryMetadataModel.discovery_time <= end_time)
            
            query = query.order_by(desc(DiscoveryMetadataModel.discovery_time))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    async def get_latest_discovery_metadata(self, discovery_type: str, target_dex: Optional[str] = None) -> Optional[DiscoveryMetadataModel]:
        """
        Get the most recent discovery metadata record for a specific type and optional DEX.
        
        Args:
            discovery_type: Type of discovery ("dex", "pool", "token")
            target_dex: Optional DEX ID to filter by
            
        Returns:
            Most recent DiscoveryMetadata record or None
        """
        with self.connection.get_session() as session:
            query = session.query(DiscoveryMetadataModel).filter(
                DiscoveryMetadataModel.discovery_type == discovery_type
            )
            
            if target_dex:
                query = query.filter(DiscoveryMetadataModel.target_dex == target_dex)
            
            return query.order_by(desc(DiscoveryMetadataModel.discovery_time)).first()
    
    async def get_discovery_statistics(
        self,
        discovery_type: Optional[str] = None,
        target_dex: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get discovery statistics for the specified period.
        
        Args:
            discovery_type: Filter by discovery type
            target_dex: Filter by target DEX
            days: Number of days to look back
            
        Returns:
            Dictionary with discovery statistics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        with self.connection.get_session() as session:
            query = session.query(DiscoveryMetadataModel).filter(
                DiscoveryMetadataModel.discovery_time >= start_time
            )
            
            if discovery_type:
                query = query.filter(DiscoveryMetadataModel.discovery_type == discovery_type)
            
            if target_dex:
                query = query.filter(DiscoveryMetadataModel.target_dex == target_dex)
            
            records = query.all()
            
            if not records:
                return {
                    "total_discoveries": 0,
                    "total_pools_discovered": 0,
                    "total_pools_filtered": 0,
                    "total_api_calls": 0,
                    "total_errors": 0,
                    "average_execution_time": 0.0,
                    "success_rate": 0.0,
                }
            
            total_discoveries = len(records)
            total_pools_discovered = sum(r.pools_discovered or 0 for r in records)
            total_pools_filtered = sum(r.pools_filtered or 0 for r in records)
            total_api_calls = sum(r.api_calls_made or 0 for r in records)
            total_errors = sum(r.errors_encountered or 0 for r in records)
            
            execution_times = [r.execution_time_seconds for r in records if r.execution_time_seconds]
            average_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
            
            successful_discoveries = sum(1 for r in records if (r.errors_encountered or 0) == 0)
            success_rate = (successful_discoveries / total_discoveries * 100) if total_discoveries > 0 else 0.0
            
            return {
                "total_discoveries": total_discoveries,
                "total_pools_discovered": total_pools_discovered,
                "total_pools_filtered": total_pools_filtered,
                "total_api_calls": total_api_calls,
                "total_errors": total_errors,
                "average_execution_time": float(average_execution_time),
                "success_rate": float(success_rate),
            }
    
    async def cleanup_old_discovery_metadata(self, days_to_keep: int = 90) -> int:
        """
        Clean up old discovery metadata records.
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            Number of records deleted
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self.connection.get_session() as session:
            try:
                deleted_count = session.query(DiscoveryMetadataModel).filter(
                    DiscoveryMetadataModel.created_at < cutoff_time
                ).delete()
                
                session.commit()
                logger.info(f"Cleaned up {deleted_count} old discovery metadata records")
                return deleted_count
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error cleaning up discovery metadata: {e}")
                raise