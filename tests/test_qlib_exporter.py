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


if __name__ == '__main__':
    pytest.main([__file__])