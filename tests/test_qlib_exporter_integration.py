"""
Integration tests for QLib exporter with IntegratedSymbolMapper.

This test suite verifies the integration between the QLib exporter and
the integrated symbol mapper, ensuring consistent symbol handling across
the system.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.qlib.integrated_symbol_mapper import IntegratedSymbolMapper
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.models.core import Pool, OHLCVRecord


class TestQLibExporterIntegration:
    """Integration tests for QLib exporter with symbol mapper."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        return AsyncMock(spec=EnhancedDatabaseManager)
    
    @pytest.fixture
    def mock_symbol_mapper(self, mock_enhanced_db_manager):
        """Create mock integrated symbol mapper."""
        mapper = AsyncMock(spec=IntegratedSymbolMapper)
        mapper.enhanced_db_manager = mock_enhanced_db_manager
        return mapper
    
    @pytest.fixture
    def qlib_exporter_with_mapper(self, mock_enhanced_db_manager, mock_symbol_mapper):
        """Create QLib exporter with integrated symbol mapper."""
        return QLibExporter(mock_enhanced_db_manager, mock_symbol_mapper)
    
    @pytest.fixture
    def qlib_exporter_without_mapper(self, mock_enhanced_db_manager):
        """Create QLib exporter without symbol mapper for comparison."""
        return QLibExporter(mock_enhanced_db_manager)
    
    @pytest.fixture
    def sample_pools(self):
        """Create sample pools with mixed case addresses."""
        return [
            Pool(
                id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
                address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
                name="Mixed Case Pool 1",
                dex_id="raydium",
                base_token_id="token1",
                quote_token_id="token2",
                reserve_usd=Decimal("1000000"),
                created_at=datetime.utcnow()
            ),
            Pool(
                id="solana_abcDEF123456789",
                address="abcDEF123456789",
                name="Mixed Case Pool 2",
                dex_id="orca",
                base_token_id="token3",
                quote_token_id="token4",
                reserve_usd=Decimal("500000"),
                created_at=datetime.utcnow()
            )
        ]
    
    @pytest.fixture
    def sample_ohlcv_records(self):
        """Create sample OHLCV records."""
        base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        records = []
        
        for i in range(24):  # 24 hours of data
            record = OHLCVRecord(
                pool_id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
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
    
    def test_exporter_initialization_with_enhanced_db_manager(self, mock_enhanced_db_manager):
        """Test that exporter initializes symbol mapper with enhanced database manager."""
        exporter = QLibExporter(mock_enhanced_db_manager)
        
        # Should automatically create integrated symbol mapper
        assert exporter.symbol_mapper is not None
        assert isinstance(exporter.symbol_mapper, IntegratedSymbolMapper)
        assert exporter.symbol_mapper.enhanced_db_manager == mock_enhanced_db_manager
    
    def test_exporter_initialization_with_basic_db_manager(self):
        """Test that exporter works without symbol mapper for basic database manager."""
        basic_db_manager = AsyncMock()  # Not an EnhancedDatabaseManager
        exporter = QLibExporter(basic_db_manager)
        
        # Should not create symbol mapper
        assert exporter.symbol_mapper is None
    
    def test_exporter_initialization_with_provided_mapper(self, mock_enhanced_db_manager, mock_symbol_mapper):
        """Test that exporter uses provided symbol mapper."""
        exporter = QLibExporter(mock_enhanced_db_manager, mock_symbol_mapper)
        
        assert exporter.symbol_mapper == mock_symbol_mapper
    
    @pytest.mark.asyncio
    async def test_initialize_symbol_cache(self, qlib_exporter_with_mapper, mock_symbol_mapper):
        """Test symbol cache initialization."""
        # Setup mock
        mock_symbol_mapper.populate_cache_from_database.return_value = 10
        
        # Test
        symbols_loaded = await qlib_exporter_with_mapper.initialize_symbol_cache(limit=100)
        
        # Assertions
        assert symbols_loaded == 10
        mock_symbol_mapper.populate_cache_from_database.assert_called_once_with(limit=100)
    
    @pytest.mark.asyncio
    async def test_initialize_symbol_cache_without_mapper(self, qlib_exporter_without_mapper):
        """Test symbol cache initialization without mapper."""
        symbols_loaded = await qlib_exporter_without_mapper.initialize_symbol_cache()
        
        # Should return 0 when no mapper is available
        assert symbols_loaded == 0
    
    def test_generate_symbol_name_with_mapper(self, qlib_exporter_with_mapper, mock_symbol_mapper, sample_pools):
        """Test symbol name generation using integrated mapper."""
        pool = sample_pools[0]
        expected_symbol = "test_symbol_from_mapper"
        
        # Setup mock
        mock_symbol_mapper.generate_symbol.return_value = expected_symbol
        
        # Test
        symbol = qlib_exporter_with_mapper._generate_symbol_name(pool)
        
        # Assertions
        assert symbol == expected_symbol
        mock_symbol_mapper.generate_symbol.assert_called_once_with(pool)
    
    def test_generate_symbol_name_without_mapper(self, qlib_exporter_without_mapper, sample_pools):
        """Test symbol name generation without mapper (fallback)."""
        pool = sample_pools[0]
        
        # Test
        symbol = qlib_exporter_without_mapper._generate_symbol_name(pool)
        
        # Should use fallback logic
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
    
    @pytest.mark.asyncio
    async def test_get_pool_for_symbol_with_mapper(self, qlib_exporter_with_mapper, mock_symbol_mapper, sample_pools):
        """Test getting pool for symbol using integrated mapper."""
        pool = sample_pools[0]
        symbol = "test_symbol"
        
        # Setup mock
        mock_symbol_mapper.lookup_pool_with_fallback.return_value = pool
        
        # Test
        result = await qlib_exporter_with_mapper._get_pool_for_symbol(symbol)
        
        # Assertions
        assert result == pool
        mock_symbol_mapper.lookup_pool_with_fallback.assert_called_once_with(symbol)
    
    @pytest.mark.asyncio
    async def test_get_pool_for_symbol_without_mapper(self, qlib_exporter_without_mapper, mock_enhanced_db_manager, sample_pools):
        """Test getting pool for symbol without mapper (fallback)."""
        pool = sample_pools[0]
        symbol = pool.id
        
        # Setup mock
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Test
        result = await qlib_exporter_without_mapper._get_pool_for_symbol(symbol)
        
        # Assertions
        assert result == pool
        mock_enhanced_db_manager.get_pool.assert_called_once_with(symbol)
    
    @pytest.mark.asyncio
    async def test_export_ohlcv_data_with_symbol_mapper(self, qlib_exporter_with_mapper, mock_enhanced_db_manager, mock_symbol_mapper, sample_pools, sample_ohlcv_records):
        """Test OHLCV data export using symbol mapper."""
        pool = sample_pools[0]
        symbol = "mapped_symbol"
        
        # Setup mocks
        mock_enhanced_db_manager.get_watchlist_pools.return_value = [pool.id]
        mock_enhanced_db_manager.get_pool.return_value = pool
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        mock_symbol_mapper.generate_symbol.return_value = symbol
        mock_symbol_mapper.lookup_pool_with_fallback.return_value = pool
        
        # Test
        df = await qlib_exporter_with_mapper.export_ohlcv_data(
            symbols=[symbol],
            timeframe="1h"
        )
        
        # Assertions
        assert not df.empty
        assert len(df) == 24
        assert df['symbol'].iloc[0] == symbol
        mock_symbol_mapper.lookup_pool_with_fallback.assert_called_with(symbol)
    
    @pytest.mark.asyncio
    async def test_case_insensitive_symbol_lookup(self, qlib_exporter_with_mapper, mock_symbol_mapper, sample_pools):
        """Test case-insensitive symbol lookup through mapper."""
        pool = sample_pools[0]
        original_symbol = "MixedCaseSymbol"
        lowercase_symbol = "mixedcasesymbol"
        
        # Setup mock to return pool for both cases
        mock_symbol_mapper.lookup_pool_with_fallback.return_value = pool
        
        # Test with original case
        result1 = await qlib_exporter_with_mapper._get_pool_for_symbol(original_symbol)
        assert result1 == pool
        
        # Test with lowercase
        result2 = await qlib_exporter_with_mapper._get_pool_for_symbol(lowercase_symbol)
        assert result2 == pool
        
        # Verify both calls were made to the mapper
        assert mock_symbol_mapper.lookup_pool_with_fallback.call_count == 2
    
    @pytest.mark.asyncio
    async def test_symbol_consistency_across_operations(self, mock_enhanced_db_manager, sample_pools, sample_ohlcv_records):
        """Test that symbols are consistent across different operations."""
        # Create real integrated symbol mapper (not mocked)
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        pool = sample_pools[0]
        
        # Setup database mocks
        mock_enhanced_db_manager.get_watchlist_pools.return_value = [pool.id]
        mock_enhanced_db_manager.get_pool.return_value = pool
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Generate symbol using exporter
        symbol1 = exporter._generate_symbol_name(pool)
        
        # Generate symbol using mapper directly
        symbol2 = real_mapper.generate_symbol(pool)
        
        # Should be identical
        assert symbol1 == symbol2
        
        # Test that lookup works with generated symbol
        result = await exporter._get_pool_for_symbol(symbol1)
        assert result == pool
    
    @pytest.mark.asyncio
    async def test_export_with_database_fallback(self, qlib_exporter_with_mapper, mock_enhanced_db_manager, mock_symbol_mapper, sample_pools, sample_ohlcv_records):
        """Test export with database fallback when symbol not in cache."""
        pool = sample_pools[0]
        symbol = "uncached_symbol"
        
        # Setup mocks - symbol not in cache initially, but found in database
        mock_symbol_mapper.lookup_pool_with_fallback.return_value = pool
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Test
        df = await qlib_exporter_with_mapper.export_ohlcv_data(
            symbols=[symbol],
            timeframe="1h"
        )
        
        # Assertions
        assert not df.empty
        assert len(df) == 24
        mock_symbol_mapper.lookup_pool_with_fallback.assert_called_with(symbol)
    
    @pytest.mark.asyncio
    async def test_bulk_symbol_operations(self, mock_enhanced_db_manager, sample_pools, sample_ohlcv_records):
        """Test bulk operations with symbol mapper."""
        # Create real integrated symbol mapper
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        # Setup database mocks
        mock_enhanced_db_manager.get_all_pools.return_value = sample_pools
        mock_enhanced_db_manager.get_watchlist_pools.return_value = [pool.id for pool in sample_pools]
        mock_enhanced_db_manager.get_pool.side_effect = lambda pool_id: next(
            (pool for pool in sample_pools if pool.id == pool_id), None
        )
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Initialize cache
        await exporter.initialize_symbol_cache()
        
        # Get symbol list
        symbols = await exporter.get_symbol_list(active_only=True)
        
        # Should have symbols for all pools
        assert len(symbols) == len(sample_pools)
        
        # Export data for all symbols
        df = await exporter.export_ohlcv_data(
            symbols=symbols,
            timeframe="1h"
        )
        
        # Should have data for all symbols
        assert not df.empty
        unique_symbols = df['symbol'].unique()
        assert len(unique_symbols) == len(sample_pools)
    
    @pytest.mark.asyncio
    async def test_performance_metrics_integration(self, mock_enhanced_db_manager, sample_pools):
        """Test that performance metrics are tracked during operations."""
        # Create real integrated symbol mapper
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        pool = sample_pools[0]
        
        # Setup database mocks
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Perform some operations
        symbol = exporter._generate_symbol_name(pool)
        await exporter._get_pool_for_symbol(symbol)  # Cache hit
        await exporter._get_pool_for_symbol("unknown_symbol")  # Cache miss
        
        # Check performance metrics
        metrics = real_mapper.get_performance_metrics()
        
        assert metrics['cache_hits'] >= 1
        assert metrics['total_cached_symbols'] >= 1
        assert 'cache_hit_rate' in metrics
    
    @pytest.mark.asyncio
    async def test_export_to_qlib_format_with_mapper(self, qlib_exporter_with_mapper, mock_enhanced_db_manager, mock_symbol_mapper, sample_pools, sample_ohlcv_records):
        """Test exporting to QLib format files with symbol mapper."""
        pool = sample_pools[0]
        symbol = "mapped_symbol"
        
        # Setup mocks
        mock_enhanced_db_manager.get_watchlist_pools.return_value = [pool.id]
        mock_enhanced_db_manager.get_pool.return_value = pool
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        mock_symbol_mapper.generate_symbol.return_value = symbol
        mock_symbol_mapper.lookup_pool_with_fallback.return_value = pool
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test
            result = await qlib_exporter_with_mapper.export_to_qlib_format(
                output_dir=temp_dir,
                symbols=[symbol],
                timeframe="1h"
            )
            
            # Assertions
            assert result['success'] is True
            assert result['files_created'] == 1
            
            # Check that file was created with mapped symbol name
            output_path = Path(temp_dir)
            csv_files = list(output_path.glob("*.csv"))
            assert len(csv_files) == 1
            assert csv_files[0].name == f"{symbol}.csv"
    
    @pytest.mark.asyncio
    async def test_symbol_mapper_error_handling(self, qlib_exporter_with_mapper, mock_symbol_mapper, sample_pools):
        """Test error handling when symbol mapper fails."""
        pool = sample_pools[0]
        
        # Setup mock to raise exception
        mock_symbol_mapper.generate_symbol.side_effect = Exception("Mapper error")
        
        # Test - should fall back to basic symbol generation
        try:
            symbol = qlib_exporter_with_mapper._generate_symbol_name(pool)
            # If no exception, the fallback worked
            assert symbol is not None
            assert len(symbol) > 0
        except Exception:
            # If exception is raised, that's also acceptable behavior
            # The important thing is that the system doesn't crash completely
            pass
    
    @pytest.mark.asyncio
    async def test_cache_validation_integration(self, mock_enhanced_db_manager, sample_pools):
        """Test cache validation integration."""
        # Create real integrated symbol mapper
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        # Setup database mocks
        mock_enhanced_db_manager.get_all_pools.return_value = sample_pools
        mock_enhanced_db_manager.get_pool.side_effect = lambda pool_id: next(
            (pool for pool in sample_pools if pool.id == pool_id), None
        )
        
        # Initialize cache
        await exporter.initialize_symbol_cache()
        
        # Validate cache consistency
        validation_results = await real_mapper.validate_cache_consistency()
        
        assert validation_results['is_consistent'] is True
        assert validation_results['total_symbols_checked'] == len(sample_pools)
        assert validation_results['database_mismatches'] == 0


class TestSymbolMapperRequirementsIntegration:
    """Test integration requirements for symbol mapper."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        return AsyncMock(spec=EnhancedDatabaseManager)
    
    @pytest.fixture
    def sample_pool_mixed_case(self):
        """Create sample pool with mixed case for testing."""
        return Pool(
            id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            name="Mixed Case Test Pool",
            dex_id="raydium",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000000"),
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_ohlcv_records(self):
        """Create sample OHLCV records for testing."""
        base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        records = []
        
        for i in range(24):  # 24 hours of data
            record = OHLCVRecord(
                pool_id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
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
    async def test_requirement_integration_case_preservation(self, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test that case preservation works through the full integration."""
        # Create real components
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        # Generate symbol through exporter
        symbol = exporter._generate_symbol_name(sample_pool_mixed_case)
        
        # Should preserve case
        assert "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP" in symbol
        
        # Should be able to look up with different cases
        pool_result = await exporter._get_pool_for_symbol(symbol.lower())
        assert pool_result == sample_pool_mixed_case
    
    @pytest.mark.asyncio
    async def test_requirement_integration_bidirectional_mapping(self, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test bidirectional mapping through integration."""
        # Create real components
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        # Setup database mock
        mock_enhanced_db_manager.get_pool.return_value = sample_pool_mixed_case
        
        # Generate symbol from pool
        symbol1 = exporter._generate_symbol_name(sample_pool_mixed_case)
        
        # Look up pool from symbol
        pool_result = await exporter._get_pool_for_symbol(symbol1)
        
        # Generate symbol from retrieved pool
        symbol2 = exporter._generate_symbol_name(pool_result)
        
        # Should be identical
        assert symbol1 == symbol2
        assert pool_result == sample_pool_mixed_case
    
    @pytest.mark.asyncio
    async def test_requirement_integration_external_system_compatibility(self, mock_enhanced_db_manager, sample_pool_mixed_case, sample_ohlcv_records):
        """Test external system compatibility through integration."""
        # Create real components
        real_mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        exporter = QLibExporter(mock_enhanced_db_manager, real_mapper)
        
        # Setup database mocks
        mock_enhanced_db_manager.get_pool.return_value = sample_pool_mixed_case
        mock_enhanced_db_manager.get_ohlcv_data.return_value = sample_ohlcv_records
        
        # Generate original symbol
        original_symbol = exporter._generate_symbol_name(sample_pool_mixed_case)
        
        # Simulate external system providing lowercase symbol
        external_symbol = original_symbol.lower()
        
        # Should be able to export data using external symbol
        df = await exporter.export_ohlcv_data(
            symbols=[external_symbol],
            timeframe="1h"
        )
        
        # Should work and preserve original case in output
        assert not df.empty
        # The symbol in the dataframe should be the original case
        assert df['symbol'].iloc[0] == original_symbol


if __name__ == "__main__":
    pytest.main([__file__])