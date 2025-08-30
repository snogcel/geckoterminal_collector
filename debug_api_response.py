#!/usr/bin/env python3
"""
Debug script to check actual API response structure.
"""

import asyncio
import json
from geckoterminal_py import GeckoTerminalAsyncClient


async def test_api_responses():
    """Test actual API responses to understand structure."""
    client = GeckoTerminalAsyncClient()
    
    print("Testing API responses...")
    
    # Test pool data
    print("\n1. Testing get_pool_by_network_address:")
    try:
        pool_response = await client.get_pool_by_network_address(
            "solana", 
            "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        )
        print(f"Pool response type: {type(pool_response)}")
        print(f"Pool response keys: {list(pool_response.keys()) if isinstance(pool_response, dict) else 'Not a dict'}")
        
        if isinstance(pool_response, dict):
            if 'data' in pool_response:
                print(f"Pool data type: {type(pool_response['data'])}")
                if isinstance(pool_response['data'], dict):
                    print(f"Pool data keys: {list(pool_response['data'].keys())}")
                elif isinstance(pool_response['data'], list):
                    print(f"Pool data length: {len(pool_response['data'])}")
                    if pool_response['data']:
                        print(f"First pool item keys: {list(pool_response['data'][0].keys()) if isinstance(pool_response['data'][0], dict) else 'Not a dict'}")
            
            # Print first few lines of response for debugging
            print(f"Pool response (first 500 chars): {str(pool_response)[:500]}...")
        
    except Exception as e:
        print(f"Error getting pool data: {e}")
    
    # Test token data
    print("\n2. Testing get_specific_token_on_network:")
    try:
        token_response = await client.get_specific_token_on_network(
            "solana", 
            "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        print(f"Token response type: {type(token_response)}")
        print(f"Token response keys: {list(token_response.keys()) if isinstance(token_response, dict) else 'Not a dict'}")
        
        if isinstance(token_response, dict):
            if 'data' in token_response:
                print(f"Token data type: {type(token_response['data'])}")
                if isinstance(token_response['data'], dict):
                    print(f"Token data keys: {list(token_response['data'].keys())}")
            
            # Print first few lines of response for debugging
            print(f"Token response (first 500 chars): {str(token_response)[:500]}...")
        
    except Exception as e:
        print(f"Error getting token data: {e}")


if __name__ == "__main__":
    asyncio.run(test_api_responses())