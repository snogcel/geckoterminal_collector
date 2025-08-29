"""
Tests for GeckoTerminal API client wrapper.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from gecko_terminal_collector.clients.gecko_client import (
    GeckoTerminalClient, 
    MockGeckoTerminalClient,
    RateLimiter,
    CircuitBreaker
)
from gecko_terminal_collector.clients.factory import create_gecko_client, create_async_gecko_client
from gecko_terminal_collector.config.models import APIConfig, ErrorConfig


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """Test that rate limiter enforces minimum delay between calls."""
        limiter = RateLimiter(delay=0.1)
        
        start_time = asyncio.get_event_loop().time()
        await limiter.wait()
        
        mid_time = asyncio.get_event_loop().time()
        await limiter.wait()
        
        end_time = asyncio.get_event_loop().time()
        
        # First call should be immediate
        assert mid_time - start_time < 0.05
        
        # Second call should be delayed (allow small tolerance for timing)
        assert end_time - mid_time >= 0.09


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        assert cb.can_execute() is True
        assert cb.state == "closed"
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        
        # Record failures up to threshold
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state == "open"
        assert cb.can_execute() is False
    
    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets failure count on success."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        
        # Record some failures
        cb.record_failure()
        cb.record_failure()
        
        # Record success
        cb.record_success()
        
        assert cb.failure_count == 0
        assert cb.state == "closed"


class TestGeckoTerminalClient:
    """Test real GeckoTerminal API client."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_config = APIConfig(
            base_url="https://api.geckoterminal.com/api/v2",
            timeout=30,
            max_concurrent=5,
            rate_limit_delay=0.01  # Fast for testing
        )
        
        self.error_config = ErrorConfig(
            max_retries=2,
            backoff_factor=1.5,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initializes correctly."""
        client = GeckoTerminalClient(self.api_config, self.error_config)
        
        assert client.api_config == self.api_config
        assert client.error_config == self.error_config
        assert client.rate_limiter is not None
        assert client.circuit_breaker is not None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client works as async context manager."""
        async with GeckoTerminalClient(self.api_config, self.error_config) as client:
            assert client._session is not None
        
        # Session should be closed after context exit
        assert client._session.closed
    
    @pytest.mark.asyncio
    @patch('gecko_terminal_collector.clients.gecko_client.GeckoTerminalAsyncClient')
    async def test_get_networks_with_retry(self, mock_sdk):
        """Test get_networks with retry logic."""
        # Mock SDK client
        mock_instance = AsyncMock()
        mock_sdk.return_value = mock_instance
        
        # Mock successful response
        expected_response = [{"id": "solana", "type": "network"}]
        mock_instance.get_networks.return_value = expected_response
        
        client = GeckoTerminalClient(self.api_config, self.error_config)
        result = await client.get_networks()
        
        assert result == expected_response
        mock_instance.get_networks.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('gecko_terminal_collector.clients.gecko_client.GeckoTerminalAsyncClient')
    async def test_retry_logic_on_failure(self, mock_sdk):
        """Test retry logic when API calls fail."""
        # Mock SDK client
        mock_instance = AsyncMock()
        mock_sdk.return_value = mock_instance
        
        # Mock failure then success
        mock_instance.get_networks.side_effect = [
            Exception("API Error"),
            [{"id": "solana", "type": "network"}]
        ]
        
        client = GeckoTerminalClient(self.api_config, self.error_config)
        result = await client.get_networks()
        
        assert result == [{"id": "solana", "type": "network"}]
        assert mock_instance.get_networks.call_count == 2
    
    @pytest.mark.asyncio
    @patch('gecko_terminal_collector.clients.gecko_client.GeckoTerminalAsyncClient')
    async def test_retry_exhaustion(self, mock_sdk):
        """Test behavior when all retries are exhausted."""
        # Mock SDK client
        mock_instance = AsyncMock()
        mock_sdk.return_value = mock_instance
        
        # Mock consistent failures
        mock_instance.get_networks.side_effect = Exception("Persistent API Error")
        
        client = GeckoTerminalClient(self.api_config, self.error_config)
        
        with pytest.raises(Exception, match="Persistent API Error"):
            await client.get_networks()
        
        # Should try max_retries + 1 times
        assert mock_instance.get_networks.call_count == self.error_config.max_retries + 1
    
    @pytest.mark.asyncio
    @patch('gecko_terminal_collector.clients.gecko_client.GeckoTerminalAsyncClient')
    async def test_get_dexes_by_network(self, mock_sdk):
        """Test get_dexes_by_network method."""
        mock_instance = AsyncMock()
        mock_sdk.return_value = mock_instance
        
        expected_response = [{"id": "heaven", "type": "dex"}]
        mock_instance.get_dexes_by_network.return_value = expected_response
        
        client = GeckoTerminalClient(self.api_config, self.error_config)
        result = await client.get_dexes_by_network("solana")
        
        assert result == expected_response
        mock_instance.get_dexes_by_network.assert_called_once_with("solana")
    
    @pytest.mark.asyncio
    @patch('gecko_terminal_collector.clients.gecko_client.GeckoTerminalAsyncClient')
    async def test_get_multiple_pools_by_network(self, mock_sdk):
        """Test get_multiple_pools_by_network method."""
        mock_instance = AsyncMock()
        mock_sdk.return_value = mock_instance
        
        expected_response = {"data": [{"id": "pool1", "type": "pool"}]}
        mock_instance.get_multiple_pools_by_network.return_value = expected_response
        
        client = GeckoTerminalClient(self.api_config, self.error_config)
        addresses = ["addr1", "addr2"]
        result = await client.get_multiple_pools_by_network("solana", addresses)
        
        assert result == expected_response
        mock_instance.get_multiple_pools_by_network.assert_called_once_with("solana", "addr1,addr2")


class TestMockGeckoTerminalClient:
    """Test mock GeckoTerminal API client."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary test fixtures directory
        self.fixtures_path = Path("test_fixtures")
        self.fixtures_path.mkdir(exist_ok=True)
        
        # Create sample CSV files
        self._create_test_fixtures()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if self.fixtures_path.exists():
            shutil.rmtree(self.fixtures_path)
    
    def _create_test_fixtures(self):
        """Create test CSV fixtures."""
        # DEX fixture
        dex_csv = self.fixtures_path / "get_dexes_by_network.csv"
        with open(dex_csv, 'w') as f:
            f.write("id,type,name\n")
            f.write("heaven,dex,Heaven\n")
            f.write("pumpswap,dex,PumpSwap\n")
        
        # Heaven pools fixture
        heaven_csv = self.fixtures_path / "get_top_pools_by_network_dex_heaven.csv"
        with open(heaven_csv, 'w') as f:
            f.write("id,type,name,address,base_token_price_usd,reserve_in_usd,dex_id,base_token_id,quote_token_id\n")
            f.write("pool1,pool,Test Pool 1,addr1,1.5,10000,heaven,token1,token2\n")
            f.write("pool2,pool,Test Pool 2,addr2,2.5,20000,heaven,token3,token4\n")
        
        # OHLCV fixture
        ohlcv_csv = self.fixtures_path / "get_ohlcv.csv"
        with open(ohlcv_csv, 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("1693440000,1.0,1.1,0.9,1.05,1000\n")
            f.write("1693443600,1.05,1.15,1.0,1.1,1500\n")
        
        # Trades fixture
        trades_csv = self.fixtures_path / "get_trades.csv"
        with open(trades_csv, 'w') as f:
            f.write("id,block_number,tx_hash,from_token_amount,to_token_amount,price_usd,side\n")
            f.write("trade1,12345,0xabc123,100,105,1.05,buy\n")
            f.write("trade2,12346,0xdef456,200,190,0.95,sell\n")
    
    @pytest.mark.asyncio
    async def test_mock_client_initialization(self):
        """Test mock client initializes and loads fixtures."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        
        assert "dexes" in client.fixtures
        assert "heaven_pools" in client.fixtures
        assert "ohlcv" in client.fixtures
        assert "trades" in client.fixtures
    
    @pytest.mark.asyncio
    async def test_mock_get_networks(self):
        """Test mock get_networks method."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        result = await client.get_networks()
        
        assert len(result) == 1
        assert result[0]["id"] == "solana"
        assert result[0]["type"] == "network"
    
    @pytest.mark.asyncio
    async def test_mock_get_dexes_by_network(self):
        """Test mock get_dexes_by_network method."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        result = await client.get_dexes_by_network("solana")
        
        assert len(result) == 2
        assert result[0]["id"] == "heaven"
        assert result[1]["id"] == "pumpswap"
    
    @pytest.mark.asyncio
    async def test_mock_get_top_pools_by_network_dex(self):
        """Test mock get_top_pools_by_network_dex method."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        result = await client.get_top_pools_by_network_dex("solana", "heaven")
        
        assert "data" in result
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "pool1"
        assert result["data"][0]["attributes"]["name"] == "Test Pool 1"
    
    @pytest.mark.asyncio
    async def test_mock_get_ohlcv_data(self):
        """Test mock get_ohlcv_data method."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        result = await client.get_ohlcv_data("solana", "pool1")
        
        assert "data" in result
        assert result["data"]["id"] == "pool1"
        assert "ohlcv_list" in result["data"]["attributes"]
        assert len(result["data"]["attributes"]["ohlcv_list"]) == 2
    
    @pytest.mark.asyncio
    async def test_mock_get_trades(self):
        """Test mock get_trades method."""
        client = MockGeckoTerminalClient(str(self.fixtures_path))
        result = await client.get_trades("solana", "pool1")
        
        assert "data" in result
        assert len(result["data"]) == 2
        assert result["data"][0]["attributes"]["block_number"] == 12345


class TestClientFactory:
    """Test client factory functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_config = APIConfig()
        self.error_config = ErrorConfig()
    
    def test_create_gecko_client_real(self):
        """Test factory creates real client."""
        client = create_gecko_client(
            self.api_config, 
            self.error_config, 
            use_mock=False
        )
        
        assert isinstance(client, GeckoTerminalClient)
    
    def test_create_gecko_client_mock(self):
        """Test factory creates mock client."""
        client = create_gecko_client(
            self.api_config, 
            self.error_config, 
            use_mock=True
        )
        
        assert isinstance(client, MockGeckoTerminalClient)
    
    @pytest.mark.asyncio
    async def test_create_async_gecko_client(self):
        """Test async factory function."""
        client = await create_async_gecko_client(
            self.api_config, 
            self.error_config, 
            use_mock=True
        )
        
        assert isinstance(client, MockGeckoTerminalClient)


if __name__ == "__main__":
    pytest.main([__file__])