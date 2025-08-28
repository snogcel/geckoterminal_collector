### Requirement 1
**User Story:**
As a Decentralized Exchange trader on the Solana Network, I want this system to have future extensibility to support new opportunities. I have identified two DEX targets that I would like to monitor: "heaven", and "pumpswap". I am using the Public API offered by GeckoTerminal to support this functionality using the public SDK: geckoterminal-py.

I've copied the test coverage from this library into /tests for your reference of availability functionalities for this public API. 

I have also placed the result of the API Call "get_dexes_by_network" into the CSV file get_dexes_by_network.csv located in the /specs folder for reference.

API Schema: /networks/{network}/dexes
SDK Command: await client.get_dexes_by_network("solana")



### Requirement 2
**User Story:**
I would like to monitor the top pools by network_dex every hour, this interval (and others within the system as a whole) should be configurable. The result of these queries are outlined the /specs folder in get_top_pools_by_network_dex_heaven.csv and get_top_pools_by_network_dex_pumpswap.csv for the DEX Targets "heaven" and "pumpswap". These files were generated using the following SDK commands:

API Schema: /networks/{network}/dexes/{dex}/pools
await client.get_top_pools_by_network_dex("solana", "pumpswap")
await client.get_top_pools_by_network_dex("solana", "heaven")



### Requirement 3
**User Story:**
I need to be able to collect information about Tokens, Pools, and Trades centered on a "Watch List" of selected tokens. There are two types of addresses to be aware of which are used somewhat interchangably in the API. These addresses are defined by "id" which represents the Pool Address, and "base_token_id" which represents the network address.

This list is being generated in a separate process and will be available in a .CSV file that is updated on an hourly basis. This frequency may change in the future. An example of this CSV is stored in /specs/watchlist.csv and is aligned with the other example data stored in /specs. This CSV stores the "id" address which represents the Pool Address.

When a new token is added to the list, the information generated from the following SDK Commands should retrieve information about the token and pool. It will likely be fastest to use the "Get Pool by Multiple Network Address" method outlined below. This is additionally supplemented with "Get Pool by Network Address" and "Get Specific Token on Network".

# Get Pool by Multiple Network Address
API Schema: /networks/{network}/pools/multi/{addresses}
SDK Command: await client.get_multiple_pools_by_network("solana", ["7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP", "7SWbVXmn2Ar8CqAdVZfQmZcCGmnChRp2JTfuEzyBL17V"])

The output of this command will utilize multiple "id" and return the data contained in get_multiple_pools_by_network.csv

# Get Pool by Network Address
API Schema: /networks/{network}/pools/{address}
SDK Command: await client.get_pool_by_network_address("solana", "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP")

This command will utilize "id" and return the data contained in get_pool_by_network_address.csv

# Get Specific Token on Network
API Schema: /networks/{network}/tokens/{address}/info
SDK Command: await client.get_specific_token_on_network("solana", "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump")

This command will utilize "base_token_id" and return a python dict described below and contained in get_specific_token_on_network.txt

{'id': 'solana_5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump',
 'type': 'token',
 'attributes': {'address': '5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump',
  'name': 'Cracker Barrel Old Country Store',
  'symbol': 'CBRL',
  'decimals': 6,
  'image_url': 'https://assets.geckoterminal.com/52ah33wkaouh2fax4lnkwvpq2vhz',
  'coingecko_coin_id': None,
  'total_supply': '999922842480187.0',
  'normalized_total_supply': '999922842.480187',
  'price_usd': '0.00004764845427',
  'fdv_usd': '47644.7778353236',
  'total_reserve_in_usd': '17177.0163064019881364397',
  'volume_usd': {'h24': '124737.925416128'},
  'market_cap_usd': None},
 'relationships': {'top_pools': {'data': [{'id': 'solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP',
     'type': 'pool'},
    {'id': 'solana_7hb25J3UPoEW4GG8dh2o6qwtzFRY348AGKjmiW8dSddN',
     'type': 'pool'},
    {'id': 'solana_H3j73uERseKuWwMehDegcmV3Tv9yBRie1nhSmRhciYeg',
     'type': 'pool'}]}}}



### Requirement 4: Collect OHLCV Data
**User Story:**
OHLCV data should be collected for every token on the Watch List using a configurable interval. Database integrity is of concern here, and should at a minimum prevent duplications. Ideally some measure should exist to verify data continuity between intervals.

The timeframe of this data is configurable, the options supported by the SDK are as follows: ['1m', '5m', '15m', '1h', '4h', '12h', '1d']

API Schema: /networks/{network}/pools/{pool_address}/ohlcv/{timeframe}
SDK Command: await client.get_ohlcv("solana", "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP", "1h")

This command will utilize "id" and return the data contained in get_ohlcv.csv



### Requirement 5: Collect Trade Data
**User Story:**
Trade Data should be collected for every token on the Watch List using a configurable interval. Database integrity is of concern here, and should at a minimum prevent duplications. Ideally some measure should exist to verify data continuity between intervals.

The API contains a limit of 300 trades, and will only return data from the last 24 hours.

The SDK includes an option to control a minimum in USD Volume (sent as an option in the API request: "trade_volume_in_usd_greater_than"). In this example we are filtering this value to only include trades that are greater than 100.

API Schema: /networks/{network}/pools/{pool_address}/trades
SDK Command: await client.get_trades("solana", "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP", "100")

This command will utilize "id" and return the data contained in get_trades.csv



### Requirement 6: Collect Historical OHLCV Data
**User Story:**
The SDK we are using does not support the fetching of Historical Data. For the purpose of building predictive models, and perhaps for other data validation requirements mentioned above, we'll need to extract historical OHLCV data using direct API Requests to GeckoTerminal.

## Method: GET
API Schema: /networks/{network}/pools/{pool_address}/ohlcv/{timeframe}
Description: Get OHLCV data of a pool, up to 6 months ago. Empty response if there is no earlier data available. Network, pool_address and timeframe are required and requested using path parameters. Aggregate, before_timestamp, limit, currency, include_empty_intervals, and token are sent as query parameters.

This command will utilize "id", and an example of a successful response is available in /specs/response_body.txt and associated headers are located in response_headers.txt

# Example (Curl)
curl -X 'GET' \
  'https://api.geckoterminal.com/api/v2/networks/solana/pools/7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP/ohlcv/minute?aggregate=15&before_timestamp=1755756000&limit=100&currency=usd&include_empty_intervals=true&token=base' \
  -H 'accept: application/json'

# Example (Request URL)
https://api.geckoterminal.com/api/v2/networks/solana/pools/7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP/ohlcv/minute?aggregate=15&before_timestamp=1755756000&limit=100&currency=usd&include_empty_intervals=true&token=base

## Parameter Definitions:
The following parameters were used to execute the above query examples:

# network
Example: solana
Description: Network id from /networks list
Info: Required, String, Path Parameter

# pool_address
Example: 7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP
Description: Pool address. Pools with more than 2 tokens are not yet supported for this endpoint.
Info: Required, String, Path Parameter

# timeframe
Available Values: day, hour, minute
Example: minute
Description: The timeframe being requested. API supports up to 6 months. 
Info: Required, String, Path Parameter

# aggregate
Available values (day): 1
Available values (hour): 1, 4, 12
Available values (minute): 1, 5, 15
Example: minute?aggregate=15 (for 15m OHLCV)
Description: Time period to aggregate for each ohlcv, implemented as an extension of the timeframe parameter (eg. /minute?aggregate=15 for 15m ohlcv)
Info: String, Query Parameter

# before_timestamp
Example: 1755756000
Description: Return ohlcv data before this timestamp (integer seconds since epoch)
Info: String, Query Parameter

# limit
Example: 100
Description: Limit number of ohlcv results to return (default: 100, max: 1000)
Info: String, Query Parameter

# currency
Available values: usd, token
Example: usd
Description: Return ohlcv in USD or quote token (default: usd)
Info: String, Query Parameter

# include_empty_intervals
Available values: true, false
Example: true
Description: Populate the OHLCV values for empty intervals (default: false)
Info: Boolean, Query Parameter

# token
Available values: base, quote, or a token address
Example: base
Description: Return ohlcv for base or quote token; use this to invert the chart. (default: base)
Info: String, Query Parameter


### Requirement 7: QLib
**User Story:**
As an analyst, I would like to use QLib to extract and parse the data collected from this system for predictive modeling purposes. I have placed a variety of scripts that are designed for this purpose into the /examples/qlib_scripts folder. The closest fit for this use case is likely contained in /examples/qlib_scripts/data_collector/crypto. This data collector is designed for Coin Gecko (which is related to GeckoTerminal) and could potentially allow future extensibility, so it seems like something modeled after this would be ideal.
