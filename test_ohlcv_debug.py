import asyncio
import json
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector

async def test_ohlcv_parsing():
    # Load config
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    
    # Initialize database
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Create collector
    collector = OHLCVCollector(config, db_manager)
    
    # Test data from your example
    test_response = {
        'data': {
            'id': '390eb34a-7780-41dc-a194-48848e211cae',
            'type': 'ohlcv_request_response',
            'attributes': {
                'ohlcv_list': [
                    [1756569600, 2.238038001881942e-05, 5.5621284996653516e-05, 2.238038001881942e-05, 4.629060043710037e-05, 8473.332505361317],
                    [1756566000, 2.259834141129537e-05, 2.259834141129537e-05, 2.2207442703328643e-05, 2.238038001881942e-05, 146.5175843460121]
                ]
            }
        }
    }
    
    # Parse the response
    pool_id = '7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP'
    timeframe = '1h'
    
    print(f"Testing OHLCV parsing for pool {pool_id}")
    print(f"Input response has {len(test_response['data']['attributes']['ohlcv_list'])} OHLCV entries")
    
    records = collector._parse_ohlcv_response(test_response, pool_id, timeframe)
    print(f'Parsed {len(records)} records')
    
    for i, record in enumerate(records[:2]):
        print(f'Record {i+1}: timestamp={record.timestamp}, open={record.open_price}, volume={record.volume_usd}')
    
    # Test validation
    if records:
        validation_result = await collector._validate_ohlcv_data(records)
        print(f"Validation result: valid={validation_result.is_valid}, errors={validation_result.errors}")
        
        # Test storage
        if validation_result.is_valid:
            stored_count = await db_manager.store_ohlcv_data(records)
            print(f"Stored {stored_count} records to database")
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(test_ohlcv_parsing())