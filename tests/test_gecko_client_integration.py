"""
Integration tests for GeckoTerminal API client with real CSV fixtures.
"""

import pytest
from pathlib import Path

from gecko_terminal_collector.clients.gecko_client import MockGeckoTerminalClient


class TestMockClientWithRealFixtures:
    """Test mock client with actual CSV fixtures from specs directory."""
    
    @pytest.mark.asyncio
    async def test_mock_client_with_real_dex_fixtures(self):
        """Test mock client loads and uses real DEX fixtures."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_dexes_by_network
        dexes = await client.get_dexes_by_network("solana")
        
        # Should have loaded from specs/get_dexes_by_network.csv
        assert len(dexes) > 0
        
        # Check structure matches API format
        for dex in dexes:
            assert "id" in dex
            assert "type" in dex
            assert dex["type"] == "dex"
            assert "attributes" in dex
            assert "name" in dex["attributes"]
    
    @pytest.mark.asyncio
    async def test_mock_client_with_real_heaven_pools(self):
        """Test mock client loads and uses real Heaven pools fixtures."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_top_pools_by_network_dex for heaven
        pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        
        # Should have loaded from specs/get_top_pools_by_network_dex_heaven.csv
        assert "data" in pools
        assert len(pools["data"]) > 0
        
        # Check structure matches API format
        for pool in pools["data"]:
            assert "id" in pool
            assert "type" in pool
            assert pool["type"] == "pool"
            assert "attributes" in pool
            assert "relationships" in pool
            
            # Check required attributes
            attributes = pool["attributes"]
            assert "name" in attributes
            assert "address" in attributes
            assert "reserve_in_usd" in attributes
            
            # Check relationships
            relationships = pool["relationships"]
            assert "dex" in relationships
            assert "base_token" in relationships
            assert "quote_token" in relationships
    
    @pytest.mark.asyncio
    async def test_mock_client_with_real_pumpswap_pools(self):
        """Test mock client loads and uses real PumpSwap pools fixtures."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_top_pools_by_network_dex for pumpswap
        pools = await client.get_top_pools_by_network_dex("solana", "pumpswap")
        
        # Should have loaded from specs/get_top_pools_by_network_dex_pumpswap.csv
        assert "data" in pools
        
        # Even if empty, should have proper structure
        assert isinstance(pools["data"], list)
        
        if pools["data"]:
            # Check structure if data exists
            pool = pools["data"][0]
            assert "id" in pool
            assert "type" in pool
            assert pool["type"] == "pool"
    
    @pytest.mark.asyncio
    async def test_mock_client_with_real_ohlcv_fixtures(self):
        """Test mock client loads and uses real OHLCV fixtures."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_ohlcv_data
        ohlcv = await client.get_ohlcv_data("solana", "test_pool")
        
        # Should have loaded from specs/get_ohlcv.csv
        assert "data" in ohlcv
        assert ohlcv["data"]["id"] == "test_pool"
        assert "attributes" in ohlcv["data"]
        assert "ohlcv_list" in ohlcv["data"]["attributes"]
        
        # Check OHLCV data structure
        ohlcv_list = ohlcv["data"]["attributes"]["ohlcv_list"]
        if ohlcv_list:
            # Each OHLCV entry should have 6 elements: [timestamp, open, high, low, close, volume]
            for entry in ohlcv_list:
                assert len(entry) == 6
    
    @pytest.mark.asyncio
    async def test_mock_client_with_real_trades_fixtures(self):
        """Test mock client loads and uses real trades fixtures."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_trades
        trades = await client.get_trades("solana", "test_pool")
        
        # Should have loaded from specs/get_trades.csv
        assert "data" in trades
        assert isinstance(trades["data"], list)
        
        if trades["data"]:
            # Check trade structure
            trade = trades["data"][0]
            assert "id" in trade
            assert "type" in trade
            assert trade["type"] == "trade"
            assert "attributes" in trade
            
            # Check required trade attributes
            attributes = trade["attributes"]
            assert "block_number" in attributes
            assert "tx_hash" in attributes
            assert "from_token_amount" in attributes
            assert "to_token_amount" in attributes
    
    @pytest.mark.asyncio
    async def test_mock_client_handles_missing_fixtures(self):
        """Test mock client handles missing fixture files gracefully."""
        # Use non-existent directory
        client = MockGeckoTerminalClient("nonexistent_directory")
        
        # Should still work but return empty/default data
        dexes = await client.get_dexes_by_network("solana")
        assert isinstance(dexes, list)
        
        pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        assert "data" in pools
        assert isinstance(pools["data"], list)
    
    @pytest.mark.asyncio
    async def test_mock_client_multiple_pools_fixture(self):
        """Test mock client with multiple pools fixture."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_multiple_pools_by_network
        pools = await client.get_multiple_pools_by_network("solana", ["addr1", "addr2"])
        
        assert "data" in pools
        assert isinstance(pools["data"], list)
    
    @pytest.mark.asyncio
    async def test_mock_client_single_pool_fixture(self):
        """Test mock client with single pool fixture."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_pool_by_network_address
        pool = await client.get_pool_by_network_address("solana", "test_address")
        
        assert "data" in pool
        # data can be None if no matching pool found
    
    @pytest.mark.asyncio
    async def test_mock_client_token_info(self):
        """Test mock client token info method."""
        client = MockGeckoTerminalClient("specs")
        
        # Test get_token_info
        token = await client.get_token_info("solana", "test_token_address")
        
        assert "data" in token
        assert token["data"]["id"] == "test_token_address"
        assert token["data"]["type"] == "token"
        assert "attributes" in token["data"]
        
        # Check token attributes
        attributes = token["data"]["attributes"]
        assert "address" in attributes
        assert "name" in attributes
        assert "symbol" in attributes
        assert "decimals" in attributes


if __name__ == "__main__":
    pytest.main([__file__])