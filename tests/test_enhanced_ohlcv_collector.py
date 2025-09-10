"""
Comprehensive tests for the enhanced OHLCVCollector with improved error handling,
data quality validation, and bulk storage optimization.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.config.models import CollectionConfig, DEXConfig, TimeframeConfig
from gecko_terminal_collector.models.core import (
    OHLCVRecord, ValidationResult, Gap, ContinuityReport
)


class TestEnhancedOHLCVCollector:
    """Test enhanced OHLCVCollector functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=CollectionConfig)
        
        # Mock DEX config
        config.dexes = MagicMock(spec=DEXConfig)
        config.dexes.network = "solana"
        
        # Mock timeframe config
        config.timeframes = MagicMock(spec=TimeframeConfig)
        config.timeframes.supported = ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
        config.timeframes.ohlcv_default = "1h"
        
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
        
        # OHLCV specific settings
        config.ohlcv_limit = 1000
        config.ohlcv_currency = "usd"
        config.ohlcv_token = "base"
        config.min_data_quality_score = 0.8
        config.max_gap_hours = 24
        
        return config
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = AsyncMock()
        
        # Mock watchlist pools
        db_manager.get_watchlist_pools.return_value = [
            "solana_pool1",
            "solana_pool2"
        ]
        
        # Mock OHLCV data storage
        db_manager.store_ohlcv_data.return_value = 5  # Mock storing 5 records
        
        return db_manager
    
    @pytest.fixture
    def collector(self, mock_config, mock_db_manager):
        """Create an enhanced OHLCVCollector instance."""
        return OHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
    
    @pytest.fixture
    def valid_ohlcv_response(self):
        """Create a valid OHLCV API response."""
        current_timestamp = int(datetime.now().timestamp())
        return {
            "data": {
                "id": "test_pool",
                "type": "ohlcv_request_response",
                "attributes": {
                    "ohlcv_list": [
                        [current_timestamp - 3600, 1.00176903067631, 1.00346106470275, 1.00090364948961, 1.00090364948961, 55810.14196810057],
                        [current_timestamp - 7200, 0.999887867433533, 1.00255640779733, 1.00073526407626, 1.00255640779733, 28732.101368975545],
                        [current_timestamp - 10800, 1.00055348753841, 1.00140375763843, 0.999266505607413, 0.999887867433533, 27440.96699698592]
                    ]
                }
            }
        }
    
    @pytest.fixture
    def invalid_ohlcv_response(self):
        """Create an invalid OHLCV API response for testing error handling."""
        current_timestamp = int(datetime.now().timestamp())
        return {
            "data": {
                "attributes": {
                    "ohlcv_list": [
                        [current_timestamp - 3600, -1.0, 1.1, 0.9, 1.05, 1000.0],  # Negative open price
                        [current_timestamp - 7200, 1.0, 0.8, 1.2, 1.05, -500.0],   # High < Low, negative volume
                        ["invalid", 1.0, 1.1, 0.9, 1.05, 1000.0],    # Invalid timestamp
                        [current_timestamp - 10800, 1.0, 1.1, 0.9],                 # Incomplete data
                    ]
                }
            }
        }
    
    # Test enhanced parsing methods
    
    def test_safe_int_conversion_valid(self, collector):
        """Test safe integer conversion with valid inputs."""
        assert collector._safe_int_conversion(123, "test") == 123
        assert collector._safe_int_conversion("456", "test") == 456
        assert collector._safe_int_conversion(789.0, "test") == 789
        assert collector._safe_int_conversion("123.456", "test") == 123
    
    def test_safe_int_conversion_invalid(self, collector):
        """Test safe integer conversion with invalid inputs."""
        assert collector._safe_int_conversion(None, "test") is None
        assert collector._safe_int_conversion("invalid", "test") is None
        assert collector._safe_int_conversion("", "test") is None
        assert collector._safe_int_conversion(float('inf'), "test") is None
    
    def test_safe_float_conversion_valid(self, collector):
        """Test safe float conversion with valid inputs."""
        assert collector._safe_float_conversion(123.456, "test") == 123.456
        assert collector._safe_float_conversion("789.012", "test") == 789.012
        assert collector._safe_float_conversion(345, "test") == 345.0
    
    def test_safe_float_conversion_invalid(self, collector):
        """Test safe float conversion with invalid inputs."""
        assert collector._safe_float_conversion(None, "test") is None
        assert collector._safe_float_conversion("invalid", "test") is None
        assert collector._safe_float_conversion("", "test") is None
        assert collector._safe_float_conversion(float('inf'), "test") is None
    
    def test_parse_ohlcv_response_valid_dict(self, collector, valid_ohlcv_response):
        """Test parsing valid dictionary OHLCV response."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        records = collector._parse_ohlcv_response(valid_ohlcv_response, pool_id, timeframe)
        
        assert len(records) == 3
        assert all(isinstance(record, OHLCVRecord) for record in records)
        assert all(record.pool_id == pool_id for record in records)
        assert all(record.timeframe == timeframe for record in records)
    
    def test_parse_ohlcv_response_invalid_dict(self, collector, invalid_ohlcv_response):
        """Test parsing invalid dictionary OHLCV response."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        records = collector._parse_ohlcv_response(invalid_ohlcv_response, pool_id, timeframe)
        
        # Should filter out invalid records
        assert len(records) == 0  # All records should be rejected due to validation issues
    
    def test_parse_ohlcv_response_empty_dict(self, collector):
        """Test parsing empty dictionary response."""
        empty_response = {"data": {"attributes": {"ohlcv_list": []}}}
        
        records = collector._parse_ohlcv_response(empty_response, "test_pool", "1h")
        
        assert len(records) == 0
    
    def test_parse_ohlcv_response_malformed_dict(self, collector):
        """Test parsing malformed dictionary response."""
        malformed_responses = [
            {},  # Empty dict
            {"data": {}},  # Missing attributes
            {"data": {"attributes": {}}},  # Missing ohlcv_list
            {"data": {"attributes": {"ohlcv_list": "not_a_list"}}},  # Invalid ohlcv_list type
        ]
        
        for response in malformed_responses:
            records = collector._parse_ohlcv_response(response, "test_pool", "1h")
            assert len(records) == 0
    
    def test_parse_ohlcv_response_dataframe(self, collector):
        """Test parsing pandas DataFrame response."""
        current_timestamp = int(datetime.now().timestamp())
        
        # Mock pandas DataFrame
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume_usd']
        
        # Mock DataFrame rows with proper attribute access
        class MockRow:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            
            def __getitem__(self, key):
                return getattr(self, key)
        
        mock_rows = [
            MockRow(timestamp=current_timestamp - 3600, open=1.0, high=1.1, low=0.9, close=1.05, volume_usd=1000.0),
            MockRow(timestamp=current_timestamp - 7200, open=1.05, high=1.15, low=0.95, close=1.1, volume_usd=1500.0),
        ]
        mock_df.iterrows.return_value = enumerate(mock_rows)
        
        # Mock hasattr to return True for DataFrame detection
        with patch('builtins.hasattr', return_value=True):
            # Mock pandas module and isna function
            with patch.dict('sys.modules', {'pandas': MagicMock()}):
                import sys
                sys.modules['pandas'].isna = MagicMock(return_value=False)
                records = collector._parse_ohlcv_response(mock_df, "test_pool", "1h")
        
        assert len(records) == 2
        assert all(isinstance(record, OHLCVRecord) for record in records)
    
    def test_parse_ohlcv_response_list(self, collector):
        """Test parsing list OHLCV response."""
        current_timestamp = int(datetime.now().timestamp())
        list_response = [
            [current_timestamp - 3600, 1.0, 1.1, 0.9, 1.05, 1000.0],
            [current_timestamp - 7200, 1.05, 1.15, 0.95, 1.1, 1500.0],
        ]
        
        records = collector._parse_ohlcv_response(list_response, "test_pool", "1h")
        
        assert len(records) == 2
        assert all(isinstance(record, OHLCVRecord) for record in records)
    
    def test_parse_ohlcv_response_unsupported_type(self, collector):
        """Test parsing unsupported response type."""
        unsupported_response = "invalid_response_type"
        
        records = collector._parse_ohlcv_response(unsupported_response, "test_pool", "1h")
        
        assert len(records) == 0
    
    # Test enhanced OHLCV entry parsing
    
    def test_parse_ohlcv_entry_valid(self, collector):
        """Test parsing valid OHLCV entry."""
        current_timestamp = int(datetime.now().timestamp())
        ohlcv_data = [current_timestamp, 1.0, 1.1, 0.9, 1.05, 1000.0]
        
        record = collector._parse_ohlcv_entry(ohlcv_data, "test_pool", "1h")
        
        assert record is not None
        assert record.pool_id == "test_pool"
        assert record.timeframe == "1h"
        assert record.timestamp == current_timestamp
        assert record.open_price == Decimal("1.0")
        assert record.high_price == Decimal("1.1")
        assert record.low_price == Decimal("0.9")
        assert record.close_price == Decimal("1.05")
        assert record.volume_usd == Decimal("1000.0")
    
    def test_parse_ohlcv_entry_invalid_format(self, collector):
        """Test parsing OHLCV entry with invalid format."""
        invalid_entries = [
            None,  # None
            "not_a_list",  # String
            [],  # Empty list
            [1, 2, 3],  # Too few elements
            [1, 2, 3, 4, 5],  # Too few elements
        ]
        
        for entry in invalid_entries:
            record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
            assert record is None
    
    def test_parse_ohlcv_entry_invalid_timestamp(self, collector):
        """Test parsing OHLCV entry with invalid timestamp."""
        invalid_timestamps = [
            ["invalid", 1.0, 1.1, 0.9, 1.05, 1000.0],  # String timestamp
            [None, 1.0, 1.1, 0.9, 1.05, 1000.0],       # None timestamp
            [-1, 1.0, 1.1, 0.9, 1.05, 1000.0],         # Negative timestamp
            [0, 1.0, 1.1, 0.9, 1.05, 1000.0],          # Zero timestamp
        ]
        
        for entry in invalid_timestamps:
            record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
            assert record is None
    
    def test_parse_ohlcv_entry_invalid_prices(self, collector):
        """Test parsing OHLCV entry with invalid prices."""
        current_timestamp = int(datetime.now().timestamp())
        invalid_price_entries = [
            [current_timestamp, -1.0, 1.1, 0.9, 1.05, 1000.0],    # Negative open
            [current_timestamp, 1.0, -1.1, 0.9, 1.05, 1000.0],    # Negative high
            [current_timestamp, 1.0, 1.1, -0.9, 1.05, 1000.0],    # Negative low
            [current_timestamp, 1.0, 1.1, 0.9, -1.05, 1000.0],    # Negative close
            [current_timestamp, 0, 1.1, 0.9, 1.05, 1000.0],       # Zero open
            [current_timestamp, 1.0, 0, 0.9, 1.05, 1000.0],       # Zero high
            [current_timestamp, 1.0, 1.1, 0, 1.05, 1000.0],       # Zero low
            [current_timestamp, 1.0, 1.1, 0.9, 0, 1000.0],        # Zero close
        ]
        
        for entry in invalid_price_entries:
            record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
            assert record is None
    
    def test_parse_ohlcv_entry_invalid_volume(self, collector):
        """Test parsing OHLCV entry with invalid volume."""
        current_timestamp = int(datetime.now().timestamp())
        
        # Negative volume should be rejected
        entry = [current_timestamp, 1.0, 1.1, 0.9, 1.05, -1000.0]
        record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
        assert record is None
    
    def test_parse_ohlcv_entry_extreme_values(self, collector):
        """Test parsing OHLCV entry with extreme but valid values."""
        current_timestamp = int(datetime.now().timestamp())
        
        # Very small prices (but positive)
        entry = [current_timestamp, 1e-10, 1.1e-10, 0.9e-10, 1.05e-10, 0.0]
        record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
        assert record is not None  # Should be accepted despite being very small
        
        # Very large prices
        entry = [current_timestamp, 1e6, 1.1e6, 0.9e6, 1.05e6, 1e9]
        record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
        assert record is not None  # Should be accepted
    
    def test_parse_ohlcv_entry_price_relationships(self, collector):
        """Test parsing OHLCV entry with unusual price relationships."""
        current_timestamp = int(datetime.now().timestamp())
        
        # High < Low (unusual but real market data can have this)
        entry = [current_timestamp, 1.0, 0.8, 1.2, 1.05, 1000.0]
        record = collector._parse_ohlcv_entry(entry, "test_pool", "1h")
        assert record is not None  # Should be accepted with warning
    
    # Test enhanced validation
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_valid(self, collector):
        """Test validation of valid OHLCV data."""
        current_time = datetime.now()
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(current_time.timestamp()),
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=current_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_empty(self, collector):
        """Test validation of empty OHLCV data."""
        records = []
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No OHLCV records to validate" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_duplicates(self, collector):
        """Test validation with duplicate timestamps."""
        current_time = datetime.now()
        timestamp = int(current_time.timestamp())
        
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=timestamp,
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=current_time
            ),
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=timestamp,  # Duplicate
                open_price=Decimal("1.05"),
                high_price=Decimal("1.25"),
                low_price=Decimal("0.85"),
                close_price=Decimal("1.15"),
                volume_usd=Decimal("1500.0"),
                datetime=current_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True  # Duplicates are warnings, not errors
        assert len(result.warnings) >= 1
        assert any("Duplicate timestamp" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_future_timestamps(self, collector):
        """Test validation with future timestamps."""
        future_time = datetime.now() + timedelta(hours=3)
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(future_time.timestamp()),
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=future_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True  # Future timestamps are warnings
        assert len(result.warnings) >= 1
        assert any("Future timestamp" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_extreme_values(self, collector):
        """Test validation with extreme values."""
        current_time = datetime.now()
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(current_time.timestamp()),
                open_price=Decimal("1000000"),  # Very high price
                high_price=Decimal("1100000"),
                low_price=Decimal("900000"),
                close_price=Decimal("1050000"),
                volume_usd=Decimal("20000000000"),  # Very high volume (above 10B threshold)
                datetime=current_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True  # Extreme values are warnings
        assert len(result.warnings) >= 2  # Should warn about high price and volume
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_negative_volume(self, collector):
        """Test validation with negative volume."""
        current_time = datetime.now()
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(current_time.timestamp()),
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("-1000.0"),  # Negative volume
                datetime=current_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any("Negative volume" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_unsupported_timeframe(self, collector):
        """Test validation with unsupported timeframe."""
        current_time = datetime.now()
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="2h",  # Unsupported
                timestamp=int(current_time.timestamp()),
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=current_time
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any("Unsupported timeframe" in error for error in result.errors)
    
    # Test helper methods
    
    def test_get_expected_timeframe_seconds(self, collector):
        """Test getting expected seconds for timeframes."""
        assert collector._get_expected_timeframe_seconds("1m") == 60
        assert collector._get_expected_timeframe_seconds("5m") == 300
        assert collector._get_expected_timeframe_seconds("15m") == 900
        assert collector._get_expected_timeframe_seconds("1h") == 3600
        assert collector._get_expected_timeframe_seconds("4h") == 14400
        assert collector._get_expected_timeframe_seconds("12h") == 43200
        assert collector._get_expected_timeframe_seconds("1d") == 86400
        assert collector._get_expected_timeframe_seconds("unknown") is None
    
    def test_is_record_valid(self, collector):
        """Test individual record validation."""
        current_time = datetime.now()
        
        # Valid record
        valid_record = OHLCVRecord(
            pool_id="test_pool",
            timeframe="1h",
            timestamp=int(current_time.timestamp()),
            open_price=Decimal("1.0"),
            high_price=Decimal("1.2"),
            low_price=Decimal("0.8"),
            close_price=Decimal("1.1"),
            volume_usd=Decimal("1000.0"),
            datetime=current_time
        )
        assert collector._is_record_valid(valid_record) is True
        
        # Invalid records
        invalid_records = [
            # Empty pool_id
            OHLCVRecord("", "1h", int(current_time.timestamp()), Decimal("1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.1"), Decimal("1000.0"), current_time),
            # Unsupported timeframe
            OHLCVRecord("test_pool", "2h", int(current_time.timestamp()), Decimal("1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.1"), Decimal("1000.0"), current_time),
            # Invalid timestamp
            OHLCVRecord("test_pool", "1h", 0, Decimal("1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.1"), Decimal("1000.0"), current_time),
            # Negative price
            OHLCVRecord("test_pool", "1h", int(current_time.timestamp()), Decimal("-1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.1"), Decimal("1000.0"), current_time),
            # Negative volume
            OHLCVRecord("test_pool", "1h", int(current_time.timestamp()), Decimal("1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.1"), Decimal("-1000.0"), current_time),
        ]
        
        for record in invalid_records:
            assert collector._is_record_valid(record) is False
    
    # Test bulk storage optimization
    
    @pytest.mark.asyncio
    async def test_bulk_store_ohlcv_data(self, collector, mock_db_manager):
        """Test bulk storage of OHLCV data."""
        current_time = datetime.now()
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=int(current_time.timestamp()) + i,
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=current_time + timedelta(seconds=i)
            )
            for i in range(10)
        ]
        
        mock_db_manager.store_ohlcv_data.return_value = len(records)
        
        stored_count = await collector._bulk_store_ohlcv_data(records)
        
        assert stored_count == len(records)
        mock_db_manager.store_ohlcv_data.assert_called_once()
        
        # Verify records were sorted
        call_args = mock_db_manager.store_ohlcv_data.call_args[0][0]
        timestamps = [r.timestamp for r in call_args]
        assert timestamps == sorted(timestamps)
    
    @pytest.mark.asyncio
    async def test_bulk_store_ohlcv_data_empty(self, collector):
        """Test bulk storage with empty records."""
        stored_count = await collector._bulk_store_ohlcv_data([])
        assert stored_count == 0
    
    # Test integration scenarios
    
    @pytest.mark.asyncio
    async def test_collect_pool_ohlcv_data_success(self, collector, mock_db_manager):
        """Test successful pool OHLCV data collection with bulk storage."""
        # Mock client
        mock_client = AsyncMock()
        mock_response = {
            "data": {
                "attributes": {
                    "ohlcv_list": [
                        [int(datetime.now().timestamp()), 1.0, 1.1, 0.9, 1.05, 1000.0]
                    ]
                }
            }
        }
        mock_client.get_ohlcv_data.return_value = mock_response
        collector._client = mock_client
        
        mock_db_manager.store_ohlcv_data.return_value = 7  # 1 record per timeframe * 7 timeframes
        
        records_count = await collector._collect_pool_ohlcv_data("test_pool")
        
        assert records_count == 7
        assert mock_client.get_ohlcv_data.call_count == len(collector.supported_timeframes)
        mock_db_manager.store_ohlcv_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_pool_ohlcv_data_api_failures(self, collector, mock_db_manager):
        """Test pool OHLCV data collection with API failures."""
        # Mock client with failures
        mock_client = AsyncMock()
        mock_client.get_ohlcv_data.side_effect = Exception("API Error")
        collector._client = mock_client
        
        records_count = await collector._collect_pool_ohlcv_data("test_pool")
        
        assert records_count == 0
        assert len(collector._collection_errors) > 0
        mock_db_manager.store_ohlcv_data.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_collect_pool_ohlcv_data_mixed_results(self, collector, mock_db_manager):
        """Test pool OHLCV data collection with mixed success/failure results."""
        # Reset collection errors
        collector._collection_errors = []
        
        # Mock client with alternating success/failure
        mock_client = AsyncMock()
        
        def side_effect(*args, **kwargs):
            # Fail for some timeframes, succeed for others
            timeframe = kwargs.get('timeframe', '')
            if timeframe in ['1m', '5m']:  # Fail for minute timeframes
                raise Exception("API Error")
            else:
                return {
                    "data": {
                        "attributes": {
                            "ohlcv_list": [
                                [int(datetime.now().timestamp()), 1.0, 1.1, 0.9, 1.05, 1000.0]
                            ]
                        }
                    }
                }
        
        mock_client.get_ohlcv_data.side_effect = side_effect
        collector._client = mock_client
        
        mock_db_manager.store_ohlcv_data.return_value = 4  # Some records stored
        
        records_count = await collector._collect_pool_ohlcv_data("test_pool")
        
        assert records_count == 4
        assert len(collector._collection_errors) > 0  # Should have some errors from API failures
        mock_db_manager.store_ohlcv_data.assert_called_once()