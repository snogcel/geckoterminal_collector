import json
import csv
import pandas as pd
from geckoterminal_py import GeckoTerminalAsyncClient
client = GeckoTerminalAsyncClient()

import asyncio

# Anger Management Exercise

# Anger Management Exercise, Part 2. Reviewing a JSON file.

async def main():
    print("Starting async operation...")
    new_pools_by_network = await client.get_new_pools_by_network("solana")
    
    new_pools_by_network_df = pd.DataFrame(new_pools_by_network)
    print(new_pools_by_network_df)
    new_pools_by_network_df.to_csv('new_pools_by_network_2.csv', index=False)

    await asyncio.sleep(1)  # await used inside an async function
    print("Async operation completed.")

async def another_async_function():
    print("Another async function running.")
    
    await main() # await can be used to call other async functions

# To run an async function, you need to use asyncio.run()
if __name__ == "__main__":
    # asyncio.run(main())
    # asyncio.run(another_async_function())

    # build spec for this API Route (not supported by SDK)

    # Assuming 'data.txt' contains a JSON string representing a dictionary
    #with open('info_recently_updated_2.txt', 'r', encoding='utf-8') as file:
    #    loaded_dict = json.load(file)

       
    # capture "data" attribute from returned data    
    #records = loaded_dict["data"]

    #df = pd.json_normalize(records, sep='_')

    #print(df.columns)
    #print(records.columns)

    # If you only need specific columns, select them here
    # For example: df = df[['id', 'type', 'attributes_name', 'attributes_symbol', 'attributes_decimals']]

    #print(df['attributes_address'])


    # network address = BoLTp38Aqnaewa1yJ98tLx19y5DEQgrDjtwWv3k9hBxu


    ## Anger Management Exercise, Part 2.

    with open('info_recently_updated.json', 'r', encoding='utf-8') as file:
        loaded_dict = json.load(file)

    # capture "data" attribute from returned data    
    records = loaded_dict["data"]
    df = pd.json_normalize(records, sep='_')

    print(df)
    df.to_csv("info_recently_updated.csv")





    

    



# access 
# /tokens/info_recently_updated

# https://api.geckoterminal.com/api/v2/tokens/info_recently_updated?include=network&network=solana







""" 
Result:

{
    "id": "solana_BoLTp38Aqnaewa1yJ98tLx19y5DEQgrDjtwWv3k9hBxu",
    "type": "token",
    "attributes": {
        "address": "BoLTp38Aqnaewa1yJ98tLx19y5DEQgrDjtwWv3k9hBxu",
        "name": "BOLT",
        "symbol": "BOLT",
        "decimals": 9,
        "image_url": "https://coin-images.coingecko.com/coins/images/69035/large/Bolt_IMage.PNG?1757320261",
        "coingecko_coin_id": "bolt-2",
        "total_supply": "5000000000000000000.0",
        "normalized_total_supply": "5000000000.0",
        "price_usd": "0.0000608796592",
        "fdv_usd": "304398.295978579",
        "total_reserve_in_usd": "24106.8952859350366444176",
        "volume_usd": {"h24": "4199.1066494847"},
        "market_cap_usd": None,
    },
    "relationships": {
        "top_pools": {
            "data": [
                {
                    "id": "solana_21u5d2xUwx7JMvUf8vq4exd6X3c7vcVoW1QzinYZWjvy",
                    "type": "pool",
                }
            ]
        }
    },
}

 """



