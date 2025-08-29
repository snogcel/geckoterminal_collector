# GeckoTerminal API Client

This module provides a robust wrapper around the `geckoterminal-py` SDK with additional features for production use.

## Features

- **Rate Limiting**: Configurable delays between API calls to respect rate limits
- **Retry Logic**: Exponential backoff retry mechanism for failed requests
- **Circuit Breaker**: Automatic failure protection to prevent cascading failures
- **Error Handling**: Comprehensive error handling with detailed logging
- **Mock Client**: Testing support with CSV fixture data
- **Async Support**: Full async/await support for high-performance applications

## Usage

### Real API Client

```python
import asyncio
from gecko_terminal_collector.clients import create_gecko_client
from gecko_terminal_collector.config.models import APIConfig, ErrorConfig

async def main():
    # Configure API settings
    api_config = APIConfig(
        rate_limit_delay=1.0,  # 1 second between calls
        timeout=30,
        max_concurrent=5
    )
    
    # Configure error handling
    error_config = ErrorConfig(
        max_retries=3,
        backoff_factor=2.0,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300
    )
    
    # Create client
    client = create_gecko_client(api_config, error_config, use_mock=False)
    
    # Use as async context manager for proper session handling
    async with client:
        # Get available networks
        networks = await client.get_networks()
        print(f"Found {len(networks)} networks")
        
        # Get DEXes for Solana
        dexes = await client.get_dexes_by_network("solana")
        print(f"Found {len(dexes)} DEXes on Solana")
        
        # Get top pools for a specific DEX
        pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        print(f"Found {len(pools['data'])} pools on Heaven DEX")
        
        # Get OHLCV data for a pool
        if pools['data']:
            pool_id = pools['data'][0]['id']
            ohlcv = await client.get_ohlcv_data("solana", pool_id, timeframe="hour")
            print(f"Retrieved OHLCV data for pool {pool_id}")

asyncio.run(main())
```

### Mock Client for Testing

```python
import asyncio
from gecko_terminal_collector.clients import create_gecko_client
from gecko_terminal_collector.config.models import APIConfig, ErrorConfig

async def test_with_mock():
    # Configuration (not used by mock but required for interface)
    api_config = APIConfig()
    error_config = ErrorConfig()
    
    # Create mock client using CSV fixtures
    client = create_gecko_client(
        api_config, 
        error_config, 
        use_mock=True, 
        fixtures_path="specs"
    )
    
    # Mock client doesn't need context manager
    # Get data from CSV fixtures
    dexes = await client.get_dexes_by_network("solana")
    pools = await client.get_top_pools_by_network_dex("solana", "heaven")
    ohlcv = await client.get_ohlcv_data("solana", "test_pool")
    
    print(f"Mock client loaded {len(dexes)} DEXes from CSV")
    print(f"Mock client loaded {len(pools['data'])} pools from CSV")

asyncio.run(test_with_mock())
```

## API Methods

### Network and DEX Information

- `get_networks()` - Get all available networks
- `get_dexes_by_network(network)` - Get DEXes available on a network

### Pool Information

- `get_top_pools_by_network(network, page=1)` - Get top pools by network
- `get_top_pools_by_network_dex(network, dex, page=1)` - Get top pools by network and DEX
- `get_multiple_pools_by_network(network, addresses)` - Get multiple pools by addresses
- `get_pool_by_network_address(network, address)` - Get specific pool by address

### Market Data

- `get_ohlcv_data(network, pool_address, timeframe="hour", ...)` - Get OHLCV data
- `get_trades(network, pool_address)` - Get recent trades

### Token Information

- `get_token_info(network, token_address)` - Get token information

## Configuration

### API Configuration

```python
api_config = APIConfig(
    base_url="https://api.geckoterminal.com/api/v2",  # API base URL
    timeout=30,                                        # Request timeout in seconds
    max_concurrent=5,                                  # Max concurrent requests
    rate_limit_delay=1.0                              # Delay between requests in seconds
)
```

### Error Handling Configuration

```python
error_config = ErrorConfig(
    max_retries=3,                    # Maximum retry attempts
    backoff_factor=2.0,               # Exponential backoff multiplier
    circuit_breaker_threshold=5,      # Failures before circuit opens
    circuit_breaker_timeout=300       # Circuit breaker timeout in seconds
)
```

## Rate Limiting

The client includes built-in rate limiting to respect API limits:

- Configurable delay between requests
- Automatic backoff on rate limit errors
- Circuit breaker protection for sustained failures

## Error Handling

The client provides robust error handling:

1. **Retry Logic**: Failed requests are automatically retried with exponential backoff
2. **Circuit Breaker**: Prevents cascading failures by temporarily stopping requests after too many failures
3. **Detailed Logging**: All errors are logged with context for debugging
4. **Graceful Degradation**: System continues operating even when some requests fail

## Testing

The mock client allows testing without making real API calls:

- Loads data from CSV fixtures in the `specs` directory
- Returns data in the same format as the real API
- Supports all the same methods as the real client
- Perfect for unit tests and development

## CSV Fixtures

The mock client expects CSV files in the following format:

- `get_dexes_by_network.csv` - DEX information
- `get_top_pools_by_network_dex_heaven.csv` - Heaven DEX pools
- `get_top_pools_by_network_dex_pumpswap.csv` - PumpSwap DEX pools
- `get_ohlcv.csv` - OHLCV data
- `get_trades.csv` - Trade data
- `get_multiple_pools_by_network.csv` - Multiple pools data
- `get_pool_by_network_address.csv` - Single pool data
- `watchlist.csv` - Watchlist data

## Requirements

- Python 3.8+
- `geckoterminal-py>=0.2.5`
- `aiohttp>=3.8.0`
- `asyncio` (built-in)

## Thread Safety

The client is designed for async/await usage and is not thread-safe. Use separate client instances for different threads or use proper async coordination.