"""
Tests for the IntegratedSymbolMapper class.

This test suite verifies the integration of the symbol mapper with the
enhanced database manager and ensures all requirements are met.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.qlib.integrated_symbol_mapper import (
    IntegratedSymbolMapper, 
    IntegratedSymbolMetadata
)
from gecko_terminal_collector.qlib.symbol_mapper import PoolLookupResult
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.models.core import Pool


class TestIntegratedSymbolMapper:
    """Test cases for IntegratedSymbolMapper functionality."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        mock = AsyncMock(spec=EnhancedDatabaseManager)
        # Add the methods that are called in the tests
        mock.get_all_pools = AsyncMock()
        mock.get_pool_by_address = AsyncMock()
        mock.search_pools_by_name_or_id = AsyncMock()
        return mock
    
    @pytest.fixture
    def integrated_mapper(self, mock_enhanced_db_manager):
        """Create IntegratedSymbolMapper instance with mock database."""
        return IntegratedSymbolMapper(mock_enhanced_db_manager)
    
    @pytest.fixture
    def sample_pools(self):
        """Create sample pools for testing."""
        return [
            Pool(
                id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
                address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
                name="Test Pool 1",
                dex_id="raydium",
                base_token_id="token1",
                quote_token_id="token2",
                reserve_usd=Decimal("1000000"),
                created_at=datetime.utcnow()
            ),
            Pool(
                id="solana_abcdef123456789",
                address="abcdef123456789",
                name="Test Pool 2",
                dex_id="orca",
                base_token_id="token3",
                quote_token_id="token4",
                reserve_usd=Decimal("500000"),
                created_at=datetime.utcnow()
            )
        ]
    
    def test_initialization(self, mock_enhanced_db_manager):
        """Test IntegratedSymbolMapper initialization."""
        mapper = IntegratedSymbolMapper(mock_enhanced_db_manager)
        
        assert mapper.enhanced_db_manager == mock_enhanced_db_manager
        assert mapper.db_manager == mock_enhanced_db_manager
        assert isinstance(mapper._integrated_metadata, dict)
        assert mapper._cache_hits == 0
        assert mapper._cache_misses == 0
        assert mapper._database_lookups == 0
    
    @pytest.mark.asyncio
    async def test_populate_cache_from_database(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test populating cache from database."""
        # Setup mock
        mock_enhanced_db_manager.get_all_pools.return_value = sample_pools
        
        # Test
        symbols_loaded = await integrated_mapper.populate_cache_from_database()
        
        # Assertions
        assert symbols_loaded == 2
        mock_enhanced_db_manager.get_all_pools.assert_called_once_with(limit=None)
        
        # Check that symbols are in cache
        assert len(integrated_mapper._symbol_to_pool_cache) == 2
        assert len(integrated_mapper._integrated_metadata) == 2
        
        # Check that all cached symbols are marked as database cached
        for symbol, metadata in integrated_mapper._integrated_metadata.items():
            assert metadata.database_cached is True
            assert symbol in integrated_mapper._symbol_to_pool_cache
    
    @pytest.mark.asyncio
    async def test_populate_cache_with_limit(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test populating cache with limit."""
        # Setup mock
        mock_enhanced_db_manager.get_all_pools.return_value = sample_pools[:1]
        
        # Test
        symbols_loaded = await integrated_mapper.populate_cache_from_database(limit=1)
        
        # Assertions
        assert symbols_loaded == 1
        mock_enhanced_db_manager.get_all_pools.assert_called_once_with(limit=1)
    
    @pytest.mark.asyncio
    async def test_lookup_pool_with_fallback_cache_hit(self, integrated_mapper, sample_pools):
        """Test lookup with cache hit."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test
        result = await integrated_mapper.lookup_pool_with_fallback(symbol)
        
        # Assertions
        assert result == pool
        assert integrated_mapper._cache_hits == 1
        assert integrated_mapper._cache_misses == 0
    
    @pytest.mark.asyncio
    async def test_lookup_pool_with_fallback_case_insensitive(self, integrated_mapper, sample_pools):
        """Test lookup with case-insensitive match."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test with different case
        lowercase_symbol = symbol.lower()
        result = await integrated_mapper.lookup_pool_with_fallback(lowercase_symbol)
        
        # Assertions
        assert result == pool
        assert integrated_mapper._cache_hits == 1
    
    @pytest.mark.asyncio
    async def test_lookup_pool_with_fallback_database_lookup(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test lookup with database fallback."""
        pool = sample_pools[0]
        symbol = "unknown_symbol"
        
        # Setup mock for database lookup
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Test
        result = await integrated_mapper.lookup_pool_with_fallback(symbol)
        
        # Assertions
        assert result == pool
        assert integrated_mapper._cache_misses == 1
        assert integrated_mapper._database_lookups == 1
        
        # Check that pool was added to cache
        generated_symbol = integrated_mapper.generate_symbol(pool)
        assert generated_symbol in integrated_mapper._symbol_to_pool_cache
    
    @pytest.mark.asyncio
    async def test_lookup_pool_detailed_enhanced(self, integrated_mapper, sample_pools):
        """Test detailed lookup with enhanced metadata."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test exact match
        result = await integrated_mapper.lookup_pool_detailed_enhanced(symbol)
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool == pool
        assert result.matched_symbol == symbol
        assert result.lookup_method == "exact_cache"
        assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_lookup_pool_detailed_enhanced_case_insensitive(self, integrated_mapper, sample_pools):
        """Test detailed lookup with case-insensitive match."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test with different case
        lowercase_symbol = symbol.lower()
        result = await integrated_mapper.lookup_pool_detailed_enhanced(lowercase_symbol)
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool == pool
        assert result.matched_symbol == symbol  # Should return original case
        assert result.lookup_method == "case_insensitive_cache"
        assert result.confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_lookup_pool_detailed_enhanced_database_fallback(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test detailed lookup with database fallback."""
        pool = sample_pools[0]
        symbol = "unknown_symbol"
        
        # Setup mock for database lookup
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Test
        result = await integrated_mapper.lookup_pool_detailed_enhanced(symbol)
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool == pool
        assert result.lookup_method == "database_fallback"
        assert result.confidence == 0.8
    
    @pytest.mark.asyncio
    async def test_enhanced_database_lookup_direct_pool_id(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test enhanced database lookup with direct pool ID."""
        pool = sample_pools[0]
        symbol = pool.id
        
        # Setup mock
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Test
        result = await integrated_mapper._enhanced_database_lookup(symbol)
        
        # Assertions
        assert result == pool
        mock_enhanced_db_manager.get_pool.assert_called_once_with(symbol)
        
        # Check that pool was added to cache
        generated_symbol = integrated_mapper.generate_symbol(pool)
        assert generated_symbol in integrated_mapper._symbol_to_pool_cache
    
    @pytest.mark.asyncio
    async def test_enhanced_database_lookup_by_address(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test enhanced database lookup by pool address."""
        pool = sample_pools[0]
        symbol = pool.address
        
        # Setup mock - first call returns None, second returns pool
        mock_enhanced_db_manager.get_pool.return_value = None
        mock_enhanced_db_manager.get_pool_by_address.return_value = pool
        
        # Test
        result = await integrated_mapper._enhanced_database_lookup(symbol)
        
        # Assertions
        assert result == pool
        mock_enhanced_db_manager.get_pool.assert_called_once_with(symbol)
        mock_enhanced_db_manager.get_pool_by_address.assert_called_once_with(symbol)
    
    @pytest.mark.asyncio
    async def test_enhanced_database_lookup_fuzzy_search(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test enhanced database lookup with fuzzy search."""
        pool = sample_pools[0]
        symbol = "test_symbol"
        
        # Setup mock - first two calls return None/empty, third returns pools
        mock_enhanced_db_manager.get_pool.return_value = None
        mock_enhanced_db_manager.get_pool_by_address.return_value = None
        mock_enhanced_db_manager.search_pools_by_name_or_id.return_value = sample_pools
        
        # Mock the parent's generate_symbol to return our test symbol for the first pool
        with patch('gecko_terminal_collector.qlib.symbol_mapper.SymbolMapper.generate_symbol', return_value=symbol):
            # Test
            result = await integrated_mapper._enhanced_database_lookup(symbol)
        
        # Assertions
        assert result == pool
        mock_enhanced_db_manager.search_pools_by_name_or_id.assert_called_once_with(symbol, limit=10)
    
    @pytest.mark.asyncio
    async def test_bulk_populate_symbols(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test bulk symbol population."""
        pool_ids = [pool.id for pool in sample_pools]
        
        # Setup mock
        mock_enhanced_db_manager.get_pool.side_effect = lambda pool_id: next(
            (pool for pool in sample_pools if pool.id == pool_id), None
        )
        
        # Test
        symbol_mapping = await integrated_mapper.bulk_populate_symbols(pool_ids)
        
        # Assertions
        assert len(symbol_mapping) == 2
        for pool_id in pool_ids:
            assert pool_id in symbol_mapping
            # Verify the symbol was generated correctly
            pool = next(pool for pool in sample_pools if pool.id == pool_id)
            expected_symbol = integrated_mapper.generate_symbol(pool)
            assert symbol_mapping[pool_id] == expected_symbol
    
    @pytest.mark.asyncio
    async def test_refresh_symbol_cache(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test symbol cache refresh."""
        # Pre-populate cache with old data
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Make the metadata old
        old_time = datetime.utcnow() - timedelta(hours=25)
        integrated_mapper._integrated_metadata[symbol].last_accessed = old_time
        
        # Setup mock for repopulation
        mock_enhanced_db_manager.get_all_pools.return_value = sample_pools
        
        # Test
        refreshed_count = await integrated_mapper.refresh_symbol_cache(max_age_hours=24)
        
        # Assertions
        assert refreshed_count == 2  # Should repopulate both pools
        # Old symbol should be removed and new ones added
        assert len(integrated_mapper._symbol_to_pool_cache) == 2
    
    def test_get_performance_metrics(self, integrated_mapper, sample_pools):
        """Test performance metrics collection."""
        # Simulate some cache activity
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        integrated_mapper._cache_hits = 5
        integrated_mapper._cache_misses = 2
        integrated_mapper._database_lookups = 1
        
        # Update hit count for the symbol
        integrated_mapper._integrated_metadata[symbol].cache_hit_count = 3
        
        # Test
        metrics = integrated_mapper.get_performance_metrics()
        
        # Assertions
        assert metrics['cache_hits'] == 5
        assert metrics['cache_misses'] == 2
        assert metrics['database_lookups'] == 1
        assert metrics['cache_hit_rate'] == 5/7  # 5 hits out of 7 total lookups
        assert metrics['total_cached_symbols'] == 1
        assert len(metrics['most_accessed_symbols']) <= 5
    
    def test_get_integrated_metadata(self, integrated_mapper, sample_pools):
        """Test getting integrated metadata."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test
        metadata = integrated_mapper.get_integrated_metadata(symbol)
        
        # Assertions
        assert isinstance(metadata, IntegratedSymbolMetadata)
        assert metadata.original_symbol == symbol
        assert metadata.pool_id == pool.id
        assert metadata.database_cached is False  # Not loaded from database
    
    @pytest.mark.asyncio
    async def test_validate_cache_consistency(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test cache consistency validation."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Setup mock - pool still exists in database
        mock_enhanced_db_manager.get_pool.return_value = pool
        
        # Test
        validation_results = await integrated_mapper.validate_cache_consistency()
        
        # Assertions
        assert validation_results['is_consistent'] is True
        assert validation_results['total_symbols_checked'] == 1
        assert validation_results['database_mismatches'] == 0
        assert len(validation_results['inconsistencies']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_cache_consistency_with_mismatches(self, integrated_mapper, mock_enhanced_db_manager, sample_pools):
        """Test cache consistency validation with database mismatches."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Setup mock - pool no longer exists in database
        mock_enhanced_db_manager.get_pool.return_value = None
        
        # Test
        validation_results = await integrated_mapper.validate_cache_consistency()
        
        # Assertions
        assert validation_results['is_consistent'] is False
        assert validation_results['total_symbols_checked'] == 1
        assert validation_results['database_mismatches'] == 1
        assert len(validation_results['inconsistencies']) == 1
        assert validation_results['inconsistencies'][0]['issue'] == 'Pool no longer exists in database'
    
    def test_clear_cache(self, integrated_mapper, sample_pools):
        """Test clearing cache including integrated metadata."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        integrated_mapper._cache_hits = 5
        integrated_mapper._cache_misses = 2
        
        # Test
        integrated_mapper.clear_cache()
        
        # Assertions
        assert len(integrated_mapper._symbol_to_pool_cache) == 0
        assert len(integrated_mapper._normalized_to_symbol_cache) == 0
        assert len(integrated_mapper._integrated_metadata) == 0
        assert integrated_mapper._cache_hits == 0
        assert integrated_mapper._cache_misses == 0
        assert integrated_mapper._database_lookups == 0
    
    def test_update_cache_hit_count(self, integrated_mapper, sample_pools):
        """Test updating cache hit count."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        # Test
        integrated_mapper._update_cache_hit_count(symbol)
        integrated_mapper._update_cache_hit_count(symbol)
        
        # Assertions
        metadata = integrated_mapper._integrated_metadata[symbol]
        assert metadata.cache_hit_count == 2
    
    def test_update_access_time(self, integrated_mapper, sample_pools):
        """Test updating access time."""
        # Pre-populate cache
        pool = sample_pools[0]
        symbol = integrated_mapper.generate_symbol(pool)
        
        original_time = integrated_mapper._integrated_metadata[symbol].last_accessed
        
        # Wait a bit and update
        import time
        time.sleep(0.01)
        integrated_mapper._update_access_time(symbol)
        
        # Assertions
        updated_time = integrated_mapper._integrated_metadata[symbol].last_accessed
        assert updated_time > original_time


class TestIntegratedSymbolMapperRequirements:
    """Test cases specifically for requirement validation."""
    
    @pytest.fixture
    def mock_enhanced_db_manager(self):
        """Create mock enhanced database manager."""
        mock = AsyncMock(spec=EnhancedDatabaseManager)
        # Add the methods that are called in the tests
        mock.get_all_pools = AsyncMock()
        mock.get_pool_by_address = AsyncMock()
        mock.search_pools_by_name_or_id = AsyncMock()
        return mock
    
    @pytest.fixture
    def integrated_mapper(self, mock_enhanced_db_manager):
        """Create IntegratedSymbolMapper instance with mock database."""
        return IntegratedSymbolMapper(mock_enhanced_db_manager)
    
    @pytest.fixture
    def sample_pool_mixed_case(self):
        """Create sample pool with mixed case address."""
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
    
    def test_requirement_5_1_symbol_generation_preserves_case(self, integrated_mapper, sample_pool_mixed_case):
        """Test Requirement 5.1: Symbol generation preserves original case."""
        symbol = integrated_mapper.generate_symbol(sample_pool_mixed_case)
        
        # Should preserve the mixed case from pool ID
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
        
        # Verify it contains both upper and lower case characters
        assert any(c.isupper() for c in symbol)
        assert any(c.islower() for c in symbol)
    
    @pytest.mark.asyncio
    async def test_requirement_5_2_case_insensitive_lookup(self, integrated_mapper, sample_pool_mixed_case):
        """Test Requirement 5.2: Case-insensitive lookup support."""
        # Generate and cache symbol
        symbol = integrated_mapper.generate_symbol(sample_pool_mixed_case)
        
        # Test case-insensitive lookup
        lowercase_result = await integrated_mapper.lookup_pool_with_fallback(symbol.lower())
        uppercase_result = await integrated_mapper.lookup_pool_with_fallback(symbol.upper())
        
        assert lowercase_result == sample_pool_mixed_case
        assert uppercase_result == sample_pool_mixed_case
    
    @pytest.mark.asyncio
    async def test_requirement_5_3_bidirectional_compatibility(self, integrated_mapper, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test Requirement 5.3: Bidirectional symbol mapping compatibility."""
        # Generate symbol from pool
        symbol = integrated_mapper.generate_symbol(sample_pool_mixed_case)
        
        # Should be able to look up pool from symbol
        result = await integrated_mapper.lookup_pool_with_fallback(symbol)
        assert result == sample_pool_mixed_case
        
        # Should be able to generate the same symbol from the retrieved pool
        regenerated_symbol = integrated_mapper.generate_symbol(result)
        assert regenerated_symbol == symbol
    
    @pytest.mark.asyncio
    async def test_requirement_5_4_external_system_mapping(self, integrated_mapper, mock_enhanced_db_manager, sample_pool_mixed_case):
        """Test Requirement 5.4: External system lowercase symbol mapping."""
        # Generate symbol
        symbol = integrated_mapper.generate_symbol(sample_pool_mixed_case)
        
        # Setup mock for database lookup to simulate external system providing lowercase
        mock_enhanced_db_manager.get_pool.return_value = sample_pool_mixed_case
        
        # Test that lowercase symbol from external system maps correctly
        lowercase_symbol = symbol.lower()
        result = await integrated_mapper.lookup_pool_with_fallback(lowercase_symbol)
        
        assert result == sample_pool_mixed_case
        
        # Verify the original case is preserved in the mapping
        detailed_result = await integrated_mapper.lookup_pool_detailed_enhanced(lowercase_symbol)
        assert detailed_result.matched_symbol == symbol  # Should return original case
    
    @pytest.mark.asyncio
    async def test_requirement_5_5_seamless_collector_integration(self, integrated_mapper, sample_pool_mixed_case):
        """Test Requirement 5.5: Seamless integration with existing collectors."""
        # Test that the symbol mapper works with the standard collector interface
        symbol = integrated_mapper.generate_symbol(sample_pool_mixed_case)
        
        # Verify symbol is cached and accessible
        assert symbol in integrated_mapper._symbol_to_pool_cache
        assert integrated_mapper._symbol_to_pool_cache[symbol] == sample_pool_mixed_case
        
        # Verify case-insensitive access works
        normalized = integrated_mapper.normalize_symbol(symbol)
        assert normalized in integrated_mapper._normalized_to_symbol_cache
        assert integrated_mapper._normalized_to_symbol_cache[normalized] == symbol
        
        # Test performance metrics are tracked
        metrics = integrated_mapper.get_performance_metrics()
        assert 'total_cached_symbols' in metrics
        assert metrics['total_cached_symbols'] >= 1


if __name__ == "__main__":
    pytest.main([__file__])