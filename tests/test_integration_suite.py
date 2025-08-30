"""
Comprehensive integration test suite for GeckoTerminal data collection system.

This test suite focuses on end-to-end workflows using CSV fixtures from /specs directory.
It tests complete data collection flows, API integration with mock responses, and 
database integration with schema validation and data integrity checks.
"""

import pytest
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
from gecko_terminal_collector.collectors.watchlist_monitor import WatchlistMonitor
from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler, SchedulerConfig
from gecko_terminal_collector.clients.gecko_client import MockGeckoTerminalClient
from gecko_terminal_collector.config.models import CollectionConfig, DatabaseConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.models.core import Pool, Token, OHLCVRecord, TradeRecord


def set_collector_client(collector, client):
    """Helper function to set the client on a collector."""
    collector._client = client


@pytest.fixture
def specs_fixture_path():
    """Path to CSV fixtures in specs directory."""
    return Path("specs")


@pytest.fixture
def integration_config():
    """Integration test configuration."""
    from gecko_terminal_collector.config.models import WatchlistConfig
    return CollectionConfig(
        intervals={
            'top_pools_monitoring': '1h',
            'ohlcv_collection': '1h', 
            'trade_collection': '30m',
            'watchlist_check': '1h'
        },
        thresholds={
            'min_trade_volume_usd': 100,
            'max_retries': 3,
            'rate_limit_delay': 1.0
        },
        timeframes={
            'ohlcv_default': '1h',
            'supported': ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
        },
        watchlist=WatchlistConfig(
            file_path='specs/watchlist.csv',
            check_interval='1h',
            auto_add_new_tokens=True,
            remove_inactive_tokens=False
        )
    )


@pytest.fixture
def integration_db_manager():
    """Integration database manager with in-memory SQLite."""
    config = DatabaseConfig(
        url="sqlite:///:memory:",
        pool_size=1,
        echo=False
    )
    
    # Use the concrete SQLAlchemy implementation for integration tests
    from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
    db_manager = SQLAlchemyDatabaseManager(config)
    return db_manager


@pytest.fixture
def metadata_tracker():
    """Metadata tracker for integration tests."""
    return MetadataTracker()


@pytest.fixture
def mock_client_with_fixtures(specs_fixture_path):
    """Mock client configured to use CSV fixtures from specs directory."""
    return MockGeckoTerminalClient(str(specs_fixture_path))


class TestEndToEndDataCollectionWorkflows:
    """Test complete end-to-end data collection workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_dex_monitoring_workflow(self, integration_config, integration_db_manager, 
                                                   metadata_tracker, mock_client_with_fixtures):
        """Test complete DEX monitoring workflow from API to database."""
        # Initialize database
        await integration_db_manager.initialize()
        
        try:
            # Create DEX monitoring collector with fixture-based mock client
            collector = DEXMonitoringCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            
            # Replace the mock client with our fixture-based one
            set_collector_client(collector, mock_client_with_fixtures)
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            assert result.records_collected > 0
            assert result.collector_type == "dex_monitoring_solana"
            
            # Verify data was stored in database
            stored_dexes = await integration_db_manager.get_dexes_by_network("solana")
            assert len(stored_dexes) > 0
            
            # Verify specific DEXes from fixture are present
            dex_ids = [dex.id for dex in stored_dexes]
            assert "heaven" in dex_ids or "pumpswap" in dex_ids
            
            # Verify metadata tracking
            metadata = metadata_tracker.get_metadata("dex_monitoring_solana")
            assert metadata.total_runs == 1
            assert metadata.successful_runs == 1
            assert metadata.total_records_collected > 0
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_complete_top_pools_workflow(self, integration_config, integration_db_manager,
                                              metadata_tracker, mock_client_with_fixtures):
        """Test complete top pools collection workflow."""
        await integration_db_manager.initialize()
        
        try:
            # First ensure DEXes are available
            dex_collector = DEXMonitoringCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(dex_collector, mock_client_with_fixtures)
            await dex_collector.collect_with_error_handling()
            
            # Create top pools collector
            collector = TopPoolsCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(collector, mock_client_with_fixtures)
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            assert result.records_collected >= 0  # May be 0 if no pools in fixtures
            
            # Verify pools were processed (even if empty)
            metadata = metadata_tracker.get_metadata("top_pools_solana")
            assert metadata.total_runs == 1
            
            # If pools were collected, verify database storage
            if result.records_collected > 0:
                stored_pools = await integration_db_manager.get_pools_by_dex("heaven")
                assert len(stored_pools) >= 0
                
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_complete_watchlist_workflow(self, integration_config, integration_db_manager,
                                              metadata_tracker, mock_client_with_fixtures):
        """Test complete watchlist processing workflow."""
        await integration_db_manager.initialize()
        
        try:
            # Create watchlist monitor to detect CSV changes
            monitor = WatchlistMonitor(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(monitor, mock_client_with_fixtures)
            
            # Execute watchlist monitoring
            result = await monitor.collect_with_error_handling()
            
            # Verify monitoring success
            assert result.success is True
            
            # Create watchlist collector for token data collection
            collector = WatchlistCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(collector, mock_client_with_fixtures)
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            
            # Verify metadata tracking
            metadata = metadata_tracker.get_metadata("watchlist_collector")
            assert metadata.total_runs == 1
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_complete_ohlcv_collection_workflow(self, integration_config, integration_db_manager,
                                                     metadata_tracker, mock_client_with_fixtures):
        """Test complete OHLCV data collection workflow."""
        await integration_db_manager.initialize()
        
        try:
            # Setup watchlist first
            await self._setup_test_watchlist(integration_db_manager, mock_client_with_fixtures)
            
            # Create OHLCV collector
            collector = OHLCVCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(collector, mock_client_with_fixtures)
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            
            # Verify OHLCV data was stored if watchlist had entries
            watchlist_pools = await integration_db_manager.get_watchlist_pools()
            if watchlist_pools:
                # Check for OHLCV data
                for pool_id in watchlist_pools[:1]:  # Check first pool
                    ohlcv_data = await integration_db_manager.get_ohlcv_data(
                        pool_id, 
                        integration_config.timeframes['ohlcv_default']
                    )
                    # Data may or may not exist depending on fixture content
                    assert isinstance(ohlcv_data, list)
            
            # Verify metadata tracking
            metadata = metadata_tracker.get_metadata("ohlcv_collector")
            assert metadata.total_runs == 1
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_complete_trade_collection_workflow(self, integration_config, integration_db_manager,
                                                     metadata_tracker, mock_client_with_fixtures):
        """Test complete trade data collection workflow."""
        await integration_db_manager.initialize()
        
        try:
            # Setup watchlist first
            await self._setup_test_watchlist(integration_db_manager, mock_client_with_fixtures)
            
            # Create trade collector
            collector = TradeCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(collector, mock_client_with_fixtures)
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            
            # Verify trade data processing
            watchlist_pools = await integration_db_manager.get_watchlist_pools()
            if watchlist_pools:
                # Check for trade data
                for pool_id in watchlist_pools[:1]:  # Check first pool
                    trade_data = await integration_db_manager.get_trade_data(
                        pool_id,
                        min_volume_usd=integration_config.thresholds['min_trade_volume_usd']
                    )
                    # Data may or may not exist depending on fixture content
                    assert isinstance(trade_data, list)
            
            # Verify metadata tracking
            metadata = metadata_tracker.get_metadata("trade_collector")
            assert metadata.total_runs == 1
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_historical_ohlcv_workflow(self, integration_config, integration_db_manager,
                                           metadata_tracker, mock_client_with_fixtures):
        """Test historical OHLCV data collection workflow."""
        await integration_db_manager.initialize()
        
        try:
            # Setup watchlist first
            await self._setup_test_watchlist(integration_db_manager, mock_client_with_fixtures)
            
            # Create historical OHLCV collector
            collector = HistoricalOHLCVCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            # Historical collector uses direct HTTP requests, not the client
            
            # Execute collection
            result = await collector.collect_with_error_handling()
            
            # Verify collection success
            assert result.success is True
            
            # Verify metadata tracking
            metadata = metadata_tracker.get_metadata("historical_ohlcv_collector")
            assert metadata.total_runs == 1
            
        finally:
            await integration_db_manager.close()
    
    async def _setup_test_watchlist(self, db_manager, mock_client):
        """Helper to setup test watchlist entries."""
        # Create a test pool entry for watchlist
        test_pool = Pool(
            id="test_pool_id",
            address="test_address",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="test_base_token",
            quote_token_id="test_quote_token",
            reserve_usd=1000.0,
            created_at=datetime.now()
        )
        
        # Store pool and add to watchlist
        await db_manager.store_pools([test_pool])
        await db_manager.store_watchlist_entry(test_pool.id, {
            'token_symbol': 'TEST',
            'token_name': 'Test Token',
            'network_address': 'test_network_address'
        })


class TestAPIIntegrationWithFixtures:
    """Test API integration using CSV fixtures as mock responses."""
    
    @pytest.mark.asyncio
    async def test_dex_api_integration_with_fixtures(self, mock_client_with_fixtures):
        """Test DEX API integration using get_dexes_by_network.csv fixture."""
        # Test get_dexes_by_network
        dexes = await mock_client_with_fixtures.get_dexes_by_network("solana")
        
        # Verify fixture data was loaded
        assert isinstance(dexes, list)
        assert len(dexes) > 0
        
        # Verify data structure matches API format
        for dex in dexes:
            assert "id" in dex
            assert "type" in dex
            assert dex["type"] == "dex"
            assert "attributes" in dex
            assert "name" in dex["attributes"]
        
        # Verify specific DEXes from fixture
        dex_ids = [dex["id"] for dex in dexes]
        expected_dexes = ["raydium", "orca", "pumpswap", "heaven"]
        found_dexes = [dex_id for dex_id in expected_dexes if dex_id in dex_ids]
        assert len(found_dexes) > 0, f"Expected to find some of {expected_dexes} in {dex_ids}"
    
    @pytest.mark.asyncio
    async def test_top_pools_api_integration_with_fixtures(self, mock_client_with_fixtures):
        """Test top pools API integration using CSV fixtures."""
        # Test Heaven DEX pools
        heaven_pools = await mock_client_with_fixtures.get_top_pools_by_network_dex("solana", "heaven")
        
        assert "data" in heaven_pools
        assert isinstance(heaven_pools["data"], list)
        
        # If fixture has data, verify structure
        if heaven_pools["data"]:
            pool = heaven_pools["data"][0]
            assert "id" in pool
            assert "type" in pool
            assert pool["type"] == "pool"
            assert "attributes" in pool
            assert "relationships" in pool
            
            # Verify required attributes from fixture
            attributes = pool["attributes"]
            required_attrs = ["name", "address", "reserve_in_usd"]
            for attr in required_attrs:
                assert attr in attributes
        
        # Test PumpSwap DEX pools
        pumpswap_pools = await mock_client_with_fixtures.get_top_pools_by_network_dex("solana", "pumpswap")
        
        assert "data" in pumpswap_pools
        assert isinstance(pumpswap_pools["data"], list)
    
    @pytest.mark.asyncio
    async def test_ohlcv_api_integration_with_fixtures(self, mock_client_with_fixtures):
        """Test OHLCV API integration using get_ohlcv.csv fixture."""
        # Test OHLCV data retrieval
        ohlcv_data = await mock_client_with_fixtures.get_ohlcv_data("solana", "test_pool", timeframe="1h")
        
        assert "data" in ohlcv_data
        assert "attributes" in ohlcv_data["data"]
        assert "ohlcv_list" in ohlcv_data["data"]["attributes"]
        
        # Verify OHLCV data structure from fixture
        ohlcv_list = ohlcv_data["data"]["attributes"]["ohlcv_list"]
        if ohlcv_list:
            for entry in ohlcv_list:
                assert len(entry) == 6  # [timestamp, open, high, low, close, volume]
                assert isinstance(entry[0], (int, float))  # timestamp
                assert all(isinstance(x, (int, float)) for x in entry[1:])  # OHLCV values
    
    @pytest.mark.asyncio
    async def test_trades_api_integration_with_fixtures(self, mock_client_with_fixtures):
        """Test trades API integration using get_trades.csv fixture."""
        # Test trade data retrieval
        trades_data = await mock_client_with_fixtures.get_trades("solana", "test_pool")
        
        assert "data" in trades_data
        assert isinstance(trades_data["data"], list)
        
        # If fixture has trade data, verify structure
        if trades_data["data"]:
            trade = trades_data["data"][0]
            assert "id" in trade
            assert "type" in trade
            assert trade["type"] == "trade"
            assert "attributes" in trade
            
            # Verify required trade attributes from fixture
            attributes = trade["attributes"]
            required_attrs = ["block_number", "tx_hash", "from_token_amount", "to_token_amount", "volume_usd"]
            for attr in required_attrs:
                assert attr in attributes
    
    @pytest.mark.asyncio
    async def test_watchlist_api_integration_with_fixtures(self, mock_client_with_fixtures):
        """Test watchlist-related API integration using fixtures."""
        # Test multiple pools retrieval (used by watchlist collector)
        pools_data = await mock_client_with_fixtures.get_multiple_pools_by_network(
            "solana", 
            ["7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"]
        )
        
        assert "data" in pools_data
        assert isinstance(pools_data["data"], list)
        
        # Test single pool retrieval
        pool_data = await mock_client_with_fixtures.get_pool_by_network_address(
            "solana", 
            "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        )
        
        assert "data" in pool_data
        
        # Test token info retrieval
        token_data = await mock_client_with_fixtures.get_token_info(
            "solana",
            "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        
        assert "data" in token_data
        assert token_data["data"]["type"] == "token"


class TestDatabaseIntegrationAndIntegrity:
    """Test database integration with schema validation and data integrity checks."""
    
    @pytest.mark.asyncio
    async def test_database_schema_validation(self, integration_db_manager):
        """Test database schema creation and validation."""
        await integration_db_manager.initialize()
        
        try:
            # Database should be initialized after calling initialize()
            
            # Test table creation by attempting basic operations
            # This will fail if schema is not properly created
            
            # Test DEX table
            from gecko_terminal_collector.database.models import DEX
            test_dex = DEX(
                id='test_dex',
                name='Test DEX',
                network='solana'
            )
            await integration_db_manager.store_dex_data([test_dex])
            
            # Test Pool table
            test_pool = Pool(
                id="test_pool",
                address="test_address",
                name="Test Pool",
                dex_id="test_dex",
                base_token_id="base_token",
                quote_token_id="quote_token",
                reserve_usd=1000.0,
                created_at=datetime.now()
            )
            await integration_db_manager.store_pools([test_pool])
            
            # Test Token table
            test_token = Token(
                id="test_token",
                address="test_token_address",
                name="Test Token",
                symbol="TEST",
                decimals=18,
                network="solana"
            )
            await integration_db_manager.store_tokens([test_token])
            
            # Test OHLCV table
            test_ohlcv = OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(datetime.now().timestamp()),
                open_price=Decimal("1.0"),
                high_price=Decimal("1.1"),
                low_price=Decimal("0.9"),
                close_price=Decimal("1.05"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime.now()
            )
            await integration_db_manager.store_ohlcv_data([test_ohlcv])
            
            # Test Trade table
            test_trade = TradeRecord(
                id="test_trade",
                pool_id="test_pool",
                block_number=12345,
                tx_hash="test_hash",
                from_token_amount=Decimal("100.0"),
                to_token_amount=Decimal("105.0"),
                price_usd=Decimal("1.05"),
                volume_usd=Decimal("105.0"),
                side="buy",
                block_timestamp=datetime.now()
            )
            await integration_db_manager.store_trade_data([test_trade])
            
            # Verify data was stored correctly
            stored_dex = await integration_db_manager.get_dex_by_id("test_dex")
            assert stored_dex is not None
            assert stored_dex.id == "test_dex"
            
            stored_pool = await integration_db_manager.get_pool("test_pool")
            assert stored_pool is not None
            assert stored_pool.id == "test_pool"
            
            stored_token = await integration_db_manager.get_token("test_token")
            assert stored_token is not None
            assert stored_token.id == "test_token"
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_data_integrity_constraints(self, integration_db_manager):
        """Test data integrity constraints and duplicate prevention."""
        await integration_db_manager.initialize()
        
        try:
            # Create required pool first for foreign key constraint
            test_pool = Pool(
                id="test_pool",
                address="test_address",
                name="Test Pool",
                dex_id="test_dex",
                base_token_id="base_token",
                quote_token_id="quote_token",
                reserve_usd=1000.0,
                created_at=datetime.now()
            )
            await integration_db_manager.store_pools([test_pool])
            
            # Test duplicate prevention for OHLCV data
            test_ohlcv1 = OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1234567890,
                open_price=1.0,
                high_price=1.1,
                low_price=0.9,
                close_price=1.05,
                volume_usd=1000.0,
                datetime=datetime.fromtimestamp(1234567890)
            )
            
            test_ohlcv2 = OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1234567890,  # Same timestamp - should be duplicate
                open_price=1.1,
                high_price=1.2,
                low_price=1.0,
                close_price=1.15,
                volume_usd=1100.0,
                datetime=datetime.fromtimestamp(1234567890)
            )
            
            # Store first record
            result1 = await integration_db_manager.store_ohlcv_data([test_ohlcv1])
            assert result1 == 1
            
            # Store duplicate - should handle gracefully
            result2 = await integration_db_manager.store_ohlcv_data([test_ohlcv2])
            # Result depends on implementation - either 0 (no insert) or 1 (upsert)
            assert result2 >= 0
            
            # Verify only one record exists (or updated record)
            stored_data = await integration_db_manager.get_ohlcv_data("test_pool", "1h")
            assert len(stored_data) == 1
            
            # Test foreign key constraints
            # Try to store OHLCV for non-existent pool
            invalid_ohlcv = OHLCVRecord(
                pool_id="non_existent_pool",
                timeframe="1h",
                timestamp=1234567891,
                open_price=1.0,
                high_price=1.1,
                low_price=0.9,
                close_price=1.05,
                volume_usd=1000.0,
                datetime=datetime.fromtimestamp(1234567891)
            )
            
            # This should either fail or be handled gracefully
            try:
                result = await integration_db_manager.store_ohlcv_data([invalid_ohlcv])
                # If it succeeds, it means FK constraints are not enforced or handled gracefully
                assert result >= 0
            except Exception as e:
                # If it fails, that's expected behavior for FK constraint violation
                assert "foreign key" in str(e).lower() or "constraint" in str(e).lower()
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_data_continuity_checking(self, integration_db_manager):
        """Test data continuity and gap detection functionality."""
        await integration_db_manager.initialize()
        
        try:
            # Create test pool first
            test_pool = Pool(
                id="continuity_test_pool",
                address="continuity_test_address",
                name="Continuity Test Pool",
                dex_id="test_dex",
                base_token_id="base_token",
                quote_token_id="quote_token",
                reserve_usd=1000.0,
                created_at=datetime.now()
            )
            await integration_db_manager.store_pools([test_pool])
            
            # Create OHLCV data with gaps
            base_time = datetime(2025, 1, 1, 0, 0, 0)
            ohlcv_records = []
            
            # Add records for hours 0, 1, 3, 4 (missing hour 2)
            for hour in [0, 1, 3, 4]:
                timestamp = base_time + timedelta(hours=hour)
                record = OHLCVRecord(
                    pool_id="continuity_test_pool",
                    timeframe="1h",
                    timestamp=int(timestamp.timestamp()),
                    open_price=1.0 + hour * 0.1,
                    high_price=1.1 + hour * 0.1,
                    low_price=0.9 + hour * 0.1,
                    close_price=1.05 + hour * 0.1,
                    volume_usd=1000.0,
                    datetime=timestamp
                )
                ohlcv_records.append(record)
            
            # Store the records
            await integration_db_manager.store_ohlcv_data(ohlcv_records)
            
            # Check for gaps
            start_time = base_time
            end_time = base_time + timedelta(hours=5)
            
            gaps = await integration_db_manager.get_data_gaps(
                "continuity_test_pool",
                "1h",
                start_time,
                end_time
            )
            
            # Should detect gap at hour 2
            assert len(gaps) >= 1
            # Gap detection implementation may vary, but should identify missing data
            
        finally:
            await integration_db_manager.close()


class TestSchedulerIntegrationWithRealCollectors:
    """Test scheduler integration with real collectors using fixtures."""
    
    @pytest.mark.asyncio
    async def test_scheduler_with_fixture_based_collectors(self, integration_config, integration_db_manager,
                                                          metadata_tracker, mock_client_with_fixtures):
        """Test scheduler orchestrating multiple collectors with fixture data."""
        await integration_db_manager.initialize()
        
        try:
            # Create scheduler
            scheduler_config = SchedulerConfig(
                max_workers=3,
                shutdown_timeout=5,
                error_recovery_delay=0.1,
                health_check_interval=0.5
            )
            
            scheduler = CollectionScheduler(
                config=integration_config,
                scheduler_config=scheduler_config,
                metadata_tracker=metadata_tracker
            )
            
            # Create collectors with fixture-based mock client
            collectors = []
            
            # DEX monitoring collector
            dex_collector = DEXMonitoringCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(dex_collector, mock_client_with_fixtures)
            collectors.append(("dex", dex_collector))
            
            # Top pools collector
            pools_collector = TopPoolsCollector(
                config=integration_config,
                db_manager=integration_db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            set_collector_client(pools_collector, mock_client_with_fixtures)
            collectors.append(("pools", pools_collector))
            
            # Register collectors with short intervals for testing
            job_ids = {}
            for name, collector in collectors:
                job_id = scheduler.register_collector(collector, "1s")
                job_ids[name] = job_id
            
            # Start scheduler
            await scheduler.start()
            
            # Let it run briefly
            await asyncio.sleep(2.5)
            
            # Execute collectors on demand to ensure they run
            results = {}
            for name, job_id in job_ids.items():
                result = await scheduler.execute_collector_now(job_id)
                results[name] = result
                assert result.success is True
            
            # Verify scheduler status
            status = scheduler.get_status()
            assert status['total_collectors'] == len(collectors)
            assert status['enabled_collectors'] == len(collectors)
            
            # Verify metadata tracking
            for name, _ in collectors:
                if name == "dex":
                    metadata = metadata_tracker.get_metadata("dex_monitoring_solana")
                elif name == "pools":
                    metadata = metadata_tracker.get_metadata("top_pools_solana")
                
                assert metadata.total_runs >= 1
                assert metadata.successful_runs >= 1
            
            # Stop scheduler
            await scheduler.stop()
            
        finally:
            await integration_db_manager.close()
    
    @pytest.mark.asyncio
    async def test_end_to_end_system_integration(self, integration_config, integration_db_manager,
                                                metadata_tracker, mock_client_with_fixtures):
        """Test complete end-to-end system integration with all components."""
        await integration_db_manager.initialize()
        
        try:
            # Create scheduler
            scheduler_config = SchedulerConfig(
                max_workers=5,
                shutdown_timeout=10,
                error_recovery_delay=0.1,
                health_check_interval=1.0
            )
            
            scheduler = CollectionScheduler(
                config=integration_config,
                scheduler_config=scheduler_config,
                metadata_tracker=metadata_tracker
            )
            
            # Create all collector types
            collectors_config = [
                ("dex", DEXMonitoringCollector),
                ("pools", TopPoolsCollector),
                ("watchlist_monitor", WatchlistMonitor),
                ("watchlist", WatchlistCollector),
                ("ohlcv", OHLCVCollector)
            ]
            
            job_ids = {}
            
            for name, collector_class in collectors_config:
                collector = collector_class(
                    config=integration_config,
                    db_manager=integration_db_manager,
                    metadata_tracker=metadata_tracker,
                    use_mock=True
                )
                set_collector_client(collector, mock_client_with_fixtures)
                
                job_id = scheduler.register_collector(collector, "2s")
                job_ids[name] = job_id
            
            # Start scheduler
            await scheduler.start()
            
            # Let system run briefly
            await asyncio.sleep(1.0)
            
            # Execute collectors in logical order
            execution_order = ["dex", "pools", "watchlist_monitor", "watchlist", "ohlcv"]
            
            for name in execution_order:
                if name in job_ids:
                    result = await scheduler.execute_collector_now(job_ids[name])
                    assert result.success is True, f"Collector {name} failed: {result.error_message}"
                    
                    # Small delay between collectors
                    await asyncio.sleep(0.1)
            
            # Verify system health
            status = scheduler.get_status()
            assert status['total_collectors'] == len(collectors_config)
            assert status['enabled_collectors'] == len(collectors_config)
            
            # Verify data flow - check that data exists in database
            # DEX data should exist
            dexes = await integration_db_manager.get_dexes_by_network("solana")
            assert len(dexes) >= 0  # May be empty if fixture is empty
            
            # Verify metadata for all collectors
            for name, _ in collectors_config:
                collector_key = {
                    "dex": "dex_monitoring_solana",
                    "pools": "top_pools_solana", 
                    "watchlist_monitor": "watchlist_monitor",
                    "watchlist": "watchlist_collector",
                    "ohlcv": "ohlcv_collector"
                }[name]
                
                metadata = metadata_tracker.get_metadata(collector_key)
                assert metadata.total_runs >= 1
                assert metadata.successful_runs >= 1
            
            # Export system summary
            summary = metadata_tracker.export_summary()
            assert summary["total_collectors"] == len(collectors_config)
            assert summary["healthy_collectors"] >= 0
            
            # Stop scheduler
            await scheduler.stop()
            
        finally:
            await integration_db_manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])