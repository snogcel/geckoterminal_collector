"""
Tests for the TradeCollector.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.config.models import CollectionConfig, DEXConfig, ThresholdConfig
from gecko_terminal_collector.models.core import (
    TradeRecord, ValidationResult, CollectionResult
)


class TestTradeCollector:
    """Test TradeCollector functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=CollectionConfig)
        
        # Mock DEX config
        config.dexes = MagicMock(spec=DEXConfig)
        config.dexes.network = "solana"
        
        # Mock threshold config
        config.thresholds = MagicMock(spec=ThresholdConfig)
        config.thresholds.min_trade_volume_usd = 100.0
        
        # Mock error handling config
        config.error_handling = MagicMock()
        config.error_handling.max_retries = 3
        config.error_handling.backoff_factor = 2.0
        config.error_handling.circuit_breaker_threshold = 5
        config.error_handling.circuit_breaker_timeout = 300
        
        # Mock API config
        config.api = MagicMock()
        config.api.timeout = 30
        config.api.max_concurrent = 5
        
        # Trade specific settings
        config.trade_limit = 300
        config.max_trade_age_hours = 24
        
        return config
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = AsyncMock()
        db_manager.get_watchlist_pools.return_value = [
            "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        ]
        db_manager.store_trade_data.return_value = 5
        db_manager.get_trade_data.return_value = []
        return db_manager
    
    @pytest.fixture
    def sample_trade_data(self):
        """Create sample trade data from CSV fixture."""
        return {
            "data": [
                {
                    "id": "solana_363106602_432SvDgRKPzNWyZjZjv8cu8CS3tQtKGSJBCzQW4Ppwz5VYxEM3w1UChE9GYWeovMDwyBzWYX73fXHcwiXjbYuu9N_42_1756397712",
                    "type": "trade",
                    "attributes": {
                        "block_number": 363106602,
                        "tx_hash": "432SvDgRKPzNWyZjZjv8cu8CS3tQtKGSJBCzQW4Ppwz5VYxEM3w1UChE9GYWeovMDwyBzWYX73fXHcwiXjbYuu9N",
                        "tx_from_address": "8qcW84HGYGUF8Jqs2JwJyKRWeMm4ksNo9dVugMz9tUc5",
                        "from_token_amount": "2.505487036",
                        "to_token_amount": "10787911.48458",
                        "price_from_in_usd": "212.618160283895494927350632339277383984859223512",
                        "price_to_in_usd": "0.0000493804611736865774611869570754394294604142126779721093309794408",
                        "block_timestamp": "2025-08-28T16:15:08Z",
                        "kind": "buy",
                        "volume_usd": "532.712044209470242119280771152461839182058804794342390432"
                    }
                },
                {
                    "id": "solana_363105233_5htGYaDNrjcggfohBhYMvA2q3bPNdorPPPM6irPsBvnkXn8QBS1aFtqRbD4gEsoWKDaDYwqwg77yQTXPfmfGX6ko_42_1756397168",
                    "type": "trade",
                    "attributes": {
                        "block_number": 363105233,
                        "tx_hash": "5htGYaDNrjcggfohBhYMvA2q3bPNdorPPPM6irPsBvnkXn8QBS1aFtqRbD4gEsoWKDaDYwqwg77yQTXPfmfGX6ko",
                        "tx_from_address": "49LRMwB8HRiMPmTyrHsfPUTkoxxwhudL4ue2Rk3YT1sX",
                        "from_token_amount": "0.997995006",
                        "to_token_amount": "4475412.982855",
                        "price_from_in_usd": "211.80211874193665632466872600261735212952237173",
                        "price_to_in_usd": "0.000047230827093375367972524251586378905519791491674955847469759436",
                        "block_timestamp": "2025-08-28T16:06:03Z",
                        "kind": "buy",
                        "volume_usd": "211.37745676467178578035770315499446035420679215181558038"
                    }
                },
                {
                    "id": "low_volume_trade",
                    "type": "trade",
                    "attributes": {
                        "block_number": 363100000,
                        "tx_hash": "lowvolumehash",
                        "tx_from_address": "lowvolumeaddress",
                        "from_token_amount": "0.1",
                        "to_token_amount": "100",
                        "price_from_in_usd": "50.0",
                        "price_to_in_usd": "0.05",
                        "block_timestamp": "2025-08-28T15:00:00Z",
                        "kind": "sell",
                        "volume_usd": "5.0"  # Below 100 USD threshold
                    }
                }
            ]
        }
    
    @pytest.fixture
    def trade_collector(self, mock_config, mock_db_manager):
        """Create a TradeCollector instance."""
        return TradeCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
    
    def test_init(self, trade_collector, mock_config):
        """Test TradeCollector initialization."""
        assert trade_collector.network == "solana"
        assert trade_collector.min_trade_volume_usd == 100.0
        assert trade_collector.trade_limit == 300
        assert trade_collector.max_trade_age_hours == 24
        assert trade_collector.get_collection_key() == "trade_collector"
    
    @pytest.mark.asyncio
    async def test_collect_success(self, trade_collector, sample_trade_data):
        """Test successful trade collection."""
        # Mock the client to return sample data
        trade_collector._client = AsyncMock()
        trade_collector._client.get_trades.return_value = sample_trade_data
        
        result = await trade_collector.collect()
        
        assert isinstance(result, CollectionResult)
        assert result.success is True
        assert result.records_collected == 5  # Mocked return value
        assert result.collector_type == "trade_collector"
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_collect_no_watchlist_pools(self, trade_collector):
        """Test collection when no watchlist pools are found."""
        trade_collector.db_manager.get_watchlist_pools.return_value = []
        
        result = await trade_collector.collect()
        
        assert result.success is True
        assert result.records_collected == 0
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_collect_with_errors(self, trade_collector):
        """Test collection with API errors."""
        # Mock client to raise an exception
        trade_collector._client = AsyncMock()
        trade_collector._client.get_trades.side_effect = Exception("API Error")
        
        result = await trade_collector.collect()
        
        assert result.success is True  # Partial success
        assert result.records_collected == 0
        assert len(result.errors) > 0
        assert "API Error" in str(result.errors)
    
    def test_parse_trade_response(self, trade_collector, sample_trade_data):
        """Test parsing trade API response."""
        pool_id = "test_pool"
        records = trade_collector._parse_trade_response(sample_trade_data, pool_id)
        
        assert len(records) == 3  # All trades should be parsed
        
        # Check first trade record
        first_record = records[0]
        assert isinstance(first_record, TradeRecord)
        assert first_record.id == "solana_363106602_432SvDgRKPzNWyZjZjv8cu8CS3tQtKGSJBCzQW4Ppwz5VYxEM3w1UChE9GYWeovMDwyBzWYX73fXHcwiXjbYuu9N_42_1756397712"
        assert first_record.pool_id == pool_id
        assert first_record.block_number == 363106602
        assert first_record.side == "buy"
        assert first_record.volume_usd > Decimal('500')
    
    def test_parse_trade_entry_valid(self, trade_collector):
        """Test parsing a valid trade entry."""
        trade_data = {
            "id": "test_trade_123",
            "type": "trade",
            "attributes": {
                "block_number": 123456,
                "tx_hash": "test_hash",
                "tx_from_address": "test_address",
                "from_token_amount": "1.5",
                "to_token_amount": "1500.0",
                "price_from_in_usd": "100.0",
                "price_to_in_usd": "0.1",
                "block_timestamp": "2025-08-28T12:00:00Z",
                "kind": "buy",
                "volume_usd": "150.0"
            }
        }
        
        record = trade_collector._parse_trade_entry(trade_data, "test_pool")
        
        assert record is not None
        assert record.id == "test_trade_123"
        assert record.pool_id == "test_pool"
        assert record.block_number == 123456
        assert record.tx_hash == "test_hash"
        assert record.from_token_amount == Decimal('1.5')
        assert record.to_token_amount == Decimal('1500.0')
        assert record.price_usd == Decimal('100.0')
        assert record.volume_usd == Decimal('150.0')
        assert record.side == "buy"
        assert isinstance(record.block_timestamp, datetime)
    
    def test_parse_trade_entry_missing_id(self, trade_collector):
        """Test parsing trade entry with missing ID."""
        trade_data = {
            "type": "trade",
            "attributes": {
                "block_number": 123456,
                "tx_hash": "test_hash"
            }
        }
        
        record = trade_collector._parse_trade_entry(trade_data, "test_pool")
        assert record is None
    
    def test_parse_trade_entry_invalid_timestamp(self, trade_collector):
        """Test parsing trade entry with invalid timestamp."""
        trade_data = {
            "id": "test_trade_123",
            "type": "trade",
            "attributes": {
                "block_number": 123456,
                "tx_hash": "test_hash",
                "block_timestamp": "invalid_timestamp"
            }
        }
        
        record = trade_collector._parse_trade_entry(trade_data, "test_pool")
        assert record is None
    
    def test_extract_price_usd(self, trade_collector):
        """Test extracting USD price from attributes."""
        # Test with price_from_in_usd
        attributes = {"price_from_in_usd": "100.50"}
        price = trade_collector._extract_price_usd(attributes)
        assert price == Decimal('100.50')
        
        # Test with price_to_in_usd
        attributes = {"price_to_in_usd": "0.001"}
        price = trade_collector._extract_price_usd(attributes)
        assert price == Decimal('0.001')
        
        # Test with no price fields
        attributes = {}
        price = trade_collector._extract_price_usd(attributes)
        assert price == Decimal('0')
    
    def test_calculate_volume_usd(self, trade_collector):
        """Test calculating USD volume."""
        # Test with direct volume_usd
        attributes = {"volume_usd": "250.75"}
        volume = trade_collector._calculate_volume_usd(
            attributes, Decimal('1'), Decimal('100'), Decimal('2.5')
        )
        assert volume == Decimal('250.75')
        
        # Test calculation from price and amounts
        attributes = {}
        volume = trade_collector._calculate_volume_usd(
            attributes, Decimal('2'), Decimal('200'), Decimal('1.5')
        )
        assert volume == Decimal('300')  # max(2, 200) * 1.5
        
        # Test with zero price
        attributes = {}
        volume = trade_collector._calculate_volume_usd(
            attributes, Decimal('2'), Decimal('200'), Decimal('0')
        )
        assert volume == Decimal('0')
    
    def test_filter_trades_by_volume(self, trade_collector):
        """Test filtering trades by volume threshold."""
        trades = [
            TradeRecord(
                id="high_volume", pool_id="pool1", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('1'),
                price_usd=Decimal('1'), volume_usd=Decimal('150'),  # Above threshold
                side="buy", block_timestamp=datetime.now()
            ),
            TradeRecord(
                id="low_volume", pool_id="pool1", block_number=2, tx_hash="hash2",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('1'),
                price_usd=Decimal('1'), volume_usd=Decimal('50'),  # Below threshold
                side="sell", block_timestamp=datetime.now()
            ),
            TradeRecord(
                id="exact_threshold", pool_id="pool1", block_number=3, tx_hash="hash3",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('1'),
                price_usd=Decimal('1'), volume_usd=Decimal('100'),  # Exact threshold
                side="buy", block_timestamp=datetime.now()
            )
        ]
        
        filtered = trade_collector._filter_trades_by_volume(trades)
        
        assert len(filtered) == 2  # high_volume and exact_threshold
        assert filtered[0].id == "high_volume"
        assert filtered[1].id == "exact_threshold"
    
    @pytest.mark.asyncio
    async def test_validate_trade_data_valid(self, trade_collector):
        """Test validation of valid trade data."""
        trades = [
            TradeRecord(
                id="valid_trade", pool_id="pool1", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('100'),
                price_usd=Decimal('2'), volume_usd=Decimal('200'),
                side="buy", block_timestamp=datetime.now()
            )
        ]
        
        result = await trade_collector._validate_trade_data(trades)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_trade_data_invalid(self, trade_collector):
        """Test validation of invalid trade data."""
        trades = [
            # Trade with missing ID and pool_id
            TradeRecord(
                id="", pool_id="", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('100'),
                price_usd=Decimal('2'), volume_usd=Decimal('200'),
                side="buy", block_timestamp=datetime.now()
            ),
            # Trade with negative values
            TradeRecord(
                id="valid_id", pool_id="valid_pool", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('-1'), to_token_amount=Decimal('100'),  # Negative amount
                price_usd=Decimal('-2'), volume_usd=Decimal('-200'),  # Negative price and volume
                side="invalid_side", block_timestamp=datetime.now()  # Invalid side
            )
        ]
        
        result = await trade_collector._validate_trade_data(trades)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("missing ID" in error for error in result.errors)
        assert any("missing pool ID" in error for error in result.errors)
        assert any("Negative" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_trade_data_duplicates(self, trade_collector):
        """Test validation with duplicate trade IDs."""
        trades = [
            TradeRecord(
                id="duplicate_id", pool_id="pool1", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('100'),
                price_usd=Decimal('2'), volume_usd=Decimal('200'),
                side="buy", block_timestamp=datetime.now()
            ),
            TradeRecord(
                id="duplicate_id", pool_id="pool1", block_number=2, tx_hash="hash2",
                from_token_amount=Decimal('2'), to_token_amount=Decimal('200'),
                price_usd=Decimal('3'), volume_usd=Decimal('300'),
                side="sell", block_timestamp=datetime.now()
            )
        ]
        
        result = await trade_collector._validate_trade_data(trades)
        
        assert result.is_valid is True  # Duplicates are warnings, not errors
        assert len(result.warnings) > 0
        assert any("Duplicate trade ID" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_trade_data_empty(self, trade_collector):
        """Test validation of empty trade data."""
        result = await trade_collector._validate_trade_data([])
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "No trade records to validate" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_get_collection_status(self, trade_collector):
        """Test getting collection status."""
        # Mock some trade data
        trade_collector.db_manager.get_trade_data.return_value = [
            TradeRecord(
                id="test_trade", pool_id="pool1", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('100'),
                price_usd=Decimal('2'), volume_usd=Decimal('200'),
                side="buy", block_timestamp=datetime.now()
            )
        ]
        
        status = await trade_collector.get_collection_status()
        
        assert "total_watchlist_pools" in status
        assert "pools_with_trade_data" in status
        assert "coverage_percentage" in status
        assert "total_recent_records" in status
        assert "min_volume_threshold_usd" in status
        assert status["min_volume_threshold_usd"] == 100.0
    
    @pytest.mark.asyncio
    async def test_verify_data_continuity(self, trade_collector):
        """Test verifying data continuity."""
        # Mock trade data with gaps
        now = datetime.now()
        trades = [
            TradeRecord(
                id="trade1", pool_id="pool1", block_number=1, tx_hash="hash1",
                from_token_amount=Decimal('1'), to_token_amount=Decimal('100'),
                price_usd=Decimal('2'), volume_usd=Decimal('200'),
                side="buy", block_timestamp=now - timedelta(hours=23)
            ),
            TradeRecord(
                id="trade2", pool_id="pool1", block_number=2, tx_hash="hash2",
                from_token_amount=Decimal('2'), to_token_amount=Decimal('200'),
                price_usd=Decimal('3'), volume_usd=Decimal('300'),
                side="sell", block_timestamp=now - timedelta(hours=20)  # 3 hour gap
            )
        ]
        
        trade_collector.db_manager.get_trade_data.return_value = trades
        
        continuity = await trade_collector.verify_data_continuity("pool1")
        
        assert "pool_id" in continuity
        assert "has_trades" in continuity
        assert "trade_count" in continuity
        assert "data_quality_score" in continuity
        assert continuity["pool_id"] == "pool1"
        assert continuity["has_trades"] is True
        assert continuity["trade_count"] == 2
    
    @pytest.mark.asyncio
    async def test_verify_data_continuity_no_trades(self, trade_collector):
        """Test verifying data continuity with no trades."""
        trade_collector.db_manager.get_trade_data.return_value = []
        
        continuity = await trade_collector.verify_data_continuity("pool1")
        
        assert continuity["has_trades"] is False
        assert continuity["trade_count"] == 0
        assert continuity["data_quality"] == "no_data"
    
    @pytest.mark.asyncio
    async def test_collect_pool_trade_data_success(self, trade_collector, sample_trade_data):
        """Test collecting trade data for a specific pool."""
        pool_id = "test_pool"
        
        # Mock the client
        trade_collector._client = AsyncMock()
        trade_collector._client.get_trades.return_value = sample_trade_data
        
        records_count = await trade_collector._collect_pool_trade_data(pool_id)
        
        assert records_count == 5  # Mocked return value from store_trade_data
        trade_collector._client.get_trades.assert_called_once_with(
            network="solana",
            pool_address=pool_id,
            trade_volume_filter=100.0
        )
    
    @pytest.mark.asyncio
    async def test_collect_pool_trade_data_api_error(self, trade_collector):
        """Test collecting trade data with API error."""
        pool_id = "test_pool"
        
        # Mock the client to raise an exception
        trade_collector._client = AsyncMock()
        trade_collector._client.get_trades.side_effect = Exception("API Error")
        
        records_count = await trade_collector._collect_pool_trade_data(pool_id)
        
        assert records_count == 0
        assert len(trade_collector._collection_errors) == 1
        assert "API Error" in trade_collector._collection_errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_pool_trade_data_no_data(self, trade_collector):
        """Test collecting trade data when no data is returned."""
        pool_id = "test_pool"
        
        # Mock the client to return empty data
        trade_collector._client = AsyncMock()
        trade_collector._client.get_trades.return_value = {"data": []}
        
        records_count = await trade_collector._collect_pool_trade_data(pool_id)
        
        assert records_count == 0
    
    def test_parse_trade_response_invalid_format(self, trade_collector):
        """Test parsing trade response with invalid format."""
        invalid_response = {"data": "not_a_list"}
        records = trade_collector._parse_trade_response(invalid_response, "test_pool")
        assert len(records) == 0
    
    def test_parse_trade_response_empty(self, trade_collector):
        """Test parsing empty trade response."""
        empty_response = {"data": []}
        records = trade_collector._parse_trade_response(empty_response, "test_pool")
        assert len(records) == 0
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_no_pools(self, trade_collector):
        """Test specific data validation with no watchlist pools."""
        trade_collector.db_manager.get_watchlist_pools.return_value = []
        
        result = await trade_collector._validate_specific_data(None)
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No active watchlist pools found" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_with_pools(self, trade_collector):
        """Test specific data validation with watchlist pools."""
        # Mock no recent trade data
        trade_collector.db_manager.get_trade_data.return_value = []
        
        result = await trade_collector._validate_specific_data(None)
        
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("No recent trade data" in warning for warning in result.warnings)


class TestTradeCollectorIntegration:
    """Integration tests for TradeCollector using CSV fixture data."""
    
    @pytest.fixture
    def csv_fixture_data(self):
        """Load actual CSV fixture data for testing."""
        csv_file = Path(__file__).parent.parent / "specs" / "get_trades.csv"
        if not csv_file.exists():
            pytest.skip("CSV fixture file not found")
        
        # Read and parse CSV data (simplified for testing)
        trades = []
        with open(csv_file, 'r') as f:
            lines = f.readlines()[1:]  # Skip header
            for line in lines[:10]:  # Use first 10 trades for testing
                parts = line.strip().split(',')
                if len(parts) >= 16:
                    trades.append({
                        "id": parts[0],
                        "type": "trade",
                        "attributes": {
                            "block_number": int(parts[2]) if parts[2].isdigit() else 0,
                            "tx_hash": parts[3],
                            "tx_from_address": parts[4],
                            "from_token_amount": parts[5],
                            "to_token_amount": parts[6],
                            "price_from_in_usd": parts[9],
                            "price_to_in_usd": parts[10],
                            "block_timestamp": parts[11],
                            "kind": parts[12],
                            "volume_usd": parts[13]
                        }
                    })
        
        return {"data": trades}
    
    @pytest.mark.asyncio
    async def test_collect_with_csv_data(self, csv_fixture_data):
        """Test collection using actual CSV fixture data."""
        # Create mock config
        config = MagicMock(spec=CollectionConfig)
        config.dexes = MagicMock(spec=DEXConfig)
        config.dexes.network = "solana"
        config.thresholds = MagicMock(spec=ThresholdConfig)
        config.thresholds.min_trade_volume_usd = 100.0
        config.error_handling = MagicMock()
        config.error_handling.max_retries = 3
        config.error_handling.backoff_factor = 2.0
        config.error_handling.circuit_breaker_threshold = 5
        config.error_handling.circuit_breaker_timeout = 300
        config.api = MagicMock()
        config.api.timeout = 30
        config.api.max_concurrent = 5
        config.trade_limit = 300
        config.max_trade_age_hours = 24
        
        # Create mock database manager
        db_manager = AsyncMock()
        db_manager.get_watchlist_pools.return_value = [
            "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        ]
        db_manager.store_trade_data.return_value = 5
        
        # Create collector
        collector = TradeCollector(config, db_manager, use_mock=True)
        
        # Mock client to return CSV data
        collector._client = AsyncMock()
        collector._client.get_trades.return_value = csv_fixture_data
        
        # Run collection
        result = await collector.collect()
        
        assert result.success is True
        assert result.records_collected > 0
        assert result.collector_type == "trade_collector"
        
        # Verify client was called correctly
        collector._client.get_trades.assert_called_once_with(
            network="solana",
            pool_address="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            trade_volume_filter=100.0
        )
        
        # Verify database storage was called
        db_manager.store_trade_data.assert_called_once()