import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.clients.gecko_client import GeckoTerminalClient

async def test_direct_api_call():
    # Load config
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    
    # Create client
    client = GeckoTerminalClient(config.api, config.error_handling)
    
    pool_address = '7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP'
    network = 'solana'
    timeframe = '1h'  # This is what gets passed to the API
    
    print(f"Making direct API call:")
    print(f"Network: {network}")
    print(f"Pool address: {pool_address}")
    print(f"Timeframe: {timeframe}")
    
    try:
        response = await client.get_ohlcv_data(
            network=network,
            pool_address=pool_address,
            timeframe=timeframe,
            limit=1000,
            currency='usd',
            token='base'
        )
        
        print(f"\nAPI Response received:")
        print(f"Response type: {type(response)}")
        
        if isinstance(response, dict):
            print(f"Response keys: {list(response.keys())}")
            
            if 'data' in response:
                data = response['data']
                print(f"Data keys: {list(data.keys())}")
                
                if 'attributes' in data:
                    attributes = data['attributes']
                    print(f"Attributes keys: {list(attributes.keys())}")
                    
                    if 'ohlcv_list' in attributes:
                        ohlcv_list = attributes['ohlcv_list']
                        print(f"OHLCV list length: {len(ohlcv_list)}")
                        
                        if ohlcv_list:
                            print(f"First entry: {ohlcv_list[0]}")
                            print(f"Last entry: {ohlcv_list[-1]}")
                        else:
                            print("OHLCV list is empty!")
                    else:
                        print("No 'ohlcv_list' in attributes")
                else:
                    print("No 'attributes' in data")
            else:
                print("No 'data' in response")
        else:
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"API call failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct_api_call())