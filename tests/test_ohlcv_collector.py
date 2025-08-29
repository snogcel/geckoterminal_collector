"""
Tests for the OHLCVCollector.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.config.models import CollectionConfig, DEXConfig, TimeframeConfig
from gecko_terminal_collector.models.core import (
    OHLCVRecord, ValidationResult, Gap, ContinuityReport
)


class TestOHLCVCollector:
    """Test OHLCVCollector functionality."""
    
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
        
        # Mock OHLCV data retrieval
        db_manager.get_ohlcv_data.return_value = [
            OHLCVRecord(
                pool_id="solana_pool1",
                timeframe="1h",
                timestamp=1689280200,
                open_price=Decimal("1.00176903067631"),
                high_price=Decimal("1.00346106470275"),
                low_price=Decimal("1.00090364948961"),
                close_price=Decimal("1.00090364948961"),
                volume_usd=Decimal("55810.14196810057"),
                datetime=datetime.fromtimestamp(1689280200)
            )
        ]
        
        # Mock continuity check - return different values based on input
        def mock_continuity_check(pool_id, timeframe):
            return ContinuityReport(
                pool_id=pool_id,
                timeframe=timeframe,
                total_gaps=0,
                gaps=[],
                data_quality_score=1.0
            )
        db_manager.check_data_continuity.side_effect = mock_continuity_check
        
        return db_manager
    
    @pytest.fixture
    def ohlcv_test_data(self):
        """Load OHLCV test data from fixture file."""
        test_data_path = Path("test_data/get_ohlcv.json")
        if test_data_path.exists():
            with open(test_data_path, 'r') as f:
                return json.load(f)
        
        # Fallback mock data if file doesn't exist
        return {
            "data": {
                "id": "test_pool",
                "type": "ohlcv_request_response",
                "attributes": {
                    "ohlcv_list": [
                        [1689280200, 1.00176903067631, 1.00346106470275, 1.00090364948961, 1.00090364948961, 55810.14196810057],
                        [1689279300, 0.999887867433533, 1.00255640779733, 1.00073526407626, 1.00255640779733, 28732.101368975545],
                        [1689278400, 1.00055348753841, 1.00140375763843, 0.999266505607413, 0.999887867433533, 27440.96699698592]
                    ]
                }
            }
        }
    
    @pytest.fixture
    def mock_client(self, ohlcv_test_data):
        """Create a mock API client."""
        client = AsyncMock()
        
        # Mock OHLCV data response
        client.get_ohlcv_data.return_value = ohlcv_test_data
        
        return client
    
    @pytest.fixture
    def collector(self, mock_config, mock_db_manager):
        """Create an OHLCVCollector instance."""
        return OHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
    
    @pytest.mark.asyncio
    async def test_collect_success(self, collector, mock_client):
        """Test successful OHLCV data collection."""
        collector._client = mock_client
        
        result = await collector.collect()
        
        assert result.success is True
        assert result.records_collected > 0
        assert len(result.errors) == 0
        
        # Verify API calls were made for each timeframe
        expected_calls = len(collector.supported_timeframes) * 2  # 2 pools
        assert mock_client.get_ohlcv_data.call_count == expected_calls
    
    @pytest.mark.asyncio
    async def test_collect_no_watchlist_pools(self, collector, mock_db_manager):
        """Test collection when no watchlist pools exist."""
        mock_db_manager.get_watchlist_pools.return_value = []
        
        result = await collector.collect()
        
        assert result.success is True
        assert result.records_collected == 0
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_collect_with_api_errors(self, collector, mock_client):
        """Test collection with API errors for some pools."""
        collector._client = mock_client
        
        # Make API calls fail for some requests
        mock_client.get_ohlcv_data.side_effect = [
            Exception("API Error"),  # First call fails
            mock_client.get_ohlcv_data.return_value,  # Second call succeeds
            Exception("API Error"),  # Third call fails
            mock_client.get_ohlcv_data.return_value,  # Fourth call succeeds
        ] * 10  # Repeat pattern for all timeframes
        
        result = await collector.collect()
        
        # Should still succeed with partial data
        assert result.success is True
        assert len(result.errors) > 0  # Should have some errors logged
    
    def test_parse_ohlcv_response(self, collector, ohlcv_test_data):
        """Test parsing of OHLCV API response."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        records = collector._parse_ohlcv_response(ohlcv_test_data, pool_id, timeframe)
        
        assert len(records) > 0
        
        # Check first record
        first_record = records[0]
        assert first_record.pool_id == pool_id
        assert first_record.timeframe == timeframe
        assert first_record.timestamp == 1689280200
        assert first_record.open_price == Decimal("1.00176903067631")
        assert first_record.high_price == Decimal("1.00346106470275")
        assert first_record.low_price == Decimal("1.00090364948961")
        assert first_record.close_price == Decimal("1.00090364948961")
        assert first_record.volume_usd == Decimal("55810.14196810057")
        assert isinstance(first_record.datetime, datetime)
    
    def test_parse_ohlcv_entry_valid(self, collector):
        """Test parsing of valid OHLCV entry."""
        ohlcv_data = [1689280200, 1.00176903067631, 1.00346106470275, 1.00090364948961, 1.00090364948961, 55810.14196810057]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        assert record is not None
        assert record.pool_id == pool_id
        assert record.timeframe == timeframe
        assert record.timestamp == 1689280200
        assert record.open_price == Decimal("1.00176903067631")
        assert record.high_price == Decimal("1.00346106470275")
        assert record.low_price == Decimal("1.00090364948961")
        assert record.close_price == Decimal("1.00090364948961")
        assert record.volume_usd == Decimal("55810.14196810057")
    
    def test_parse_ohlcv_entry_invalid_format(self, collector):
        """Test parsing of invalid OHLCV entry format."""
        # Too few elements
        ohlcv_data = [1689280200, 1.0, 1.1]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        assert record is None
    
    def test_parse_ohlcv_entry_invalid_prices(self, collector):
        """Test parsing of OHLCV entry with invalid price relationships."""
        # High < Low (invalid) - but we now allow this and just log a warning
        ohlcv_data = [1689280200, 1.0, 0.8, 1.2, 1.0, 1000.0]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        # Should still create a record, just with unusual price relationships
        assert record is not None
        assert record.pool_id == pool_id
        assert record.timeframe == timeframe
    
    def test_validate_price_relationships_valid(self, collector):
        """Test validation of valid price relationships."""
        open_price = Decimal("1.0")
        high_price = Decimal("1.2")
        low_price = Decimal("0.8")
        close_price = Decimal("1.1")
        
        is_valid = collector._validate_price_relationships(open_price, high_price, low_price, close_price)
        
        assert is_valid is True
    
    def test_validate_price_relationships_invalid_high(self, collector):
        """Test validation with invalid high price."""
        open_price = Decimal("1.0")
        high_price = Decimal("0.9")  # High < Open (invalid)
        low_price = Decimal("0.8")
        close_price = Decimal("1.1")
        
        is_valid = collector._validate_price_relationships(open_price, high_price, low_price, close_price)
        
        assert is_valid is False
    
    def test_validate_price_relationships_invalid_low(self, collector):
        """Test validation with invalid low price."""
        open_price = Decimal("1.0")
        high_price = Decimal("1.2")
        low_price = Decimal("1.1")  # Low > Open (invalid)
        close_price = Decimal("1.1")
        
        is_valid = collector._validate_price_relationships(open_price, high_price, low_price, close_price)
        
        assert is_valid is False
    
    def test_validate_price_relationships_negative_prices(self, collector):
        """Test validation with negative prices."""
        open_price = Decimal("-1.0")  # Negative price (invalid)
        high_price = Decimal("1.2")
        low_price = Decimal("0.8")
        close_price = Decimal("1.1")
        
        is_valid = collector._validate_price_relationships(open_price, high_price, low_price, close_price)
        
        assert is_valid is False
    
    def test_convert_timeframe_to_api_format(self, collector):
        """Test conversion of timeframes to API format."""
        assert collector._convert_timeframe_to_api_format("1m") == "minute"
        assert collector._convert_timeframe_to_api_format("5m") == "minute"
        assert collector._convert_timeframe_to_api_format("15m") == "minute"
        assert collector._convert_timeframe_to_api_format("1h") == "hour"
        assert collector._convert_timeframe_to_api_format("4h") == "hour"
        assert collector._convert_timeframe_to_api_format("12h") == "hour"
        assert collector._convert_timeframe_to_api_format("1d") == "day"
        assert collector._convert_timeframe_to_api_format("unknown") == "hour"  # Default
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_valid(self, collector):
        """Test validation of valid OHLCV data."""
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1689280200,
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime.fromtimestamp(1689280200)
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
        timestamp = 1689280200
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
                datetime=datetime.fromtimestamp(timestamp)
            ),
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=timestamp,  # Duplicate timestamp
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime.fromtimestamp(timestamp)
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        # Duplicates are now warnings, not errors
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("Duplicate timestamp" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_negative_volume(self, collector):
        """Test validation with negative volume."""
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1689280200,
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("-1000.0"),  # Negative volume
                datetime=datetime.fromtimestamp(1689280200)
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Negative volume detected" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_unsupported_timeframe(self, collector):
        """Test validation with unsupported timeframe."""
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="2h",  # Unsupported timeframe
                timestamp=1689280200,
                open_price=Decimal("1.0"),
                high_price=Decimal("1.2"),
                low_price=Decimal("0.8"),
                close_price=Decimal("1.1"),
                volume_usd=Decimal("1000.0"),
                datetime=datetime.fromtimestamp(1689280200)
            )
        ]
        
        result = await collector._validate_ohlcv_data(records)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Unsupported timeframe" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_future_timestamp(self, collector):
        """Test validation with future timestamp."""
        future_time = datetime.now() + timedelta(hours=2)
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
        
        assert result.is_valid is True  # Warning, not error
        assert len(result.warnings) == 1
        assert "Future timestamp detected" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_verify_data_continuity(self, collector, mock_db_manager):
        """Test data continuity verification."""
        pool_id = "test_pool"
        
        # Mock continuity report with gaps
        mock_db_manager.check_data_continuity.return_value = ContinuityReport(
            pool_id=pool_id,
            timeframe="1h",
            total_gaps=2,
            gaps=[
                Gap(
                    start_time=datetime.now() - timedelta(hours=2),
                    end_time=datetime.now() - timedelta(hours=1),
                    pool_id=pool_id,
                    timeframe="1h"
                )
            ],
            data_quality_score=0.7  # Below threshold
        )
        
        # Should not raise exception
        await collector._verify_data_continuity(pool_id)
        
        # Verify continuity check was called for each timeframe
        expected_calls = len(collector.supported_timeframes)
        assert mock_db_manager.check_data_continuity.call_count == expected_calls
    
    @pytest.mark.asyncio
    async def test_validate_specific_data(self, collector, mock_db_manager):
        """Test specific data validation."""
        # Mock empty OHLCV data to trigger warnings
        mock_db_manager.get_ohlcv_data.return_value = []
        
        result = await collector._validate_specific_data(None)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        # Should have warnings about missing recent data
        assert len(result.warnings) > 0
    
    @pytest.mark.asyncio
    async def test_get_collection_status(self, collector, mock_db_manager):
        """Test getting collection status."""
        status = await collector.get_collection_status()
        
        assert "total_watchlist_pools" in status
        assert "supported_timeframes" in status
        assert "timeframe_coverage" in status
        assert "total_recent_records" in status
        assert "default_timeframe" in status
        
        assert status["total_watchlist_pools"] == 2
        assert status["supported_timeframes"] == collector.supported_timeframes
        assert status["default_timeframe"] == collector.default_timeframe
    
    @pytest.mark.asyncio
    async def test_detect_and_report_gaps(self, collector, mock_db_manager):
        """Test gap detection and reporting."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        report = await collector.detect_and_report_gaps(pool_id, timeframe)
        
        assert isinstance(report, ContinuityReport)
        assert report.pool_id == pool_id
        assert report.timeframe == timeframe
        
        # Verify database method was called
        mock_db_manager.check_data_continuity.assert_called_with(pool_id, timeframe)
    
    @pytest.mark.asyncio
    async def test_backfill_gaps(self, collector, mock_client, ohlcv_test_data):
        """Test gap backfilling functionality."""
        collector._client = mock_client
        
        pool_id = "test_pool"
        timeframe = "1h"
        gaps = [
            Gap(
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() - timedelta(hours=1),
                pool_id=pool_id,
                timeframe=timeframe
            )
        ]
        
        backfilled_count = await collector.backfill_gaps(pool_id, timeframe, gaps)
        
        assert backfilled_count >= 0
        
        # Verify API call was made with before_timestamp
        mock_client.get_ohlcv_data.assert_called()
        call_args = mock_client.get_ohlcv_data.call_args
        assert "before_timestamp" in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_collect_pool_ohlcv_data(self, collector, mock_client):
        """Test collecting OHLCV data for a specific pool."""
        collector._client = mock_client
        
        pool_id = "test_pool"
        
        records_count = await collector._collect_pool_ohlcv_data(pool_id)
        
        assert records_count > 0
        
        # Verify API calls were made for each timeframe
        expected_calls = len(collector.supported_timeframes)
        assert mock_client.get_ohlcv_data.call_count == expected_calls
    
    def test_get_collection_key(self, collector):
        """Test getting collection key."""
        key = collector.get_collection_key()
        assert key == "ohlcv_collector"
    
    def test_parse_ohlcv_response_invalid_structure(self, collector):
        """Test parsing OHLCV response with invalid structure."""
        invalid_response = {
            "data": {
                "attributes": {
                    "ohlcv_list": "invalid_structure"  # Should be list
                }
            }
        }
        
        records = collector._parse_ohlcv_response(invalid_response, "test_pool", "1h")
        
        assert len(records) == 0
    
    def test_parse_ohlcv_response_missing_data(self, collector):
        """Test parsing OHLCV response with missing data."""
        empty_response = {}
        
        records = collector._parse_ohlcv_response(empty_response, "test_pool", "1h")
        
        assert len(records) == 0
    
    @pytest.mark.asyncio
    async def test_collect_with_all_supported_timeframes(self, collector, mock_client, ohlcv_test_data):
        """Test collection with all supported timeframes."""
        collector._client = mock_client
        
        # Test that all timeframes are processed
        result = await collector.collect()
        
        assert result.success is True
        
        # Verify API was called for each timeframe and each pool
        expected_calls = len(collector.supported_timeframes) * 2  # 2 pools
        assert mock_client.get_ohlcv_data.call_count == expected_calls
        
        # Verify different timeframe formats were used
        call_args_list = mock_client.get_ohlcv_data.call_args_list
        timeframe_args = [call.kwargs.get('timeframe') for call in call_args_list]
        
        # Should have minute, hour, and day timeframes
        assert 'minute' in timeframe_args
        assert 'hour' in timeframe_args
        assert 'day' in timeframe_args
    
    @pytest.mark.asyncio
    async def test_parse_ohlcv_entry_with_string_values(self, collector):
        """Test parsing OHLCV entry with string numeric values."""
        ohlcv_data = ["1689280200", "1.00176903067631", "1.00346106470275", "1.00090364948961", "1.00090364948961", "55810.14196810057"]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        assert record is not None
        assert record.timestamp == 1689280200
        assert record.open_price == Decimal("1.00176903067631")
    
    @pytest.mark.asyncio
    async def test_parse_ohlcv_entry_with_invalid_numeric_values(self, collector):
        """Test parsing OHLCV entry with invalid numeric values."""
        ohlcv_data = [1689280200, "invalid", 1.00346106470275, 1.00090364948961, 1.00090364948961, 55810.14196810057]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        assert record is None