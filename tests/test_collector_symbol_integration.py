"""
Tests for consistent symbol generation across all collectors.

This test suite verifies that all collectors use the integrated symbol
mapper consistently and generate symbols in a uniform way.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.qlib.integrated_symbol_mapper import IntegratedSymbolMapper
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.models.core import Pool


class TestCollectorSymbolIntegration:
    """Test symbol integration across all collectors."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        return AsyncMock(spec=EnhancedDatabaseManager)
    
    @pytest.fixture
    def collection_config(self):
        """Create collection configuration."""
        return CollectionConfig()
    
    @pytest.fixture
    def sample_pool(self):
        """Create sample pool for testing."""
        return Pool(
            id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            name="Test Pool",
            dex_id="raydium",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000000"),
            created_at=datetime.utcnow()
        )
    
    def test_base_collector_symbol_mapper_initialization(self, collection_config, mock_enhanced_db_manager):
        """Test that base collector initializes symbol mapper with enhanced database manager."""
        
        # Create a concrete implementation of BaseDataCollector for testing
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have initialized symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
        assert collector.symbol_mapper.enhanced_db_manager == mock_enhanced_db_manager
    
    def test_base_collector_symbol_generation(self, collection_config, mock_enhanced_db_manager, sample_pool):
        """Test symbol generation through base collector."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Test symbol generation
        symbol = collector.generate_symbol(sample_pool)
        
        # Should generate consistent symbol
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
    
    def test_base_collector_fallback_symbol_generation(self, collection_config, sample_pool):
        """Test fallback symbol generation when enhanced database manager is not available."""
        # Use basic database manager (not enhanced)
        basic_db_manager = AsyncMock()
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, basic_db_manager)
        
        # Should not have symbol mapper
        assert collector.symbol_mapper is None
        
        # Should still generate symbol using fallback
        symbol = collector.generate_symbol(sample_pool)
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
    
    @pytest.mark.asyncio
    async def test_base_collector_pool_lookup(self, collection_config, mock_enhanced_db_manager, sample_pool):
        """Test pool lookup through base collector."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Mock the symbol mapper lookup
        collector.symbol_mapper.lookup_pool_with_fallback = AsyncMock(return_value=sample_pool)
        
        # Test lookup
        symbol = "test_symbol"
        result = await collector.lookup_pool_by_symbol(symbol)
        
        # Assertions
        assert result == sample_pool
        collector.symbol_mapper.lookup_pool_with_fallback.assert_called_once_with(symbol)
    
    def test_watchlist_collector_symbol_integration(self, collection_config, mock_enhanced_db_manager):
        """Test that WatchlistCollector integrates with symbol mapper."""
        collector = WatchlistCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
    
    def test_ohlcv_collector_symbol_integration(self, collection_config, mock_enhanced_db_manager):
        """Test that OHLCVCollector integrates with symbol mapper."""
        collector = OHLCVCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
    
    def test_top_pools_collector_symbol_integration(self, collection_config, mock_enhanced_db_manager):
        """Test that TopPoolsCollector integrates with symbol mapper."""
        collector = TopPoolsCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
    
    def test_trade_collector_symbol_integration(self, collection_config, mock_enhanced_db_manager):
        """Test that TradeCollector integrates with symbol mapper."""
        collector = TradeCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
    
    def test_dex_monitoring_collector_symbol_integration(self, collection_config, mock_enhanced_db_manager):
        """Test that DEXMonitoringCollector integrates with symbol mapper."""
        collector = DEXMonitoringCollector(collection_config, mock_enhanced_db_manager)
        
        # Should have symbol mapper
        assert collector.symbol_mapper is not None
        assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
    
    def test_consistent_symbol_generation_across_collectors(self, collection_config, mock_enhanced_db_manager, sample_pool):
        """Test that all collectors generate the same symbol for the same pool."""
        
        # Create all collector types
        collectors = [
            WatchlistCollector(collection_config, mock_enhanced_db_manager),
            OHLCVCollector(collection_config, mock_enhanced_db_manager),
            TopPoolsCollector(collection_config, mock_enhanced_db_manager),
            TradeCollector(collection_config, mock_enhanced_db_manager),
            DEXMonitoringCollector(collection_config, mock_enhanced_db_manager)
        ]
        
        # Generate symbols from all collectors
        symbols = []
        for collector in collectors:
            symbol = collector.generate_symbol(sample_pool)
            symbols.append(symbol)
        
        # All symbols should be identical
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        for symbol in symbols:
            assert symbol == expected_symbol
        
        # All symbols should be the same
        assert len(set(symbols)) == 1
    
    def test_symbol_generation_with_dict_input(self, collection_config, mock_enhanced_db_manager):
        """Test symbol generation with dictionary input (fallback case)."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Test with dictionary input (no Pool object)
        pool_dict = {
            'id': 'solana_test_pool_123',
            'address': 'test_address_123',
            'name': 'Test Pool'
        }
        
        symbol = collector.generate_symbol(pool_dict)
        
        # Should generate symbol from dictionary
        expected_symbol = "solana_test_pool_123"
        assert symbol == expected_symbol
    
    def test_symbol_generation_with_string_input(self, collection_config, mock_enhanced_db_manager):
        """Test symbol generation with string input (fallback case)."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Test with string input
        pool_string = "solana_string_pool_456"
        
        symbol = collector.generate_symbol(pool_string)
        
        # Should generate symbol from string
        expected_symbol = "solana_string_pool_456"
        assert symbol == expected_symbol
    
    def test_symbol_generation_special_characters(self, collection_config, mock_enhanced_db_manager):
        """Test symbol generation handles special characters consistently."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Test with special characters
        pool_dict = {
            'id': 'solana-pool@with#special$chars%'
        }
        
        symbol = collector.generate_symbol(pool_dict)
        
        # Should clean up special characters
        expected_symbol = "solana_pool_with_special_chars"
        assert symbol == expected_symbol
        
        # Should not have duplicate underscores
        assert "__" not in symbol
        
        # Should not start or end with underscores
        assert not symbol.startswith("_")
        assert not symbol.endswith("_")
    
    @pytest.mark.asyncio
    async def test_pool_lookup_consistency_across_collectors(self, collection_config, mock_enhanced_db_manager, sample_pool):
        """Test that pool lookup is consistent across all collectors."""
        
        # Create all collector types
        collectors = [
            WatchlistCollector(collection_config, mock_enhanced_db_manager),
            OHLCVCollector(collection_config, mock_enhanced_db_manager),
            TopPoolsCollector(collection_config, mock_enhanced_db_manager),
            TradeCollector(collection_config, mock_enhanced_db_manager),
            DEXMonitoringCollector(collection_config, mock_enhanced_db_manager)
        ]
        
        # Mock the symbol mapper lookup for all collectors
        for collector in collectors:
            collector.symbol_mapper.lookup_pool_with_fallback = AsyncMock(return_value=sample_pool)
        
        # Test lookup from all collectors
        symbol = "test_symbol"
        results = []
        for collector in collectors:
            result = await collector.lookup_pool_by_symbol(symbol)
            results.append(result)
        
        # All results should be the same
        for result in results:
            assert result == sample_pool
        
        # Verify all symbol mappers were called
        for collector in collectors:
            collector.symbol_mapper.lookup_pool_with_fallback.assert_called_once_with(symbol)
    
    def test_symbol_mapper_error_handling_in_collectors(self, collection_config, mock_enhanced_db_manager, sample_pool):
        """Test that collectors handle symbol mapper errors gracefully."""
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, mock_enhanced_db_manager)
        
        # Mock symbol mapper to raise exception
        collector.symbol_mapper.generate_symbol = MagicMock(side_effect=Exception("Mapper error"))
        
        # Should fall back to basic symbol generation
        symbol = collector.generate_symbol(sample_pool)
        
        # Should still generate a valid symbol
        assert symbol is not None
        assert len(symbol) > 0
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
    
    @pytest.mark.asyncio
    async def test_pool_lookup_without_symbol_mapper(self, collection_config, sample_pool):
        """Test pool lookup when symbol mapper is not available."""
        # Use basic database manager (not enhanced)
        basic_db_manager = AsyncMock()
        
        class TestCollector(BaseDataCollector):
            async def collect(self):
                pass
            
            def validate_data(self, data):
                pass
            
            def get_collection_key(self) -> str:
                return "test_collector"
        
        collector = TestCollector(collection_config, basic_db_manager)
        
        # Should not have symbol mapper
        assert collector.symbol_mapper is None
        
        # Pool lookup should return None
        result = await collector.lookup_pool_by_symbol("test_symbol")
        assert result is None


class TestSymbolMapperRequirementsInCollectors:
    """Test that collectors meet symbol mapper requirements."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        return AsyncMock(spec=EnhancedDatabaseManager)
    
    @pytest.fixture
    def collection_config(self):
        """Create collection configuration."""
        return CollectionConfig()
    
    @pytest.fixture
    def sample_pool_mixed_case(self):
        """Create sample pool with mixed case for testing."""
        return Pool(
            id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            name="Mixed Case Pool",
            dex_id="raydium",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000000"),
            created_at=datetime.utcnow()
        )
    
    def test_requirement_5_1_collectors_preserve_case(self, collection_config, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test Requirement 5.1: All collectors preserve original case in symbol generation."""
        
        # Test with all collector types
        collectors = [
            WatchlistCollector(collection_config, mock_enhanced_db_manager),
            OHLCVCollector(collection_config, mock_enhanced_db_manager),
            TopPoolsCollector(collection_config, mock_enhanced_db_manager),
            TradeCollector(collection_config, mock_enhanced_db_manager),
            DEXMonitoringCollector(collection_config, mock_enhanced_db_manager)
        ]
        
        for collector in collectors:
            symbol = collector.generate_symbol(sample_pool_mixed_case)
            
            # Should preserve mixed case
            assert "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP" in symbol
            
            # Should contain both upper and lower case
            assert any(c.isupper() for c in symbol)
            assert any(c.islower() for c in symbol)
    
    @pytest.mark.asyncio
    async def test_requirement_5_2_collectors_support_case_insensitive_lookup(self, collection_config, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test Requirement 5.2: All collectors support case-insensitive lookup."""
        
        collector = WatchlistCollector(collection_config, mock_enhanced_db_manager)
        
        # Mock the symbol mapper to return pool for both cases
        collector.symbol_mapper.lookup_pool_with_fallback = AsyncMock(return_value=sample_pool_mixed_case)
        
        # Test with different cases
        original_symbol = "MixedCaseSymbol"
        lowercase_symbol = "mixedcasesymbol"
        uppercase_symbol = "MIXEDCASESYMBOL"
        
        # All should return the same pool
        result1 = await collector.lookup_pool_by_symbol(original_symbol)
        result2 = await collector.lookup_pool_by_symbol(lowercase_symbol)
        result3 = await collector.lookup_pool_by_symbol(uppercase_symbol)
        
        assert result1 == sample_pool_mixed_case
        assert result2 == sample_pool_mixed_case
        assert result3 == sample_pool_mixed_case
    
    def test_requirement_5_5_collectors_seamless_integration(self, collection_config, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test Requirement 5.5: Symbol mapper integrates seamlessly with all collectors."""
        
        # Test that all collectors can be instantiated with enhanced database manager
        collector_classes = [
            WatchlistCollector,
            OHLCVCollector,
            TopPoolsCollector,
            TradeCollector,
            DEXMonitoringCollector
        ]
        
        for collector_class in collector_classes:
            try:
                collector = collector_class(collection_config, mock_enhanced_db_manager)
                
                # Should have symbol mapper
                assert collector.symbol_mapper is not None
                assert isinstance(collector.symbol_mapper, IntegratedSymbolMapper)
                
                # Should be able to generate symbols
                symbol = collector.generate_symbol(sample_pool_mixed_case)
                assert symbol is not None
                assert len(symbol) > 0
                
            except Exception as e:
                pytest.fail(f"Failed to integrate symbol mapper with {collector_class.__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__])