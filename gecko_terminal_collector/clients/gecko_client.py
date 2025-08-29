"""
GeckoTerminal API client wrapper with rate limiting, retry logic, and error handling.
"""

import asyncio
import csv
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

import aiohttp
from geckoterminal_py import GeckoTerminalAsyncClient

from ..config.models import APIConfig, ErrorConfig
from ..models.core import Pool, Token, OHLCVRecord, TradeRecord


logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API calls with configurable delay."""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last_call = 0.0
    
    async def wait(self):
        """Wait if necessary to respect rate limits."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_call
        
        if time_since_last < self.delay:
            await asyncio.sleep(self.delay - time_since_last)
        
        self.last_call = asyncio.get_event_loop().time()


class CircuitBreaker:
    """Circuit breaker pattern for API failure protection."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class BaseGeckoClient(ABC):
    """Abstract base class for GeckoTerminal clients."""
    
    @abstractmethod
    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get available networks."""
        pass
    
    @abstractmethod
    async def get_dexes_by_network(self, network: str) -> List[Dict[str, Any]]:
        """Get DEXes available on a network."""
        pass
    
    @abstractmethod
    async def get_top_pools_by_network(self, network: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network."""
        pass
    
    @abstractmethod
    async def get_top_pools_by_network_dex(self, network: str, dex: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network and DEX."""
        pass
    
    @abstractmethod
    async def get_multiple_pools_by_network(self, network: str, addresses: List[str]) -> Dict[str, Any]:
        """Get multiple pools by their addresses."""
        pass
    
    @abstractmethod
    async def get_pool_by_network_address(self, network: str, address: str) -> Dict[str, Any]:
        """Get specific pool by network and address."""
        pass
    
    @abstractmethod
    async def get_ohlcv_data(self, network: str, pool_address: str, 
                           timeframe: str = "hour", 
                           before_timestamp: Optional[int] = None,
                           limit: int = 1000,
                           currency: str = "usd",
                           token: str = "base") -> Dict[str, Any]:
        """Get OHLCV data for a pool."""
        pass
    
    @abstractmethod
    async def get_trades(self, network: str, pool_address: str) -> Dict[str, Any]:
        """Get recent trades for a pool."""
        pass
    
    @abstractmethod
    async def get_token_info(self, network: str, token_address: str) -> Dict[str, Any]:
        """Get token information."""
        pass


class GeckoTerminalClient(BaseGeckoClient):
    """
    Async GeckoTerminal API client with rate limiting, retry logic, and error handling.
    
    Wraps the geckoterminal-py SDK with additional resilience features.
    """
    
    def __init__(self, api_config: APIConfig, error_config: ErrorConfig):
        """
        Initialize the client with configuration.
        
        Args:
            api_config: API configuration settings
            error_config: Error handling configuration
        """
        self.api_config = api_config
        self.error_config = error_config
        
        # Initialize rate limiter and circuit breaker
        self.rate_limiter = RateLimiter(api_config.rate_limit_delay)
        self.circuit_breaker = CircuitBreaker(
            error_config.circuit_breaker_threshold,
            error_config.circuit_breaker_timeout
        )
        
        # Initialize the underlying SDK client
        self._sdk_client = GeckoTerminalAsyncClient()
        
        # Session for direct API calls
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.api_config.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def _execute_with_retry(self, operation, *args, **kwargs) -> Any:
        """
        Execute an operation with retry logic and circuit breaker.
        
        Args:
            operation: The operation to execute
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: If all retries are exhausted or circuit breaker is open
        """
        if not self.circuit_breaker.can_execute():
            raise Exception("Circuit breaker is open - too many recent failures")
        
        last_exception = None
        
        for attempt in range(self.error_config.max_retries + 1):
            try:
                # Wait for rate limiting
                await self.rate_limiter.wait()
                
                # Execute the operation
                result = await operation(*args, **kwargs)
                
                # Record success and return result
                self.circuit_breaker.record_success()
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.error_config.max_retries + 1}): {e}"
                )
                
                # Record failure
                self.circuit_breaker.record_failure()
                
                # If this was the last attempt, don't wait
                if attempt == self.error_config.max_retries:
                    break
                
                # Calculate backoff delay
                delay = self.error_config.backoff_factor ** attempt
                await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(f"All retries exhausted for API call: {last_exception}")
        raise last_exception
    
    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get available networks."""
        async def _get_networks():
            return await self._sdk_client.get_networks()
        
        return await self._execute_with_retry(_get_networks)
    
    async def get_dexes_by_network(self, network: str) -> List[Dict[str, Any]]:
        """Get DEXes available on a network."""
        async def _get_dexes():
            return await self._sdk_client.get_dexes_by_network(network)
        
        return await self._execute_with_retry(_get_dexes)
    
    async def get_top_pools_by_network(self, network: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network."""
        async def _get_top_pools():
            return await self._sdk_client.get_top_pools_by_network(network, page=page)
        
        return await self._execute_with_retry(_get_top_pools)
    
    async def get_top_pools_by_network_dex(self, network: str, dex: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network and DEX."""
        async def _get_top_pools_dex():
            return await self._sdk_client.get_top_pools_by_network_dex(network, dex, page=page)
        
        return await self._execute_with_retry(_get_top_pools_dex)
    
    async def get_multiple_pools_by_network(self, network: str, addresses: List[str]) -> Dict[str, Any]:
        """Get multiple pools by their addresses."""
        async def _get_multiple_pools():
            # Join addresses with comma as expected by the API
            addresses_str = ",".join(addresses)
            return await self._sdk_client.get_multiple_pools_by_network(network, addresses_str)
        
        return await self._execute_with_retry(_get_multiple_pools)
    
    async def get_pool_by_network_address(self, network: str, address: str) -> Dict[str, Any]:
        """Get specific pool by network and address."""
        async def _get_pool():
            return await self._sdk_client.get_pool_by_network_address(network, address)
        
        return await self._execute_with_retry(_get_pool)
    
    async def get_ohlcv_data(self, network: str, pool_address: str, 
                           timeframe: str = "hour", 
                           before_timestamp: Optional[int] = None,
                           limit: int = 1000,
                           currency: str = "usd",
                           token: str = "base") -> Dict[str, Any]:
        """Get OHLCV data for a pool."""
        async def _get_ohlcv():
            return await self._sdk_client.get_ohlcv(
                network, pool_address, timeframe, 
                before_timestamp=before_timestamp,
                limit=limit, currency=currency, token=token
            )
        
        return await self._execute_with_retry(_get_ohlcv)
    
    async def get_trades(self, network: str, pool_address: str) -> Dict[str, Any]:
        """Get recent trades for a pool."""
        async def _get_trades():
            return await self._sdk_client.get_trades(network, pool_address)
        
        return await self._execute_with_retry(_get_trades)
    
    async def get_token_info(self, network: str, token_address: str) -> Dict[str, Any]:
        """Get token information."""
        async def _get_token():
            return await self._sdk_client.get_specific_token_on_network(network, token_address)
        
        return await self._execute_with_retry(_get_token)
    
    async def direct_api_call(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a direct API call for endpoints not covered by the SDK.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response data
        """
        if not self._session:
            raise RuntimeError("Client must be used as async context manager for direct API calls")
        
        async def _direct_call():
            url = f"{self.api_config.base_url}/{endpoint.lstrip('/')}"
            async with self._session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        
        return await self._execute_with_retry(_direct_call)


class MockGeckoTerminalClient(BaseGeckoClient):
    """
    Mock client for testing using CSV fixture data.
    
    Loads data from CSV files in the specs directory and returns it
    in the same format as the real API client.
    """
    
    def __init__(self, fixtures_path: str = "specs"):
        """
        Initialize mock client with path to fixture files.
        
        Args:
            fixtures_path: Path to directory containing CSV fixtures
        """
        self.fixtures_path = Path(fixtures_path)
        self._load_fixtures()
    
    def _load_fixtures(self):
        """Load all CSV fixtures into memory."""
        self.fixtures = {}
        
        # Load DEX data
        dex_file = self.fixtures_path / "get_dexes_by_network.csv"
        if dex_file.exists():
            self.fixtures["dexes"] = self._load_csv(dex_file)
        
        # Load pool data
        heaven_pools = self.fixtures_path / "get_top_pools_by_network_dex_heaven.csv"
        if heaven_pools.exists():
            self.fixtures["heaven_pools"] = self._load_csv(heaven_pools)
        
        pumpswap_pools = self.fixtures_path / "get_top_pools_by_network_dex_pumpswap.csv"
        if pumpswap_pools.exists():
            self.fixtures["pumpswap_pools"] = self._load_csv(pumpswap_pools)
        
        # Load OHLCV data
        ohlcv_file = self.fixtures_path / "get_ohlcv.csv"
        if ohlcv_file.exists():
            self.fixtures["ohlcv"] = self._load_csv(ohlcv_file)
        
        # Load trades data
        trades_file = self.fixtures_path / "get_trades.csv"
        if trades_file.exists():
            self.fixtures["trades"] = self._load_csv(trades_file)
        
        # Load multiple pools data
        multi_pools_file = self.fixtures_path / "get_multiple_pools_by_network.csv"
        if multi_pools_file.exists():
            self.fixtures["multiple_pools"] = self._load_csv(multi_pools_file)
        
        # Load single pool data
        single_pool_file = self.fixtures_path / "get_pool_by_network_address.csv"
        if single_pool_file.exists():
            self.fixtures["single_pool"] = self._load_csv(single_pool_file)
        
        # Load watchlist
        watchlist_file = self.fixtures_path / "watchlist.csv"
        if watchlist_file.exists():
            self.fixtures["watchlist"] = self._load_csv(watchlist_file)
    
    def _load_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load CSV file and return as list of dictionaries."""
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric strings to appropriate types
                    converted_row = {}
                    for key, value in row.items():
                        converted_row[key] = self._convert_value(value)
                    data.append(converted_row)
        except Exception as e:
            logger.warning(f"Failed to load fixture {file_path}: {e}")
        
        return data
    
    def _convert_value(self, value: str) -> Any:
        """Convert string values to appropriate types."""
        if not value or value.strip() == "":
            return None
        
        value = value.strip()
        
        # Try to convert to number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get available networks (mock)."""
        return [
            {
                "id": "solana",
                "type": "network",
                "attributes": {
                    "name": "Solana",
                    "coingecko_asset_platform_id": "solana"
                }
            }
        ]
    
    async def get_dexes_by_network(self, network: str) -> List[Dict[str, Any]]:
        """Get DEXes available on a network (mock)."""
        dexes_data = self.fixtures.get("dexes", [])
        
        # Convert CSV format to API format
        result = []
        for dex in dexes_data:
            result.append({
                "id": dex.get("id"),
                "type": "dex",
                "attributes": {
                    "name": dex.get("name")
                }
            })
        
        return result
    
    async def get_top_pools_by_network(self, network: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network (mock)."""
        # Combine heaven and pumpswap pools
        heaven_pools = self.fixtures.get("heaven_pools", [])
        pumpswap_pools = self.fixtures.get("pumpswap_pools", [])
        all_pools = heaven_pools + pumpswap_pools
        
        return self._format_pools_response(all_pools)
    
    async def get_top_pools_by_network_dex(self, network: str, dex: str, page: int = 1) -> Dict[str, Any]:
        """Get top pools by network and DEX (mock)."""
        if dex == "heaven":
            pools_data = self.fixtures.get("heaven_pools", [])
        elif dex == "pumpswap":
            pools_data = self.fixtures.get("pumpswap_pools", [])
        else:
            pools_data = []
        
        return self._format_pools_response(pools_data)
    
    def _format_pools_response(self, pools_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format pools data to match API response structure."""
        formatted_pools = []
        
        for pool in pools_data:
            formatted_pool = {
                "id": pool.get("id"),
                "type": "pool",
                "attributes": {
                    "name": pool.get("name"),
                    "address": pool.get("address"),
                    "base_token_price_usd": str(pool.get("base_token_price_usd", 0)),
                    "quote_token_price_usd": str(pool.get("quote_token_price_usd", 0)),
                    "reserve_in_usd": str(pool.get("reserve_in_usd", 0)),
                    "pool_created_at": pool.get("pool_created_at"),
                    "fdv_usd": pool.get("fdv_usd"),
                    "market_cap_usd": pool.get("market_cap_usd"),
                    "price_change_percentage": {
                        "h1": pool.get("price_change_percentage_h1"),
                        "h24": pool.get("price_change_percentage_h24")
                    },
                    "transactions": {
                        "h1": {
                            "buys": pool.get("transactions_h1_buys"),
                            "sells": pool.get("transactions_h1_sells")
                        },
                        "h24": {
                            "buys": pool.get("transactions_h24_buys"),
                            "sells": pool.get("transactions_h24_sells")
                        }
                    },
                    "volume_usd": {
                        "h24": pool.get("volume_usd_h24")
                    }
                },
                "relationships": {
                    "dex": {
                        "data": {
                            "id": pool.get("dex_id"),
                            "type": "dex"
                        }
                    },
                    "base_token": {
                        "data": {
                            "id": pool.get("base_token_id"),
                            "type": "token"
                        }
                    },
                    "quote_token": {
                        "data": {
                            "id": pool.get("quote_token_id"),
                            "type": "token"
                        }
                    }
                }
            }
            formatted_pools.append(formatted_pool)
        
        return {
            "data": formatted_pools,
            "meta": {
                "page": {
                    "current": 1,
                    "total": 1
                }
            }
        }
    
    async def get_multiple_pools_by_network(self, network: str, addresses: List[str]) -> Dict[str, Any]:
        """Get multiple pools by their addresses (mock)."""
        pools_data = self.fixtures.get("multiple_pools", [])
        
        # Filter pools by addresses if provided
        if addresses:
            filtered_pools = [
                pool for pool in pools_data 
                if pool.get("address") in addresses or pool.get("id") in addresses
            ]
        else:
            filtered_pools = pools_data
        
        return self._format_pools_response(filtered_pools)
    
    async def get_pool_by_network_address(self, network: str, address: str) -> Dict[str, Any]:
        """Get specific pool by network and address (mock)."""
        pools_data = self.fixtures.get("single_pool", [])
        
        # Find pool by address
        pool_data = None
        for pool in pools_data:
            if pool.get("address") == address or pool.get("id") == address:
                pool_data = pool
                break
        
        if not pool_data and pools_data:
            # Return first pool as fallback
            pool_data = pools_data[0]
        
        if pool_data:
            response = self._format_pools_response([pool_data])
            return {
                "data": response["data"][0] if response["data"] else None
            }
        
        return {"data": None}
    
    async def get_ohlcv_data(self, network: str, pool_address: str, 
                           timeframe: str = "hour", 
                           before_timestamp: Optional[int] = None,
                           limit: int = 1000,
                           currency: str = "usd",
                           token: str = "base") -> Dict[str, Any]:
        """Get OHLCV data for a pool (mock)."""
        ohlcv_data = self.fixtures.get("ohlcv", [])
        
        # Convert CSV format to API format
        formatted_data = []
        for row in ohlcv_data:
            formatted_data.append([
                row.get("timestamp"),
                row.get("open"),
                row.get("high"), 
                row.get("low"),
                row.get("close"),
                row.get("volume")
            ])
        
        return {
            "data": {
                "id": pool_address,
                "type": "pool",
                "attributes": {
                    "ohlcv_list": formatted_data
                }
            },
            "meta": {
                "base": {
                    "address": pool_address,
                    "symbol": "TOKEN"
                }
            }
        }
    
    async def get_trades(self, network: str, pool_address: str) -> Dict[str, Any]:
        """Get recent trades for a pool (mock)."""
        trades_data = self.fixtures.get("trades", [])
        
        # Convert CSV format to API format
        formatted_trades = []
        for trade in trades_data:
            formatted_trade = {
                "id": trade.get("id", f"trade_{len(formatted_trades)}"),
                "type": "trade",
                "attributes": {
                    "block_number": trade.get("block_number"),
                    "tx_hash": trade.get("tx_hash"),
                    "tx_from_address": trade.get("tx_from_address"),
                    "from_token_amount": str(trade.get("from_token_amount", 0)),
                    "to_token_amount": str(trade.get("to_token_amount", 0)),
                    "price_from_in_currency_token": str(trade.get("price_usd", 0)),
                    "price_to_in_currency_token": str(trade.get("price_usd", 0)),
                    "price_from_in_usd": str(trade.get("price_usd", 0)),
                    "price_to_in_usd": str(trade.get("price_usd", 0)),
                    "block_timestamp": trade.get("block_timestamp"),
                    "kind": trade.get("side", "buy")
                }
            }
            formatted_trades.append(formatted_trade)
        
        return {
            "data": formatted_trades
        }
    
    async def get_token_info(self, network: str, token_address: str) -> Dict[str, Any]:
        """Get token information (mock)."""
        # Return mock token data
        return {
            "data": {
                "id": token_address,
                "type": "token",
                "attributes": {
                    "address": token_address,
                    "name": "Mock Token",
                    "symbol": "MOCK",
                    "decimals": 9,
                    "total_supply": "1000000000",
                    "price_usd": "1.0"
                }
            }
        }