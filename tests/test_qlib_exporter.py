"""
Tests for QLib data export functionality.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json
from typing import List

from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.qlib.utils import (
    QLibDataValidator, 
    QLibSymbolManager,
    QLibDataProcessor
)
from gecko_terminal_collector.models.core import (
    Pool, Token, OHLCVRecord, ContinuityReport, Gap
)


class TestQLibExporter:
    """Test cases for QLibExporter class."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        return AsyncMock()
    
    @pytest.fixture
    def qlib_exporter(self, mock_db_manager):
        """Create QLibExporter instance with mock database."""
        return QLibExporter(mock_db_manager)
    
    @pytest.fixture
    def sample_pool(self):
        """Create sample pool for testing."""
        return Pool(
            id="solana_test_pool_123",
            address="test_address_123",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="base_token_123",
            quote_token_id="quote_token_456",
            reserve_usd=Decimal("100000.50"),
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_ohlcv_records(self):
        """Create sample OHLCV records for testing."""
        base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        records = []
        
        for i in range(24):  # 24 hours of data
            record = OHLCVRecord(
                pool_id="solana_test_pool_123",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=i)).timestamp()),
                open_price=Decimal(f"{100 + i}"),
                high_price=Decimal(f"{105 + i}"),
                low_price=Decimal(f"{95 + i}"),
                close_price=Decimal(f"{102 + i}"),
                volume_usd=Decimal(f"{1000 + i * 10}"),
                datetime=base_time + timedelta(hours=i)
            )
            records.append(record)
        
        return records
    
    @pytest.mark.asyncio
    async def test_get_symbol_list_active_only(self, qlib_exporter, mock_db_manager, sample_pool):
        """Test getting symbol list for active watchlist only."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        
        # Test
        symbols = await qlib_exporter.get_symbol_list(active_only=True)
        
        # Assertions
        assert len(symbols) == 1
        assert symbols[0] == "HEAVEN_TEST_POOL_123"
        mock_db_manager.get_watchlist_pools.assert_called_once()
        mock_db_manager.get_pool.assert_called_once_with("solana_test_pool_123")
    
    @pytest.mark.asyncio
    async def test_get_symbol_list_with_dex_filter(self, qlib_exporter, mock_db_manager, sample_pool):
        """Test getting symbol list with DEX filter."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        
        # Test with matching DEX
        symbols = await qlib_exporter.get_symbol_list(dex_filter=["heaven"], active_only=True)
        assert len(symbols) == 1
        
        # Test with non-matching DEX
        symbols = await qlib_exporter.get_symbol_list(dex_filter=["pumpswap"], active_only=True)
        assert len(symbols) == 0
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test exporting OHLCV data."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Pre-populate the cache to simulate the symbol being found
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        df = await qlib_exporter.export_ohlcv_data(
            symbols=["HEAVEN_TEST_POOL_123"],
            timeframe="1h"
        )
        
        # Assertions
        assert not df.empty
        assert len(df) == 24
        assert list(df.columns) == ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume']
        assert df['symbol'].iloc[0] == "HEAVEN_TEST_POOL_123"
        assert df['open'].iloc[0] == 100.0
        assert df['high'].iloc[0] == 105.0
        assert df['low'].iloc[0] == 95.0
        assert df['close'].iloc[0] == 102.0
        assert df['volume'].iloc[0] == 1000.0
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_without_volume(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test exporting OHLCV data without volume."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Pre-populate the cache to simulate the symbol being found
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        df = await qlib_exporter.export_ohlcv_data(
            symbols=["HEAVEN_TEST_POOL_123"],
            timeframe="1h",
            include_volume=False
        )
        
        # Assertions
        assert not df.empty
        assert 'volume' not in df.columns
        assert list(df.columns) == ['datetime', 'symbol', 'open', 'high', 'low', 'close']
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_with_date_range(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test exporting OHLCV data with date range."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow()
        
        # Pre-populate the cache to simulate the symbol being found
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        df = await qlib_exporter.export_ohlcv_data(
            symbols=["HEAVEN_TEST_POOL_123"],
            start_date=start_date,
            end_date=end_date,
            timeframe="1h"
        )
        
        # Assertions
        mock_db_manager.get_ohlcv_data.assert_called_once_with(
            pool_id="solana_test_pool_123",
            timeframe="1h",
            start_time=start_date,
            end_time=end_date
        )
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_with_timezone_normalization(self, qlib_exporter, mock_db_manager, sample_pool):
        """Test OHLCV data export with timezone normalization."""
        # Create sample data with timezone-aware timestamps
        base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        timezone_records = []
        
        for i in range(5):
            record = OHLCVRecord(
                pool_id="solana_test_pool_123",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=i)).timestamp()),
                open_price=Decimal(f"{100 + i}"),
                high_price=Decimal(f"{105 + i}"),
                low_price=Decimal(f"{95 + i}"),
                close_price=Decimal(f"{102 + i}"),
                volume_usd=Decimal(f"{1000 + i * 10}"),
                datetime=base_time + timedelta(hours=i)
            )
            timezone_records.append(record)
        
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = timezone_records
        
        # Pre-populate the cache
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test with timezone normalization
        df = await qlib_exporter.export_ohlcv_data(
            symbols=["HEAVEN_TEST_POOL_123"],
            timeframe="1h",
            normalize_timezone=True
        )
        
        # Assertions
        assert not df.empty
        assert len(df) == 5
        # Check that datetime column is timezone-naive (normalized to UTC)
        assert df['datetime'].dt.tz is None
        # Verify data integrity
        assert df['open'].iloc[0] == 100.0
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_by_date_range(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test strict date range export method."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        start_date = "2023-01-01"
        end_date = "2023-01-02"
        
        # Pre-populate the cache
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        df = await qlib_exporter.export_ohlcv_data_by_date_range(
            symbols=["HEAVEN_TEST_POOL_123"],
            start_date=start_date,
            end_date=end_date,
            timeframe="1h"
        )
        
        # Assertions
        assert not df.empty
        # Verify timezone normalization was applied
        assert df['datetime'].dt.tz is None
        # Verify data is sorted
        assert df['datetime'].is_monotonic_increasing
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_by_date_range_with_limits(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test date range export with record limits."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Pre-populate the cache
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test with record limit
        df = await qlib_exporter.export_ohlcv_data_by_date_range(
            symbols=["HEAVEN_TEST_POOL_123"],
            start_date="2023-01-01",
            end_date="2023-01-02",
            timeframe="1h",
            max_records_per_symbol=10
        )
        
        # Assertions
        assert not df.empty
        assert len(df) <= 10  # Should be limited
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_by_date_range_validation_errors(self, qlib_exporter):
        """Test date range export validation errors."""
        # Test missing dates
        with pytest.raises(ValueError, match="Both start_date and end_date are required"):
            await qlib_exporter.export_ohlcv_data_by_date_range(
                symbols=["TEST"],
                start_date="2023-01-01"
                # Missing end_date
            )
        
        # Test invalid date order
        with pytest.raises(ValueError, match="start_date must be before end_date"):
            await qlib_exporter.export_ohlcv_data_by_date_range(
                symbols=["TEST"],
                start_date="2023-01-02",
                end_date="2023-01-01"
            )
    
    @pytest.mark.asyncio
    async def test_export_symbol_data_with_validation(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test single symbol export with validation."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Pre-populate the cache
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        result = await qlib_exporter.export_symbol_data_with_validation(
            symbol="HEAVEN_TEST_POOL_123",
            timeframe="1h",
            validate_data=True
        )
        
        # Assertions
        assert result['symbol'] == "HEAVEN_TEST_POOL_123"
        assert not result['data'].empty
        assert 'validation' in result
        assert 'metadata' in result
        assert result['metadata']['record_count'] == 24
        assert result['metadata']['timeframe'] == "1h"
        assert result['metadata']['has_volume'] is True
    
    def test_apply_date_range_filter(self, qlib_exporter):
        """Test date range filtering helper method."""
        # Create test DataFrame
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=10, freq='1h'),
            'symbol': ['TEST'] * 10,
            'open': [100.0] * 10
        })
        
        start_date = datetime(2023, 1, 1, 3)  # 3 AM
        end_date = datetime(2023, 1, 1, 7)    # 7 AM
        
        # Test filtering
        filtered = qlib_exporter._apply_date_range_filter(df, start_date, end_date)
        
        # Should include records from 3 AM to 7 AM (inclusive)
        assert len(filtered) == 5  # 3, 4, 5, 6, 7 AM
        assert filtered['datetime'].min() >= start_date
        assert filtered['datetime'].max() <= end_date
    
    def test_normalize_timezone(self, qlib_exporter):
        """Test timezone normalization."""
        # Create DataFrame with timezone-naive datetime
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=5, freq='1h'),
            'symbol': ['TEST'] * 5,
            'open': [100.0] * 5
        })
        
        # Test normalization
        normalized = qlib_exporter._normalize_timezone(df)
        
        # Should remain timezone-naive but be treated as UTC
        assert normalized['datetime'].dt.tz is None
        assert len(normalized) == 5
        
        # Test with timezone-aware data
        df_tz = df.copy()
        df_tz['datetime'] = df_tz['datetime'].dt.tz_localize('US/Eastern')
        
        normalized_tz = qlib_exporter._normalize_timezone(df_tz)
        
        # Should be converted to UTC and made timezone-naive
        assert normalized_tz['datetime'].dt.tz is None
        assert len(normalized_tz) == 5
    
    @pytest.mark.asyncio
    async def test_get_data_availability_report(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test generating data availability report."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        continuity_report = ContinuityReport(
            pool_id="solana_test_pool_123",
            timeframe="1h",
            total_gaps=2,
            gaps=[],
            data_quality_score=0.95
        )
        mock_db_manager.check_data_continuity.return_value = continuity_report
        
        # Pre-populate the cache to simulate the symbol being found
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        # Test
        report = await qlib_exporter.get_data_availability_report(
            symbols=["HEAVEN_TEST_POOL_123"],
            timeframe="1h"
        )
        
        # Assertions
        assert "HEAVEN_TEST_POOL_123" in report
        symbol_info = report["HEAVEN_TEST_POOL_123"]
        assert symbol_info['available'] is True
        assert symbol_info['pool_id'] == "solana_test_pool_123"
        assert symbol_info['dex_id'] == "heaven"
        assert symbol_info['total_records'] == 24
        assert symbol_info['data_quality_score'] == 0.95
        assert symbol_info['total_gaps'] == 2
    
    @pytest.mark.asyncio
    async def test_export_to_qlib_format(self, qlib_exporter, mock_db_manager, sample_pool, sample_ohlcv_records):
        """Test exporting to QLib format files."""
        # Setup mocks
        mock_db_manager.get_watchlist_pools.return_value = ["solana_test_pool_123"]
        mock_db_manager.get_pool.return_value = sample_pool
        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Pre-populate the cache to simulate the symbol being found
        qlib_exporter._pool_cache["HEAVEN_TEST_POOL_123"] = sample_pool
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test
            result = await qlib_exporter.export_to_qlib_format(
                output_dir=temp_dir,
                symbols=["HEAVEN_TEST_POOL_123"],
                timeframe="1h"
            )
            
            # Assertions
            assert result['success'] is True
            assert result['files_created'] == 1
            assert result['total_records'] == 24
            
            # Check files were created
            output_path = Path(temp_dir)
            csv_files = list(output_path.glob("*.csv"))
            assert len(csv_files) == 1
            assert csv_files[0].name == "HEAVEN_TEST_POOL_123.csv"
            
            # Check summary file
            summary_file = output_path / "export_summary.json"
            assert summary_file.exists()
            
            with open(summary_file) as f:
                summary = json.load(f)
                assert summary['symbols_exported'] == 1
                assert summary['files_created'] == 1
    
    def test_generate_symbol_name(self, qlib_exporter, sample_pool):
        """Test symbol name generation."""
        symbol = qlib_exporter._generate_symbol_name(sample_pool)
        assert symbol == "HEAVEN_TEST_POOL_123"
    
    def test_convert_ohlcv_to_qlib_format(self, qlib_exporter, sample_ohlcv_records):
        """Test converting OHLCV records to QLib format."""
        df = qlib_exporter._convert_ohlcv_to_qlib_format(
            sample_ohlcv_records, "TEST_SYMBOL", include_volume=True
        )
        
        assert not df.empty
        assert len(df) == 24
        assert list(df.columns) == ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume']
        assert all(df['symbol'] == "TEST_SYMBOL")
        assert df['open'].iloc[0] == 100.0
    
    def test_parse_date(self, qlib_exporter):
        """Test date parsing functionality."""
        # Test string date
        date_str = "2023-01-01"
        parsed = qlib_exporter._parse_date(date_str)
        assert isinstance(parsed, datetime)
        assert parsed.year == 2023
        assert parsed.month == 1
        assert parsed.day == 1
        
        # Test datetime object
        date_obj = datetime(2023, 6, 15)
        parsed = qlib_exporter._parse_date(date_obj)
        assert parsed == date_obj
        
        # Test invalid date
        with pytest.raises(ValueError):
            qlib_exporter._parse_date("invalid-date")


class TestQLibDataValidator:
    """Test cases for QLibDataValidator class."""
    
    def test_validate_dataframe_valid(self):
        """Test validation of valid DataFrame."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=10, freq='1h'),
            'symbol': ['TEST'] * 10,
            'open': [100.0] * 10,
            'high': [105.0] * 10,
            'low': [95.0] * 10,
            'close': [102.0] * 10,
            'volume': [1000.0] * 10
        })
        
        result = QLibDataValidator.validate_dataframe(df, require_volume=True)
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
        assert result['stats']['total_rows'] == 10
        assert result['stats']['unique_symbols'] == 1
    
    def test_validate_dataframe_missing_columns(self):
        """Test validation with missing required columns."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=10, freq='1h'),
            'symbol': ['TEST'] * 10,
            'open': [100.0] * 10
            # Missing high, low, close
        })
        
        result = QLibDataValidator.validate_dataframe(df)
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        assert 'Missing required columns' in result['errors'][0]
    
    def test_validate_dataframe_invalid_ohlc(self):
        """Test validation with invalid OHLC relationships."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=10, freq='1h'),
            'symbol': ['TEST'] * 10,
            'open': [100.0] * 10,
            'high': [90.0] * 10,  # High < Open (invalid)
            'low': [95.0] * 10,
            'close': [102.0] * 10
        })
        
        result = QLibDataValidator.validate_dataframe(df)
        
        assert len(result['warnings']) > 0
        assert any('Invalid OHLC relationships' in warning for warning in result['warnings'])
    
    def test_validate_dataframe_empty(self):
        """Test validation of empty DataFrame."""
        df = pd.DataFrame()
        
        result = QLibDataValidator.validate_dataframe(df)
        
        assert result['is_valid'] is False
        assert 'DataFrame is empty' in result['errors']


class TestQLibSymbolManager:
    """Test cases for QLibSymbolManager class."""
    
    def test_normalize_symbol(self):
        """Test symbol normalization."""
        # Test basic normalization
        assert QLibSymbolManager.normalize_symbol("test-symbol!") == "TESTSYMBOL"
        
        # Test symbol starting with number
        assert QLibSymbolManager.normalize_symbol("123test") == "S_123TEST"
        
        # Test long symbol
        long_symbol = "a" * 60
        normalized = QLibSymbolManager.normalize_symbol(long_symbol)
        assert len(normalized) <= 50
    
    def test_create_symbol_mapping(self):
        """Test creating symbol mapping from pools."""
        pools = [
            MagicMock(id="pool1", dex_id="heaven", name="Test Pool 1"),
            MagicMock(id="pool2", dex_id="pumpswap", name="Test Pool 2")
        ]
        
        mapping = QLibSymbolManager.create_symbol_mapping(pools)
        
        assert len(mapping) == 2
        assert "pool1" in mapping
        assert "pool2" in mapping
        assert mapping["pool1"] != mapping["pool2"]  # Should be unique


class TestQLibDataProcessor:
    """Test cases for QLibDataProcessor class."""
    
    def test_resample_ohlcv(self):
        """Test OHLCV data resampling."""
        # Create test data with 1-hour intervals
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=24, freq='1h'),
            'symbol': ['TEST'] * 24,
            'open': list(range(100, 124)),
            'high': list(range(105, 129)),
            'low': list(range(95, 119)),
            'close': list(range(102, 126)),
            'volume': [1000] * 24
        })
        
        # Resample to daily
        resampled = QLibDataProcessor.resample_ohlcv(df, '1D')
        
        assert len(resampled) == 1  # Should have 1 day
        assert resampled['open'].iloc[0] == 100  # First open
        assert resampled['close'].iloc[0] == 125  # Last close
        assert resampled['high'].iloc[0] == 128  # Max high
        assert resampled['low'].iloc[0] == 95   # Min low
        assert resampled['volume'].iloc[0] == 24000  # Sum of volume
    
    def test_fill_missing_data(self):
        """Test filling missing data."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=5, freq='1h'),
            'symbol': ['TEST'] * 5,
            'open': [100, None, None, 103, 104],
            'high': [105, None, None, 108, 109],
            'low': [95, None, None, 98, 99],
            'close': [102, None, None, 105, 106]
        })
        
        # Forward fill
        filled = QLibDataProcessor.fill_missing_data(df, method='forward')
        
        assert filled['open'].iloc[1] == 100  # Forward filled
        assert filled['open'].iloc[2] == 100  # Forward filled
        assert not filled.isnull().any().any()  # No null values
    
    def test_calculate_returns(self):
        """Test calculating returns."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=5, freq='1h'),
            'symbol': ['TEST'] * 5,
            'close': [100, 102, 104, 103, 105]
        })
        
        result = QLibDataProcessor.calculate_returns(df)
        
        assert 'return' in result.columns
        assert 'log_return' in result.columns
        assert pd.isna(result['return'].iloc[0])  # First return should be NaN
        assert abs(result['return'].iloc[1] - 0.02) < 1e-10  # (102-100)/100 = 0.02


class TestQLibIntegration:
    """Integration tests for QLib data format compatibility."""
    
    @pytest.fixture
    def integration_db_manager(self):
        """Create a more realistic database manager mock for integration tests."""
        mock_db = AsyncMock()
        
        # Mock realistic pool data
        pools = [
            Pool(
                id="solana_heaven_pool_1",
                address="heaven_addr_1",
                name="Heaven Pool 1",
                dex_id="heaven",
                base_token_id="token_1",
                quote_token_id="token_2",
                reserve_usd=Decimal("50000"),
                created_at=datetime.utcnow()
            ),
            Pool(
                id="solana_pumpswap_pool_1",
                address="pumpswap_addr_1", 
                name="PumpSwap Pool 1",
                dex_id="pumpswap",
                base_token_id="token_3",
                quote_token_id="token_4",
                reserve_usd=Decimal("75000"),
                created_at=datetime.utcnow()
            )
        ]
        
        # Mock OHLCV data with realistic patterns
        def create_realistic_ohlcv(pool_id: str, days: int = 7, start_time=None, end_time=None) -> List[OHLCVRecord]:
            records = []
            
            # Use provided time range or default
            if start_time and end_time:
                base_time = start_time.replace(minute=0, second=0, microsecond=0)
                total_hours = int((end_time - start_time).total_seconds() / 3600)
            else:
                base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                total_hours = days * 24
            
            base_price = 100.0
            
            for hour in range(total_hours):
                timestamp = base_time + timedelta(hours=hour)
                
                # Skip if outside the requested range
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                
                # Simulate realistic price movement
                price_change = (hash(f"{pool_id}_{hour}") % 1000 - 500) / 10000
                open_price = base_price * (1 + price_change)
                high_price = open_price * (1 + abs(price_change) * 2)
                low_price = open_price * (1 - abs(price_change) * 2)
                close_price = open_price * (1 + price_change * 0.5)
                volume = 1000 + (hash(f"{pool_id}_{hour}") % 5000)
                
                record = OHLCVRecord(
                    pool_id=pool_id,
                    timeframe="1h",
                    timestamp=int(timestamp.timestamp()),
                    open_price=Decimal(str(round(open_price, 8))),
                    high_price=Decimal(str(round(high_price, 8))),
                    low_price=Decimal(str(round(low_price, 8))),
                    close_price=Decimal(str(round(close_price, 8))),
                    volume_usd=Decimal(str(volume)),
                    datetime=timestamp
                )
                records.append(record)
                base_price = float(close_price)  # Use close as next base
            
            return records
        
        # Setup mock responses
        mock_db.get_watchlist_pools.return_value = ["solana_heaven_pool_1", "solana_pumpswap_pool_1"]
        mock_db.get_pool.side_effect = lambda pool_id: next((p for p in pools if p.id == pool_id), None)
        mock_db.get_ohlcv_data.side_effect = lambda pool_id, **kwargs: create_realistic_ohlcv(
            pool_id, 
            start_time=kwargs.get('start_time'),
            end_time=kwargs.get('end_time')
        )
        
        # Mock continuity report
        mock_db.check_data_continuity.return_value = ContinuityReport(
            pool_id="test_pool",
            timeframe="1h",
            total_gaps=1,
            gaps=[],
            data_quality_score=0.98
        )
        
        return mock_db
    
    @pytest.fixture
    def integration_exporter(self, integration_db_manager):
        """Create QLib exporter with integration database."""
        return QLibExporter(integration_db_manager)
    
    @pytest.mark.asyncio
    async def test_qlib_format_compliance_full_export(self, integration_exporter):
        """Test full export compliance with QLib format requirements."""
        # Export all available data
        df = await integration_exporter.export_ohlcv_data(
            timeframe="1h",
            normalize_timezone=True,
            fill_missing=False
        )
        
        # Validate QLib format compliance
        from gecko_terminal_collector.qlib.utils import QLibDataValidator
        validation = QLibDataValidator.validate_dataframe(df, require_volume=True)
        
        # Assertions for QLib compliance
        assert validation['is_valid'], f"QLib validation failed: {validation['errors']}"
        assert not df.empty
        assert len(validation['errors']) == 0
        
        # Check required columns
        required_cols = ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume']
        assert all(col in df.columns for col in required_cols)
        
        # Check data types
        assert pd.api.types.is_datetime64_any_dtype(df['datetime'])
        assert pd.api.types.is_numeric_dtype(df['open'])
        assert pd.api.types.is_numeric_dtype(df['high'])
        assert pd.api.types.is_numeric_dtype(df['low'])
        assert pd.api.types.is_numeric_dtype(df['close'])
        assert pd.api.types.is_numeric_dtype(df['volume'])
        
        # Check timezone normalization (should be timezone-naive UTC)
        assert df['datetime'].dt.tz is None
        
        # Check data sorting
        assert df['datetime'].is_monotonic_increasing or df.groupby('symbol')['datetime'].apply(lambda x: x.is_monotonic_increasing).all()
        
        # Check OHLC relationships
        ohlc_valid = (
            (df['high'] >= df['open']) &
            (df['high'] >= df['close']) &
            (df['high'] >= df['low']) &
            (df['low'] <= df['open']) &
            (df['low'] <= df['close'])
        ).all()
        assert ohlc_valid, "Invalid OHLC relationships found"
    
    @pytest.mark.asyncio
    async def test_qlib_export_with_date_filtering(self, integration_exporter):
        """Test QLib export with date range filtering."""
        start_date = datetime.utcnow() - timedelta(days=3)
        end_date = datetime.utcnow() - timedelta(days=1)
        
        df = await integration_exporter.export_ohlcv_data_by_date_range(
            start_date=start_date,
            end_date=end_date,
            timeframe="1h"
        )
        
        # Validate date filtering
        assert not df.empty
        assert df['datetime'].min() >= start_date
        assert df['datetime'].max() <= end_date
        
        # Validate QLib format
        from gecko_terminal_collector.qlib.utils import QLibDataValidator
        validation = QLibDataValidator.validate_dataframe(df, require_volume=True)
        assert validation['is_valid']
    
    @pytest.mark.asyncio
    async def test_qlib_symbol_consistency(self, integration_exporter):
        """Test symbol naming consistency for QLib."""
        # Get symbol list
        symbols = await integration_exporter.get_symbol_list()
        assert len(symbols) > 0
        
        # Export data for each symbol
        for symbol in symbols:
            result = await integration_exporter.export_symbol_data_with_validation(
                symbol=symbol,
                timeframe="1h",
                validate_data=True
            )
            
            assert result['symbol'] == symbol
            assert not result['data'].empty
            assert result['validation']['is_valid']
            
            # Check symbol consistency in data
            assert (result['data']['symbol'] == symbol).all()
    
    @pytest.mark.asyncio
    async def test_qlib_data_availability_report_integration(self, integration_exporter):
        """Test data availability reporting for QLib integration."""
        report = await integration_exporter.get_data_availability_report(timeframe="1h")
        
        assert len(report) > 0
        
        for symbol, info in report.items():
            assert info['available'] is True
            assert 'pool_id' in info
            assert 'dex_id' in info
            assert 'start_date' in info
            assert 'end_date' in info
            assert 'total_records' in info
            assert 'data_quality_score' in info
            assert info['data_quality_score'] >= 0.0
            assert info['data_quality_score'] <= 1.0
    
    @pytest.mark.asyncio
    async def test_qlib_file_export_integration(self, integration_exporter):
        """Test file export for QLib integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export to files
            result = await integration_exporter.export_to_qlib_format(
                output_dir=temp_dir,
                timeframe="1h",
                date_field_name="datetime"
            )
            
            assert result['success'] is True
            assert result['files_created'] > 0
            assert result['total_records'] > 0
            
            # Validate exported files
            from gecko_terminal_collector.qlib.utils import validate_qlib_export_directory
            validation = validate_qlib_export_directory(temp_dir)
            
            assert validation['is_valid']
            assert validation['stats']['csv_files'] > 0
            assert len(validation['stats']['symbols']) > 0
            
            # Check individual CSV files
            output_path = Path(temp_dir)
            csv_files = list(output_path.glob("*.csv"))
            
            for csv_file in csv_files:
                if csv_file.name != 'export_summary.json':
                    df = pd.read_csv(csv_file)
                    
                    # Validate each file
                    from gecko_terminal_collector.qlib.utils import QLibDataValidator
                    file_validation = QLibDataValidator.validate_dataframe(df, require_volume=True)
                    assert file_validation['is_valid'], f"File {csv_file.name} failed validation"
    
    @pytest.mark.asyncio
    async def test_qlib_timezone_handling_integration(self, integration_exporter):
        """Test timezone handling for QLib compatibility."""
        # Export data with timezone normalization
        df = await integration_exporter.export_ohlcv_data(
            timeframe="1h",
            normalize_timezone=True
        )
        
        assert not df.empty
        
        # Check timezone handling
        assert df['datetime'].dt.tz is None  # Should be timezone-naive
        
        # Verify timestamps are reasonable (not in far future/past)
        now = datetime.utcnow()
        min_reasonable = now - timedelta(days=365)  # 1 year ago
        max_reasonable = now + timedelta(days=30)   # 30 days in future (more reasonable for test data)
        
        assert df['datetime'].min() >= min_reasonable
        assert df['datetime'].max() <= max_reasonable
    
    @pytest.mark.asyncio
    async def test_qlib_data_normalization_integration(self, integration_exporter):
        """Test data normalization for QLib compatibility."""
        # Export data with all normalization options
        df = await integration_exporter.export_ohlcv_data(
            timeframe="1h",
            normalize_timezone=True,
            fill_missing=True
        )
        
        assert not df.empty
        
        # Check for data quality
        assert not df.isnull().any().any(), "Should not have null values after normalization"
        
        # Check numeric precision (should be reasonable for financial data)
        for col in ['open', 'high', 'low', 'close']:
            assert df[col].dtype in ['float64', 'int64'], f"Column {col} should be numeric"
            assert (df[col] > 0).all(), f"Column {col} should have positive values"
        
        # Check volume
        assert (df['volume'] >= 0).all(), "Volume should be non-negative"


if __name__ == '__main__':
    pytest.main([__file__])