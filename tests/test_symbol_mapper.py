"""
Tests for the SymbolMapper class.

This test suite verifies the case-insensitive symbol lookup functionality
and ensures all requirements are met.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from gecko_terminal_collector.qlib.symbol_mapper import (
    SymbolMapper, 
    PoolLookupResult, 
    SymbolMetadata
)
from gecko_terminal_collector.models.core import Pool


class TestSymbolMapper:
    """Test cases for SymbolMapper functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db_manager = Mock()
        self.symbol_mapper = SymbolMapper(self.db_manager)
        
        # Create test pools with mixed-case addresses
        self.pool_mixed_case = Pool(
            id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            name="Test Pool Mixed Case",
            dex_id="raydium",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000000"),
            created_at=datetime.utcnow()
        )
        
        self.pool_lowercase = Pool(
            id="solana_abcdef123456789",
            address="abcdef123456789",
            name="Test Pool Lowercase",
            dex_id="orca",
            base_token_id="token3",
            quote_token_id="token4",
            reserve_usd=Decimal("500000"),
            created_at=datetime.utcnow()
        )
    
    def test_generate_symbol_preserves_case(self):
        """Test that generate_symbol preserves original case from pool ID."""
        # Requirement 1.1: Symbol generation preserves original case
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        # Should preserve the mixed case from pool ID
        expected_symbol = "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert symbol == expected_symbol
        
        # Verify it's cached
        assert symbol in self.symbol_mapper._symbol_to_pool_cache
        assert self.symbol_mapper._symbol_to_pool_cache[symbol] == self.pool_mixed_case
    
    def test_generate_symbol_handles_special_characters(self):
        """Test that generate_symbol handles special characters properly."""
        pool_with_special_chars = Pool(
            id="solana-pool@with#special$chars%",
            address="test_address",
            name="Special Chars Pool",
            dex_id="test_dex",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.utcnow()
        )
        
        symbol = self.symbol_mapper.generate_symbol(pool_with_special_chars)
        
        # Special characters should be replaced with underscores
        # Trailing underscores should be removed
        expected_symbol = "solana_pool_with_special_chars"
        assert symbol == expected_symbol
        
        # Should not have duplicate underscores
        assert "__" not in symbol
    
    def test_generate_symbol_invalid_input(self):
        """Test generate_symbol with invalid input."""
        with pytest.raises(ValueError, match="Pool and pool.id are required"):
            self.symbol_mapper.generate_symbol(None)
        
        pool_no_id = Pool(
            id="",
            address="test",
            name="No ID Pool",
            dex_id="test",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.utcnow()
        )
        
        with pytest.raises(ValueError, match="Pool and pool.id are required"):
            self.symbol_mapper.generate_symbol(pool_no_id)
    
    def test_normalize_symbol(self):
        """Test normalize_symbol method."""
        # Requirement 1.4: Consistent lowercase conversion
        test_cases = [
            ("MixedCaseSymbol", "mixedcasesymbol"),
            ("UPPERCASE", "uppercase"),
            ("lowercase", "lowercase"),
            ("Mixed_With_Underscores", "mixed_with_underscores"),
            ("", ""),
        ]
        
        for input_symbol, expected in test_cases:
            result = self.symbol_mapper.normalize_symbol(input_symbol)
            assert result == expected
    
    def test_lookup_pool_exact_match(self):
        """Test lookup_pool with exact case match."""
        # Generate and cache a symbol
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        # Lookup with exact case should work
        result = self.symbol_mapper.lookup_pool(symbol)
        assert result == self.pool_mixed_case
    
    def test_lookup_pool_case_insensitive_match(self):
        """Test lookup_pool with case-insensitive fallback."""
        # Requirement 2.1: Case-insensitive lookup capability
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        # Lookup with different case should still work
        lowercase_symbol = symbol.lower()
        result = self.symbol_mapper.lookup_pool(lowercase_symbol)
        assert result == self.pool_mixed_case
        
        uppercase_symbol = symbol.upper()
        result = self.symbol_mapper.lookup_pool(uppercase_symbol)
        assert result == self.pool_mixed_case
    
    def test_lookup_pool_exact_match_priority(self):
        """Test that exact matches take priority over case-insensitive matches."""
        # Requirement 2.2: Exact match priority
        
        # Create two pools with symbols that would conflict in lowercase
        pool1 = Pool(
            id="Test_Symbol",
            address="addr1",
            name="Pool 1",
            dex_id="dex1",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.utcnow()
        )
        
        pool2 = Pool(
            id="test_symbol",  # Same as pool1 but lowercase
            address="addr2",
            name="Pool 2",
            dex_id="dex2",
            base_token_id="token3",
            quote_token_id="token4",
            reserve_usd=Decimal("2000"),
            created_at=datetime.utcnow()
        )
        
        # Generate symbols for both
        symbol1 = self.symbol_mapper.generate_symbol(pool1)
        symbol2 = self.symbol_mapper.generate_symbol(pool2)
        
        # Exact match should return the correct pool
        assert self.symbol_mapper.lookup_pool(symbol1) == pool1
        assert self.symbol_mapper.lookup_pool(symbol2) == pool2
    
    def test_lookup_pool_not_found(self):
        """Test lookup_pool when symbol is not found."""
        result = self.symbol_mapper.lookup_pool("nonexistent_symbol")
        assert result is None
    
    def test_lookup_pool_empty_input(self):
        """Test lookup_pool with empty input."""
        assert self.symbol_mapper.lookup_pool("") is None
        assert self.symbol_mapper.lookup_pool(None) is None
    
    def test_lookup_pool_detailed_exact_match(self):
        """Test lookup_pool_detailed with exact match."""
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        result = self.symbol_mapper.lookup_pool_detailed(symbol)
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool == self.pool_mixed_case
        assert result.matched_symbol == symbol
        assert result.lookup_method == "exact"
        assert result.confidence == 1.0
    
    def test_lookup_pool_detailed_case_insensitive_match(self):
        """Test lookup_pool_detailed with case-insensitive match."""
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        lowercase_symbol = symbol.lower()
        
        result = self.symbol_mapper.lookup_pool_detailed(lowercase_symbol)
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool == self.pool_mixed_case
        assert result.matched_symbol == symbol  # Should return original case
        assert result.lookup_method == "case_insensitive"
        assert result.confidence == 0.9
    
    def test_lookup_pool_detailed_not_found(self):
        """Test lookup_pool_detailed when symbol is not found."""
        result = self.symbol_mapper.lookup_pool_detailed("nonexistent")
        
        assert isinstance(result, PoolLookupResult)
        assert result.pool is None
        assert result.matched_symbol == "nonexistent"
        assert result.lookup_method == "not_found"
        assert result.confidence == 0.0
    
    def test_cache_management(self):
        """Test cache management functionality."""
        # Generate symbols to populate cache
        symbol1 = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        symbol2 = self.symbol_mapper.generate_symbol(self.pool_lowercase)
        
        # Check cache stats
        stats = self.symbol_mapper.get_cache_stats()
        assert stats['case_sensitive_entries'] == 2
        assert stats['normalized_entries'] == 2
        assert stats['metadata_entries'] == 2
        assert stats['cache_consistency'] is True
        
        # Test get_all_symbols
        all_symbols = self.symbol_mapper.get_all_symbols()
        assert symbol1 in all_symbols
        assert symbol2 in all_symbols
        assert len(all_symbols) == 2
        
        # Test clear_cache
        self.symbol_mapper.clear_cache()
        stats_after_clear = self.symbol_mapper.get_cache_stats()
        assert stats_after_clear['case_sensitive_entries'] == 0
        assert stats_after_clear['normalized_entries'] == 0
        assert stats_after_clear['metadata_entries'] == 0
    
    def test_symbol_metadata(self):
        """Test symbol metadata tracking."""
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        # Get metadata
        metadata = self.symbol_mapper.get_symbol_metadata(symbol)
        
        assert isinstance(metadata, SymbolMetadata)
        assert metadata.original_symbol == symbol
        assert metadata.normalized_symbol == symbol.lower()
        assert metadata.pool_id == self.pool_mixed_case.id
        assert metadata.case_sensitive is True
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.last_accessed, datetime)
    
    def test_symbol_variants(self):
        """Test get_symbol_variants functionality."""
        # Create pools with similar symbols but different cases
        pool_upper = Pool(
            id="TEST_SYMBOL",
            address="addr1",
            name="Upper Pool",
            dex_id="dex1",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.utcnow()
        )
        
        pool_lower = Pool(
            id="test_symbol",
            address="addr2",
            name="Lower Pool",
            dex_id="dex2",
            base_token_id="token3",
            quote_token_id="token4",
            reserve_usd=Decimal("2000"),
            created_at=datetime.utcnow()
        )
        
        # Generate symbols
        symbol_upper = self.symbol_mapper.generate_symbol(pool_upper)
        symbol_lower = self.symbol_mapper.generate_symbol(pool_lower)
        
        # Get variants for either symbol
        variants_upper = self.symbol_mapper.get_symbol_variants(symbol_upper)
        variants_lower = self.symbol_mapper.get_symbol_variants(symbol_lower)
        
        # Both should return the same set of variants
        assert set(variants_upper) == set(variants_lower)
        assert symbol_upper in variants_upper
        assert symbol_lower in variants_upper
        assert len(variants_upper) == 2
    
    def test_access_time_tracking(self):
        """Test that access times are tracked properly."""
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        
        # Get initial metadata
        initial_metadata = self.symbol_mapper.get_symbol_metadata(symbol)
        initial_access_time = initial_metadata.last_accessed
        
        # Perform lookup (should update access time)
        import time
        time.sleep(0.01)  # Small delay to ensure different timestamp
        self.symbol_mapper.lookup_pool(symbol)
        
        # Check that access time was updated
        updated_metadata = self.symbol_mapper.get_symbol_metadata(symbol)
        assert updated_metadata.last_accessed > initial_access_time
    
    def test_dual_caching_strategy(self):
        """Test that dual caching strategy works correctly."""
        symbol = self.symbol_mapper.generate_symbol(self.pool_mixed_case)
        normalized = self.symbol_mapper.normalize_symbol(symbol)
        
        # Verify both caches are populated
        assert symbol in self.symbol_mapper._symbol_to_pool_cache
        assert normalized in self.symbol_mapper._normalized_to_symbol_cache
        
        # Verify the mapping is correct
        assert self.symbol_mapper._normalized_to_symbol_cache[normalized] == symbol
        assert self.symbol_mapper._symbol_to_pool_cache[symbol] == self.pool_mixed_case
        
        # Verify case-insensitive lookup works through the dual cache
        result = self.symbol_mapper.lookup_pool(normalized)
        assert result == self.pool_mixed_case


class TestSymbolMapperIntegration:
    """Integration tests for SymbolMapper with database scenarios."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.db_manager = Mock()
        self.symbol_mapper = SymbolMapper(self.db_manager)
    
    def test_initialization_without_db_manager(self):
        """Test SymbolMapper initialization without database manager."""
        mapper = SymbolMapper()
        assert mapper.db_manager is None
        
        # Should still work for basic operations
        pool = Pool(
            id="test_pool",
            address="test_addr",
            name="Test Pool",
            dex_id="test_dex",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.utcnow()
        )
        
        symbol = mapper.generate_symbol(pool)
        result = mapper.lookup_pool(symbol)
        assert result == pool
    
    def test_database_fallback_no_db_manager(self):
        """Test database fallback when no db_manager is provided."""
        mapper = SymbolMapper()  # No db_manager
        
        # Should return None for unknown symbols
        result = mapper.lookup_pool("unknown_symbol")
        assert result is None
        
        # Detailed lookup should indicate no database method
        detailed_result = mapper.lookup_pool_detailed("unknown_symbol")
        assert detailed_result.lookup_method == "not_found"
        assert detailed_result.pool is None


if __name__ == "__main__":
    pytest.main([__file__])