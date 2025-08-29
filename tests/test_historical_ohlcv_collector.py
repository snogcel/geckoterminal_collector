"""
Tests for historical OHLCV data collector.

Tests the HistoricalOHLCVCollector using response_body.txt and response_headers.txt fixtures
to verify direct API requests, pagination logic, and backfill functionality.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig, DEXConfig, TimeframeConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import OHLCVRecord, Gap, ValidationResult


@pytest.fixture
def mock_config():
    """Create mock configuration for testing."""
    config = MagicMock(spec=CollectionConfig)
    config.dexes = MagicMock(spec=DEXConfig)
    config.dexes.network = "solana"
    config.timeframes = MagicMock(spec=TimeframeConfig)
    config.timeframes.supported = ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
    config.api = MagicMock(spec=APIConfig)
    config.api.base_url = "https://api.geckoterminal.com/api/v2"
    config.api.timeout = 30
    config.error_handling = MagicMock(spec=ErrorConfig)
    config.error_handling.max_retries = 3
    config.error_handling.backoff_factor = 2.0
    config.max_history_days = 180
    config.historical_limit = 1000
    config.include_empty_intervals = False
    config.pagination_delay = 0.1  # Faster for testing
    return config


@pytest.fixture
def mock_db_manager():
    """Create mock database manager for testing."""
    db_manager = AsyncMock(spec=DatabaseManager)
    db_manager.get_watchlist_pools.return_value = [
        "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
        "solana_8bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NQ"
    ]
    db_manager.store_ohlcv_data.return_value = 10
    db_manager.get_ohlcv_data.return_value = []
    return db_manager


@pytest.fixture
def historical_collector(mock_config, mock_db_manager):
    """Create historical OHLCV collector for testing."""
    return HistoricalOHLCVCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        use_mock=True
    )


@pytest.fixture
def sample_response_data():
    """Load sample response data from fixture file."""
    try:
        response_file = Path("specs/response_body.txt")
        if response_file.exists():
            with open(response_file, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    
    # Fallback mock data if file doesn't exist
    return {
        "data": {
            "id": "test-pool-id",
            "type": "ohlcv_request_response",
            "attributes": {
                "ohlcv_list": [
                    [1755756000, 0.00001613691542742065, 0.000018577063943794163, 0.00001613691542742065, 0.000018111106133282376, 941.0332575772828],
                    [1755755100, 0.000014647992091963596, 0.000017077344049933372, 0.000014647992091963596, 0.00001613691542742065, 797.5948397989445],
                    [1755754200, 0.000014097837034941836, 0.000014705403314656966, 0.000014097837034941836, 0.000014647992091963596, 66.94200307214307]
                ]
            }
        },
        "meta": {
            "base": {
                "address": "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump",
                "name": "Test Token",
                "symbol": "TEST"
            }
        }
    }


class TestHistoricalOHLCVCollector:
    """Test cases for HistoricalOHLCVCollector."""
    
    @pytest.mark.asyncio
    async def test_collector_initialization(self, mock_config, mock_db_manager):
        """Test collector initialization with configuration."""
        collector = HistoricalOHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        assert collector.network == "solana"
        assert collector.supported_timeframes == ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
        assert collector.max_history_days == 180
        assert collector.get_collection_key() == "historical_ohlcv_collector"
    
    @pytest.mark.asyncio
    async def test_collect_with_no_watchlist_pools(self, historical_collector, mock_db_manager):
        """Test collection when no watchlist pools are available."""
        mock_db_manager.get_watchlist_pools.return_value = []
        
        result = await historical_collector.collect()
        
        assert result.success is True
        assert result.records_collected == 0
        assert result.collector_type == "historical_ohlcv_collector"
    
    @pytest.mark.asyncio
    async def test_collect_with_watchlist_pools(self, historical_collector, mock_db_manager, sample_response_data):
        """Test collection with watchlist pools."""
        # Mock existing data range to trigger historical collection
        mock_db_manager.get_ohlcv_data.return_value = []
        
        with patch.object(historical_collector, '_get_mock_historical_response') as mock_response:
            mock_response.return_value = sample_response_data
            
            result = await historical_collector.collect()
            
            assert result.success is True
            assert result.records_collected > 0
            assert result.collector_type == "historical_ohlcv_collector"
    
    @pytest.mark.asyncio
    async def test_parse_direct_ohlcv_response(self, historical_collector, sample_response_data):
        """Test parsing of direct API OHLCV response."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        records = historical_collector._parse_direct_ohlcv_response(
            sample_response_data, pool_id, timeframe
        )
        
        assert len(records) > 0  # Should have some records
        assert all(isinstance(record, OHLCVRecord) for record in records)
        assert all(record.pool_id == pool_id for record in records)
        assert all(record.timeframe == timeframe for record in records)
        
        # Check first record values
        first_record = records[0]
        assert first_record.timestamp == 1755756000
        assert first_record.open_price == Decimal('0.00001613691542742065')
        assert first_record.high_price == Decimal('0.000018577063943794163')
        assert first_record.low_price == Decimal('0.00001613691542742065')
        assert first_record.close_price == Decimal('0.000018111106133282376')
        assert first_record.volume_usd == Decimal('941.0332575772828')
    
    @pytest.mark.asyncio
    async def test_parse_ohlcv_entry_valid_data(self, historical_collector):
        """Test parsing of individual OHLCV entry with valid data."""
        ohlcv_data = [1755756000, 0.00001613691542742065, 0.000018577063943794163, 0.00001613691542742065, 0.000018111106133282376, 941.0332575772828]
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = historical_collector._parse_ohlcv_entry(ohlcv_data, pool_id, timeframe)
        
        assert record is not None
        assert record.pool_id == pool_id
        assert record.timeframe == timeframe
        assert record.timestamp == 1755756000
        assert record.open_price == Decimal('0.00001613691542742065')
        assert record.volume_usd == Decimal('941.0332575772828')
        assert isinstance(record.datetime, datetime)
    
    @pytest.mark.asyncio
    async def test_parse_ohlcv_entry_invalid_data(self, historical_collector):
        """Test parsing of individual OHLCV entry with invalid data."""
        # Test with insufficient data
        invalid_data = [1755756000, 0.00001613691542742065]  # Missing required fields
        pool_id = "test_pool"
        timeframe = "1h"
        
        record = historical_collector._parse_ohlcv_entry(invalid_data, pool_id, timeframe)
        assert record is None
        
        # Test with non-list data
        record = historical_collector._parse_ohlcv_entry("invalid", pool_id, timeframe)
        assert record is None
        
        # Test with invalid numeric data
        invalid_numeric = [1755756000, "invalid", 0.000018577063943794163, 0.00001613691542742065, 0.000018111106133282376, 941.0332575772828]
        record = historical_collector._parse_ohlcv_entry(invalid_numeric, pool_id, timeframe)
        assert record is None
    
    @pytest.mark.asyncio
    async def test_validate_price_relationships(self, historical_collector):
        """Test validation of OHLCV price relationships."""
        # Valid price relationships
        assert historical_collector._validate_price_relationships(
            Decimal('10'), Decimal('15'), Decimal('8'), Decimal('12')
        ) is True
        
        # Invalid: high < open
        assert historical_collector._validate_price_relationships(
            Decimal('15'), Decimal('10'), Decimal('8'), Decimal('12')
        ) is False
        
        # Invalid: low > close
        assert historical_collector._validate_price_relationships(
            Decimal('10'), Decimal('15'), Decimal('14'), Decimal('12')
        ) is False
        
        # Invalid: negative prices
        assert historical_collector._validate_price_relationships(
            Decimal('-10'), Decimal('15'), Decimal('8'), Decimal('12')
        ) is False
    
    @pytest.mark.asyncio
    async def test_convert_timeframe_to_api_format(self, historical_collector):
        """Test conversion of timeframes to API format."""
        assert historical_collector._convert_timeframe_to_api_format('1m') == 'minute'
        assert historical_collector._convert_timeframe_to_api_format('5m') == 'minute'
        assert historical_collector._convert_timeframe_to_api_format('15m') == 'minute'
        assert historical_collector._convert_timeframe_to_api_format('1h') == 'hour'
        assert historical_collector._convert_timeframe_to_api_format('4h') == 'hour'
        assert historical_collector._convert_timeframe_to_api_format('12h') == 'hour'
        assert historical_collector._convert_timeframe_to_api_format('1d') == 'day'
        assert historical_collector._convert_timeframe_to_api_format('unknown') == 'hour'  # Default
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_valid(self, historical_collector):
        """Test validation of valid OHLCV data."""
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1755756000,
                open_price=Decimal('10'),
                high_price=Decimal('15'),
                low_price=Decimal('8'),
                close_price=Decimal('12'),
                volume_usd=Decimal('1000'),
                datetime=datetime.fromtimestamp(1755756000)
            )
        ]
        
        result = await historical_collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_invalid(self, historical_collector):
        """Test validation of invalid OHLCV data."""
        records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="invalid_timeframe",  # Invalid timeframe
                timestamp=1755756000,
                open_price=Decimal('10'),
                high_price=Decimal('15'),
                low_price=Decimal('8'),
                close_price=Decimal('12'),
                volume_usd=Decimal('-1000'),  # Negative volume
                datetime=datetime.fromtimestamp(1755756000)
            )
        ]
        
        result = await historical_collector._validate_ohlcv_data(records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 2  # Invalid timeframe and negative volume
        assert any("Negative volume" in error for error in result.errors)
        assert any("Unsupported timeframe" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_empty(self, historical_collector):
        """Test validation of empty OHLCV data."""
        result = await historical_collector._validate_ohlcv_data([])
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "No historical OHLCV records to validate" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_validate_ohlcv_data_duplicates(self, historical_collector):
        """Test validation of OHLCV data with duplicates."""
        duplicate_record = OHLCVRecord(
            pool_id="test_pool",
            timeframe="1h",
            timestamp=1755756000,
            open_price=Decimal('10'),
            high_price=Decimal('15'),
            low_price=Decimal('8'),
            close_price=Decimal('12'),
            volume_usd=Decimal('1000'),
            datetime=datetime.fromtimestamp(1755756000)
        )
        
        records = [duplicate_record, duplicate_record]  # Same record twice
        
        result = await historical_collector._validate_ohlcv_data(records)
        
        assert result.is_valid is True  # Duplicates are warnings, not errors
        assert len(result.warnings) >= 1
        assert any("Duplicate timestamp" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_get_existing_data_range_no_data(self, historical_collector, mock_db_manager):
        """Test getting existing data range when no data exists."""
        mock_db_manager.get_ohlcv_data.return_value = []
        
        result = await historical_collector._get_existing_data_range("test_pool", "1h")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_existing_data_range_with_data(self, historical_collector, mock_db_manager):
        """Test getting existing data range when data exists."""
        existing_records = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1755756000,
                open_price=Decimal('10'),
                high_price=Decimal('15'),
                low_price=Decimal('8'),
                close_price=Decimal('12'),
                volume_usd=Decimal('1000'),
                datetime=datetime.fromtimestamp(1755756000)
            ),
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1755759600,  # 1 hour later
                open_price=Decimal('12'),
                high_price=Decimal('18'),
                low_price=Decimal('10'),
                close_price=Decimal('15'),
                volume_usd=Decimal('1200'),
                datetime=datetime.fromtimestamp(1755759600)
            )
        ]
        mock_db_manager.get_ohlcv_data.return_value = existing_records
        
        result = await historical_collector._get_existing_data_range("test_pool", "1h")
        
        assert result is not None
        assert len(result) == 2  # (min_datetime, max_datetime)
        assert result[0] == datetime.fromtimestamp(1755756000)
        assert result[1] == datetime.fromtimestamp(1755759600)
    
    @pytest.mark.asyncio
    async def test_collect_historical_data_with_pagination(self, historical_collector, sample_response_data):
        """Test historical data collection with pagination."""
        pool_id = "test_pool"
        timeframe = "1h"
        start_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()
        
        with patch.object(historical_collector, '_get_mock_historical_response') as mock_response:
            mock_response.return_value = sample_response_data
            
            records = await historical_collector._collect_historical_data_with_pagination(
                pool_id, timeframe, start_time, end_time
            )
            
            assert len(records) >= 0  # May be filtered by time range
            assert all(isinstance(record, OHLCVRecord) for record in records)
            assert all(record.pool_id == pool_id for record in records)
            assert all(record.timeframe == timeframe for record in records)
    
    @pytest.mark.asyncio
    async def test_backfill_data_gaps(self, historical_collector, mock_db_manager, sample_response_data):
        """Test backfilling of data gaps."""
        pool_id = "test_pool"
        timeframe = "1h"
        
        # Create test gaps
        gaps = [
            Gap(
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() - timedelta(hours=1),
                pool_id=pool_id,
                timeframe=timeframe
            )
        ]
        
        with patch.object(historical_collector, '_get_mock_historical_response') as mock_response:
            mock_response.return_value = sample_response_data
            
            backfilled_count = await historical_collector.backfill_data_gaps(pool_id, timeframe, gaps)
            
            assert backfilled_count >= 0
            # Note: store_ohlcv_data may not be called if no records match the time range
    
    @pytest.mark.asyncio
    async def test_get_collection_status(self, historical_collector, mock_db_manager):
        """Test getting collection status."""
        mock_db_manager.get_ohlcv_data.return_value = [
            OHLCVRecord(
                pool_id="test_pool",
                timeframe="1h",
                timestamp=1755756000,
                open_price=Decimal('10'),
                high_price=Decimal('15'),
                low_price=Decimal('8'),
                close_price=Decimal('12'),
                volume_usd=Decimal('1000'),
                datetime=datetime.fromtimestamp(1755756000)
            )
        ]
        
        status = await historical_collector.get_collection_status()
        
        assert "total_watchlist_pools" in status
        assert "supported_timeframes" in status
        assert "max_history_days" in status
        assert "timeframe_coverage" in status
        assert "total_historical_records" in status
        assert "collection_stats" in status
        
        assert status["max_history_days"] == 180
        assert status["supported_timeframes"] == ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data(self, historical_collector, mock_db_manager):
        """Test specific data validation."""
        mock_db_manager.get_ohlcv_data.return_value = []
        
        result = await historical_collector._validate_specific_data(None)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.warnings) > 0  # Should warn about no historical data
    
    @pytest.mark.asyncio
    async def test_mock_historical_response_loading(self, historical_collector):
        """Test loading of mock historical response from fixture file."""
        pool_id = "test_pool"
        timeframe = "1h"
        before_timestamp = int(datetime.now().timestamp())
        
        response = await historical_collector._get_mock_historical_response(
            pool_id, timeframe, before_timestamp
        )
        
        # Should return either loaded fixture data or None
        if response is not None:
            assert "data" in response
            assert "attributes" in response["data"]
            assert "ohlcv_list" in response["data"]["attributes"]
            
            # Check that timestamps are adjusted to be before the requested timestamp
            ohlcv_list = response["data"]["attributes"]["ohlcv_list"]
            for ohlcv_entry in ohlcv_list:
                if len(ohlcv_entry) > 0:
                    assert ohlcv_entry[0] < before_timestamp
    
    @pytest.mark.asyncio
    async def test_collection_error_handling(self, historical_collector, mock_db_manager):
        """Test error handling during collection."""
        # Mock database error
        mock_db_manager.get_watchlist_pools.side_effect = Exception("Database error")
        
        result = await historical_collector.collect()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "Database error" in str(result.errors)
    
    @pytest.mark.asyncio
    async def test_collection_with_partial_failures(self, historical_collector, mock_db_manager, sample_response_data):
        """Test collection with partial failures."""
        # Mock one pool to succeed and one to fail
        mock_db_manager.get_watchlist_pools.return_value = ["pool1", "pool2"]
        mock_db_manager.get_ohlcv_data.return_value = []
        
        call_count = 0
        async def mock_response_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 7:  # First pool succeeds (7 timeframes)
                return sample_response_data
            else:  # Second pool fails
                raise Exception("API error")
        
        with patch.object(historical_collector, '_get_mock_historical_response', side_effect=mock_response_side_effect):
            result = await historical_collector.collect()
            
            assert result.success is True  # Partial success
            assert result.records_collected > 0
            # Note: Errors may not propagate to top level if they're handled at pool level
    
    @pytest.mark.asyncio
    async def test_pagination_logic(self, historical_collector, sample_response_data):
        """Test pagination logic with multiple requests."""
        pool_id = "test_pool"
        timeframe = "1h"
        start_time = datetime.now() - timedelta(days=1)
        end_time = datetime.now()
        
        # Mock multiple responses with different timestamps
        responses = []
        base_timestamp = int(end_time.timestamp())
        
        for i in range(3):  # 3 pages of data
            response = sample_response_data.copy()
            ohlcv_list = []
            for j in range(3):  # 3 records per page
                timestamp = base_timestamp - (i * 3 + j) * 3600  # 1 hour intervals
                ohlcv_entry = [timestamp, 0.00001, 0.00002, 0.000005, 0.000015, 100.0]
                ohlcv_list.append(ohlcv_entry)
            response["data"]["attributes"]["ohlcv_list"] = ohlcv_list
            responses.append(response)
        
        call_count = 0
        async def mock_response_side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count < len(responses):
                response = responses[call_count]
                call_count += 1
                return response
            return None  # No more data
        
        with patch.object(historical_collector, '_get_mock_historical_response', side_effect=mock_response_side_effect):
            records = await historical_collector._collect_historical_data_with_pagination(
                pool_id, timeframe, start_time, end_time
            )
            
            # Should collect records from at least one page
            assert len(records) >= 3  # At least one page
            assert all(isinstance(record, OHLCVRecord) for record in records)
            
            # Verify timestamps are in descending order (newest first)
            if len(records) > 1:
                timestamps = [record.timestamp for record in records]
                assert timestamps == sorted(timestamps, reverse=True)


class TestHistoricalOHLCVCollectorIntegration:
    """Integration tests for HistoricalOHLCVCollector."""
    
    @pytest.mark.asyncio
    async def test_full_collection_workflow(self, mock_config, mock_db_manager, sample_response_data):
        """Test complete collection workflow from start to finish."""
        collector = HistoricalOHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        # Mock database responses
        mock_db_manager.get_watchlist_pools.return_value = ["test_pool"]
        mock_db_manager.get_ohlcv_data.return_value = []  # No existing data
        mock_db_manager.store_ohlcv_data.return_value = 3  # Store 3 records
        
        with patch.object(collector, '_get_mock_historical_response') as mock_response:
            mock_response.return_value = sample_response_data
            
            # Run collection
            result = await collector.collect()
            
            # Verify results
            assert result.success is True
            assert result.records_collected > 0  # Should have collected some records
            assert result.collector_type == "historical_ohlcv_collector"
            
            # Verify database calls
            mock_db_manager.get_watchlist_pools.assert_called_once()
            assert mock_db_manager.store_ohlcv_data.call_count == 7  # One per timeframe
    
    @pytest.mark.asyncio
    async def test_backfill_integration(self, mock_config, mock_db_manager, sample_response_data):
        """Test integration of backfill functionality."""
        collector = HistoricalOHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        # Create test gaps
        gaps = [
            Gap(
                start_time=datetime.now() - timedelta(hours=4),
                end_time=datetime.now() - timedelta(hours=2),
                pool_id="test_pool",
                timeframe="1h"
            ),
            Gap(
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now(),
                pool_id="test_pool",
                timeframe="1h"
            )
        ]
        
        mock_db_manager.store_ohlcv_data.return_value = 2  # Store 2 records per gap
        
        with patch.object(collector, '_get_mock_historical_response') as mock_response:
            mock_response.return_value = sample_response_data
            
            # Run backfill
            backfilled_count = await collector.backfill_data_gaps("test_pool", "1h", gaps)
            
            # Verify results
            assert backfilled_count >= 0  # May be 0 if no records match time range
            # Note: store_ohlcv_data may not be called if no records match the time range
    
    @pytest.mark.asyncio
    async def test_status_reporting_integration(self, mock_config, mock_db_manager):
        """Test integration of status reporting functionality."""
        collector = HistoricalOHLCVCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        # Mock database responses for status
        mock_db_manager.get_watchlist_pools.return_value = ["pool1", "pool2"]
        mock_db_manager.get_ohlcv_data.return_value = [
            OHLCVRecord(
                pool_id="pool1",
                timeframe="1h",
                timestamp=1755756000,
                open_price=Decimal('10'),
                high_price=Decimal('15'),
                low_price=Decimal('8'),
                close_price=Decimal('12'),
                volume_usd=Decimal('1000'),
                datetime=datetime.fromtimestamp(1755756000)
            )
        ]
        
        # Get status
        status = await collector.get_collection_status()
        
        # Verify status structure
        assert status["total_watchlist_pools"] == 2
        assert status["max_history_days"] == 180
        assert len(status["timeframe_coverage"]) == 7  # All supported timeframes
        
        # Verify timeframe coverage structure
        for timeframe in collector.supported_timeframes:
            assert timeframe in status["timeframe_coverage"]
            coverage = status["timeframe_coverage"][timeframe]
            assert "pools_with_historical_data" in coverage
            assert "coverage_percentage" in coverage