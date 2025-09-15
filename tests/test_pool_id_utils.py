"""
Tests for pool ID utilities.
"""

import pytest
from gecko_terminal_collector.utils.pool_id_utils import PoolIDUtils


class TestPoolIDUtils:
    """Test cases for PoolIDUtils."""
    
    def test_parse_pool_id_with_network_prefix(self):
        """Test parsing pool ID with network prefix."""
        network, address = PoolIDUtils.parse_pool_id("solana_ABC123")
        assert network == "solana"
        assert address == "ABC123"
    
    def test_parse_pool_id_without_network_prefix(self):
        """Test parsing pool ID without network prefix."""
        network, address = PoolIDUtils.parse_pool_id("ABC123")
        assert network is None
        assert address == "ABC123"
    
    def test_parse_pool_id_unknown_network(self):
        """Test parsing pool ID with unknown network prefix."""
        network, address = PoolIDUtils.parse_pool_id("unknown_ABC123")
        assert network is None
        assert address == "unknown_ABC123"
    
    def test_ensure_network_prefix_add(self):
        """Test adding network prefix when missing."""
        result = PoolIDUtils.ensure_network_prefix("ABC123", "solana")
        assert result == "solana_ABC123"
    
    def test_ensure_network_prefix_keep_existing(self):
        """Test keeping existing correct network prefix."""
        result = PoolIDUtils.ensure_network_prefix("solana_ABC123", "solana")
        assert result == "solana_ABC123"
    
    def test_ensure_network_prefix_replace_incorrect(self):
        """Test replacing incorrect network prefix."""
        result = PoolIDUtils.ensure_network_prefix("ethereum_ABC123", "solana")
        assert result == "solana_ABC123"
    
    def test_remove_network_prefix(self):
        """Test removing network prefix."""
        result = PoolIDUtils.remove_network_prefix("solana_ABC123")
        assert result == "ABC123"
    
    def test_remove_network_prefix_no_prefix(self):
        """Test removing network prefix when none exists."""
        result = PoolIDUtils.remove_network_prefix("ABC123")
        assert result == "ABC123"
    
    def test_get_network_from_pool_id(self):
        """Test extracting network from pool ID."""
        network = PoolIDUtils.get_network_from_pool_id("solana_ABC123")
        assert network == "solana"
        
        network = PoolIDUtils.get_network_from_pool_id("ABC123")
        assert network is None
    
    def test_normalize_pool_id_with_default(self):
        """Test normalizing pool ID with default network."""
        result = PoolIDUtils.normalize_pool_id("ABC123", "solana")
        assert result == "solana_ABC123"
    
    def test_normalize_pool_id_keep_existing(self):
        """Test normalizing pool ID that already has network."""
        result = PoolIDUtils.normalize_pool_id("ethereum_ABC123", "solana")
        assert result == "ethereum_ABC123"
    
    def test_is_valid_pool_id_format_valid(self):
        """Test validation of valid pool ID formats."""
        assert PoolIDUtils.is_valid_pool_id_format("solana_ABC123")
        assert PoolIDUtils.is_valid_pool_id_format("ABC123")
        assert PoolIDUtils.is_valid_pool_id_format("ethereum_0x1234567890abcdef")
    
    def test_is_valid_pool_id_format_invalid(self):
        """Test validation of invalid pool ID formats."""
        assert not PoolIDUtils.is_valid_pool_id_format("")
        assert not PoolIDUtils.is_valid_pool_id_format("AB")  # Too short
        assert not PoolIDUtils.is_valid_pool_id_format("invalid_network_ABC123")
        assert not PoolIDUtils.is_valid_pool_id_format("ABC@123")  # Invalid chars
        assert not PoolIDUtils.is_valid_pool_id_format(None)


if __name__ == "__main__":
    pytest.main([__file__])