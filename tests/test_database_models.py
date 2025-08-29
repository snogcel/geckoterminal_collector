"""
Tests for database models and SQLAlchemy implementation.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.models import Base, DEX, Pool, Token, OHLCVData, Trade, WatchlistEntry, CollectionMetadata
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.models.core import Pool as PoolModel, Token as TokenModel, OHLCVRecord, TradeRecord


@pytest.fixture
def db_config():
    """Create test database configuration."""
    return DatabaseConfig(
        url="sqlite:///:memory:",  # In-memory database for testing
        pool_size=1,
        echo=False
    )


@pytest.fixture
def db_manager(db_config):
    """Create test database manager."""
    manager = SQLAlchemyDatabaseManager(db_config)
    return manager


@pytest_asyncio.fixture
async def initialized_db(db_manager):
    """Initialize test database."""
    await db_manager.initialize()
    yield db_manager
    await db_manager.close()


class TestDatabaseModels:
    """Test database model definitions."""
    
    def test_model_creation(self, db_config):
        """Test that models can be created and tables exist."""
        engine = create_engine(db_config.url)
        Base.metadata.create_all(engine)
        
        # Verify tables were created
        inspector = engine.dialect.get_table_names(engine.connect())
        expected_tables = [
            'dexes', 'pools', 'tokens', 'ohlcv_data', 
            'trades', 'watchlist', 'collection_metadata'
        ]
        
        for table in expected_tables:
            assert table in inspector
    
    def test_dex_model(self, db_config):
        """Test DEX model operations."""
        engine = create_engine(db_config.url)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            # Create DEX
            dex = DEX(
                id="heaven",
                name="Heaven DEX",
                network="solana"
            )
            session.add(dex)
            session.commit()
            
            # Retrieve DEX
            retrieved_dex = session.query(DEX).filter_by(id="heaven").first()
            assert retrieved_dex is not None
            assert retrieved_dex.name == "Heaven DEX"
            assert retrieved_dex.network == "solana"
    
    def test_pool_model(self, db_config):
        """Test Pool model operations."""
        engine = create_engine(db_config.url)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            # Create DEX first (foreign key requirement)
            dex = DEX(id="heaven", name="Heaven DEX", network="solana")
            session.add(dex)
            
            # Create Pool
            pool = Pool(
                id="solana_test_pool",
                address="test_address",
                name="Test Pool",
                dex_id="heaven",
                base_token_id="token1",
                quote_token_id="token2",
                reserve_usd=Decimal("1000.50"),
                created_at=datetime.utcnow()
            )
            session.add(pool)
            session.commit()
            
            # Retrieve Pool
            retrieved_pool = session.query(Pool).filter_by(id="solana_test_pool").first()
            assert retrieved_pool is not None
            assert retrieved_pool.name == "Test Pool"
            assert retrieved_pool.dex_id == "heaven"
    
    def test_ohlcv_unique_constraint(self, db_config):
        """Test OHLCV unique constraint prevents duplicates."""
        engine = create_engine(db_config.url, implicit_returning=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            # Create required dependencies
            dex = DEX(id="heaven", name="Heaven DEX", network="solana")
            pool = Pool(
                id="test_pool",
                address="test_address", 
                name="Test Pool",
                dex_id="heaven"
            )
            session.add_all([dex, pool])
            session.commit()
            
            # Create first OHLCV record
            ohlcv1 = OHLCVData(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1640995200,  # 2022-01-01 00:00:00
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime(2022, 1, 1, 0, 0, 0)
            )
            session.add(ohlcv1)
            session.commit()
            
            # Try to create duplicate - should raise IntegrityError
            ohlcv2 = OHLCVData(
                pool_id="test_pool",
                timeframe="1h", 
                timestamp=1640995200,  # Same timestamp
                open_price=Decimal("101.0"),
                high_price=Decimal("111.0"),
                low_price=Decimal("96.0"),
                close_price=Decimal("106.0"),
                volume_usd=Decimal("1001.0"),
                datetime=datetime(2022, 1, 1, 0, 0, 0)
            )
            session.add(ohlcv2)
            
            with pytest.raises(Exception):  # Should raise IntegrityError
                session.commit()


class TestSQLAlchemyManager:
    """Test SQLAlchemy database manager implementation."""
    
    @pytest.mark.asyncio
    async def test_store_pools(self, initialized_db):
        """Test storing pool data."""
        pools = [
            PoolModel(
                id="test_pool_1",
                address="address_1",
                name="Test Pool 1",
                dex_id="heaven",
                base_token_id="token1",
                quote_token_id="token2",
                reserve_usd=Decimal("1000.0"),
                created_at=datetime.utcnow()
            ),
            PoolModel(
                id="test_pool_2", 
                address="address_2",
                name="Test Pool 2",
                dex_id="pumpswap",
                base_token_id="token3",
                quote_token_id="token4",
                reserve_usd=Decimal("2000.0"),
                created_at=datetime.utcnow()
            )
        ]
        
        stored_count = await initialized_db.store_pools(pools)
        assert stored_count == 2
        
        # Verify pools were stored
        retrieved_pool = await initialized_db.get_pool("test_pool_1")
        assert retrieved_pool is not None
        assert retrieved_pool.name == "Test Pool 1"
        assert retrieved_pool.dex_id == "heaven"
    
    @pytest.mark.asyncio
    async def test_store_tokens(self, initialized_db):
        """Test storing token data."""
        tokens = [
            TokenModel(
                id="token_1",
                address="token_address_1",
                name="Test Token 1",
                symbol="TT1",
                decimals=9,
                network="solana"
            ),
            TokenModel(
                id="token_2",
                address="token_address_2", 
                name="Test Token 2",
                symbol="TT2",
                decimals=6,
                network="solana"
            )
        ]
        
        stored_count = await initialized_db.store_tokens(tokens)
        assert stored_count == 2
        
        # Verify tokens were stored
        retrieved_token = await initialized_db.get_token("token_1")
        assert retrieved_token is not None
        assert retrieved_token.symbol == "TT1"
        assert retrieved_token.decimals == 9
    
    @pytest.mark.asyncio
    async def test_store_ohlcv_data(self, initialized_db):
        """Test storing OHLCV data with duplicate prevention."""
        # First create a pool
        pool = PoolModel(
            id="test_pool",
            address="test_address",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([pool])
        
        # Create OHLCV records
        ohlcv_records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1640995200,
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime(2022, 1, 1, 0, 0, 0)
            ),
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1640998800,  # Next hour
                open_price=Decimal("105.0"),
                high_price=Decimal("115.0"),
                low_price=Decimal("100.0"),
                close_price=Decimal("110.0"),
                volume_usd=Decimal("1500.0"),
                datetime=datetime(2022, 1, 1, 1, 0, 0)
            )
        ]
        
        stored_count = await initialized_db.store_ohlcv_data(ohlcv_records)
        assert stored_count == 2
        
        # Verify data was stored
        retrieved_data = await initialized_db.get_ohlcv_data("test_pool", "1h")
        assert len(retrieved_data) == 2
        assert retrieved_data[0].open_price == Decimal("100.0")
    
    @pytest.mark.asyncio
    async def test_watchlist_operations(self, initialized_db):
        """Test watchlist operations."""
        # First create a pool
        pool = PoolModel(
            id="watchlist_pool",
            address="watchlist_address",
            name="Watchlist Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([pool])
        
        # Add to watchlist
        metadata = {
            'token_symbol': 'TEST',
            'token_name': 'Test Token',
            'network_address': 'test_network_address'
        }
        await initialized_db.store_watchlist_entry("watchlist_pool", metadata)
        
        # Verify watchlist entry
        watchlist_pools = await initialized_db.get_watchlist_pools()
        assert "watchlist_pool" in watchlist_pools
        
        # Remove from watchlist
        await initialized_db.remove_watchlist_entry("watchlist_pool")
        
        # Verify removal
        watchlist_pools = await initialized_db.get_watchlist_pools()
        assert "watchlist_pool" not in watchlist_pools
    
    @pytest.mark.asyncio
    async def test_collection_metadata(self, initialized_db):
        """Test collection metadata operations."""
        collector_type = "test_collector"
        run_time = datetime.utcnow()
        
        # Update metadata for successful run
        await initialized_db.update_collection_metadata(
            collector_type, run_time, success=True
        )
        
        # Retrieve metadata
        metadata = await initialized_db.get_collection_metadata(collector_type)
        assert metadata is not None
        assert metadata['collector_type'] == collector_type
        assert metadata['run_count'] == 1
        assert metadata['error_count'] == 0
        
        # Update metadata for failed run
        await initialized_db.update_collection_metadata(
            collector_type, run_time, success=False, error_message="Test error"
        )
        
        # Verify error was recorded
        metadata = await initialized_db.get_collection_metadata(collector_type)
        assert metadata['run_count'] == 2
        assert metadata['error_count'] == 1
        assert metadata['last_error'] == "Test error"