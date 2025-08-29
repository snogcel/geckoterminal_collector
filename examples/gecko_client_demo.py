"""
Demo script showing how to use the GeckoTerminal API client wrapper.
"""

import asyncio
import logging
from gecko_terminal_collector.clients import create_gecko_client
from gecko_terminal_collector.config.models import APIConfig, ErrorConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_real_client():
    """Demonstrate usage of the real API client."""
    print("=== Real GeckoTerminal API Client Demo ===")
    
    # Create configuration
    api_config = APIConfig(
        rate_limit_delay=1.0,  # 1 second between calls
        timeout=30
    )
    error_config = ErrorConfig(
        max_retries=3,
        backoff_factor=2.0
    )
    
    # Create client
    client = create_gecko_client(api_config, error_config, use_mock=False)
    
    try:
        # Use client as async context manager for proper session handling
        async with client:
            # Get available networks
            print("\n1. Getting available networks...")
            networks = await client.get_networks()
            print(f"Found {len(networks)} networks")
            for network in networks[:3]:  # Show first 3
                print(f"  - {network.get('id')}: {network.get('attributes', {}).get('name')}")
            
            # Get DEXes for Solana
            print("\n2. Getting DEXes for Solana...")
            dexes = await client.get_dexes_by_network("solana")
            print(f"Found {len(dexes)} DEXes on Solana")
            for dex in dexes[:5]:  # Show first 5
                print(f"  - {dex.get('id')}: {dex.get('attributes', {}).get('name')}")
            
            # Get top pools for Heaven DEX
            print("\n3. Getting top pools for Heaven DEX...")
            pools = await client.get_top_pools_by_network_dex("solana", "heaven")
            pool_data = pools.get("data", [])
            print(f"Found {len(pool_data)} pools on Heaven DEX")
            for pool in pool_data[:3]:  # Show first 3
                attrs = pool.get("attributes", {})
                print(f"  - {pool.get('id')}: {attrs.get('name')} (${attrs.get('reserve_in_usd', 0):,.2f})")
    
    except Exception as e:
        logger.error(f"Error with real client: {e}")
        print(f"Error: {e}")
        print("Note: This requires internet connection and valid API access")


async def demo_mock_client():
    """Demonstrate usage of the mock API client with CSV fixtures."""
    print("\n=== Mock GeckoTerminal API Client Demo ===")
    
    # Create configuration (not used by mock client but required for interface)
    api_config = APIConfig()
    error_config = ErrorConfig()
    
    # Create mock client using CSV fixtures
    client = create_gecko_client(api_config, error_config, use_mock=True, fixtures_path="specs")
    
    try:
        # Get available networks
        print("\n1. Getting available networks (mock)...")
        networks = await client.get_networks()
        print(f"Found {len(networks)} networks")
        for network in networks:
            print(f"  - {network.get('id')}: {network.get('attributes', {}).get('name')}")
        
        # Get DEXes for Solana
        print("\n2. Getting DEXes for Solana (from CSV fixture)...")
        dexes = await client.get_dexes_by_network("solana")
        print(f"Found {len(dexes)} DEXes on Solana")
        for dex in dexes:
            print(f"  - {dex.get('id')}: {dex.get('attributes', {}).get('name')}")
        
        # Get top pools for Heaven DEX
        print("\n3. Getting top pools for Heaven DEX (from CSV fixture)...")
        pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        pool_data = pools.get("data", [])
        print(f"Found {len(pool_data)} pools on Heaven DEX")
        for pool in pool_data[:3]:  # Show first 3
            attrs = pool.get("attributes", {})
            reserve = attrs.get("reserve_in_usd")
            if reserve is not None:
                try:
                    reserve_float = float(reserve)
                    print(f"  - {pool.get('id')}: {attrs.get('name')} (${reserve_float:,.2f})")
                except (ValueError, TypeError):
                    print(f"  - {pool.get('id')}: {attrs.get('name')} (${reserve})")
            else:
                print(f"  - {pool.get('id')}: {attrs.get('name')}")
        
        # Get OHLCV data
        print("\n4. Getting OHLCV data (from CSV fixture)...")
        if pool_data:
            pool_id = pool_data[0].get("id")
            ohlcv = await client.get_ohlcv_data("solana", pool_id)
            ohlcv_list = ohlcv.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
            print(f"Found {len(ohlcv_list)} OHLCV records for pool {pool_id}")
            for i, record in enumerate(ohlcv_list[:3]):  # Show first 3
                if len(record) >= 6:
                    timestamp, open_price, high, low, close, volume = record[:6]
                    print(f"  - Record {i+1}: O:{open_price} H:{high} L:{low} C:{close} V:{volume}")
        
        # Get trades data
        print("\n5. Getting trades data (from CSV fixture)...")
        if pool_data:
            pool_id = pool_data[0].get("id")
            trades = await client.get_trades("solana", pool_id)
            trade_data = trades.get("data", [])
            print(f"Found {len(trade_data)} trades for pool {pool_id}")
            for trade in trade_data[:3]:  # Show first 3
                attrs = trade.get("attributes", {})
                print(f"  - Trade {trade.get('id')}: {attrs.get('from_token_amount')} -> {attrs.get('to_token_amount')}")
    
    except Exception as e:
        logger.error(f"Error with mock client: {e}")
        print(f"Error: {e}")


async def main():
    """Run both demos."""
    print("GeckoTerminal API Client Wrapper Demo")
    print("=" * 50)
    
    # Run mock client demo (always works)
    await demo_mock_client()
    
    # Ask user if they want to try real client
    print("\n" + "=" * 50)
    try:
        response = input("Do you want to try the real API client? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            await demo_real_client()
        else:
            print("Skipping real API client demo.")
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
    except Exception:
        print("Skipping real API client demo.")
    
    print("\nDemo completed!")


if __name__ == "__main__":
    asyncio.run(main())