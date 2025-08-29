"""
Factory for creating GeckoTerminal API clients.
"""

from typing import Union

from ..config.models import APIConfig, ErrorConfig
from .gecko_client import GeckoTerminalClient, MockGeckoTerminalClient, BaseGeckoClient


def create_gecko_client(
    api_config: APIConfig, 
    error_config: ErrorConfig,
    use_mock: bool = False,
    fixtures_path: str = "specs"
) -> BaseGeckoClient:
    """
    Create a GeckoTerminal API client.
    
    Args:
        api_config: API configuration settings
        error_config: Error handling configuration
        use_mock: Whether to use mock client for testing
        fixtures_path: Path to CSV fixtures for mock client
        
    Returns:
        Configured API client instance
    """
    if use_mock:
        return MockGeckoTerminalClient(fixtures_path)
    else:
        return GeckoTerminalClient(api_config, error_config)


async def create_async_gecko_client(
    api_config: APIConfig, 
    error_config: ErrorConfig,
    use_mock: bool = False,
    fixtures_path: str = "specs"
) -> BaseGeckoClient:
    """
    Create and initialize an async GeckoTerminal API client.
    
    Args:
        api_config: API configuration settings
        error_config: Error handling configuration
        use_mock: Whether to use mock client for testing
        fixtures_path: Path to CSV fixtures for mock client
        
    Returns:
        Initialized async API client instance
    """
    client = create_gecko_client(api_config, error_config, use_mock, fixtures_path)
    
    # Initialize async context if needed
    if hasattr(client, '__aenter__'):
        await client.__aenter__()
    
    return client