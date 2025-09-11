
### TODO 3: Figured out the best way to collect **network_address** efficiently. [MOVED_TO_V2_SPEC]
# See FOLLOW UP LIST: TODO 3a  [MOVED_TO_V2_SPEC]
# TODO 3b: Review Pool Table Foreign Key Dependencies, which is causing problems with the existing Watchlist Functionality
# TODO 3c: Review data collection for tokens as they are launched, and how they might replace certain functionalities of DexScreener_scraper
# TODO 3d: Review TODO 2 (see below), as this one task allows many other functionalities to now happen.

### TODO 2: New Pools by Network (spec out time series data for storing additional data) [MOVED_TO_V2_SPEC]
# Create additional “Pool” class in geckoterminal_collector to support information capture requirements

# example existing data structure ("pool", primary key / foreign key constraint on token data):
id: solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
address: 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
name: "WORTHLESS / SOL"
dex_id: "pumpswap"
base_token_id: **network_address**
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 5095.2274
created_at: "2025-09-08T20:09:26Z"
last_updated: 

# Scam Coins! haha
dmeahd7crzkxefovsew2lbhtk5q7araynjqzva3z48ro



##### FOLLOW UP LIST #####

### TODO 3a: Figure out the best way to collect **network_address** efficiently  [MOVED_TO_V2_SPEC]
## existing spec (./.kiro/specs/tasks.md):
# **pool_address** ("id") and **network_address** ("base_token_id")

# Ideas:

# Utilize the same SDK method to fulfill two requirements:
1. Build out time-series data about network_pools
2. Use for discovery of **network_address** with a given set of **pool_addresses**

# See: Requirement 3 from prior document, *business_requirements.md*

## This SDK call will retrieve information about multiple **network_address** given **pool_address**: 
# await client.get_multiple_pools_by_network("solana", ["48caJmZzkhuzVqWMoiJhPoc8DkDi66Ut8aVXkroT9vHV", "4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3"])

# 48caJmZzkhuzVqWMoiJhPoc8DkDi66Ut8aVXkroT9vHV **pool_address**
# Fv73EXJBRfctJzLVC3P7uQP6er6JU8b4KtDr4LQFpump **network_address**

# Related to time-series usage of this SDK method, this one can also provide **network_address** given an existing pool address.
# Confirm the logic here, that we have pool_address from **TODO_2**: 


## SDK Call that finds network token with pool address (related to dex) and network:

# 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3 **pool_address**
# 2nXahcBAsDN5nUSpHxZNM8C7KpHae7kUwbAPXjnqpump **network_address**


# Get Pool by Multiple Network Address
API Schema: /networks/{network}/pools/multi/{addresses}
SDK Command: await client.get_multiple_pools_by_network("solana", ["7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP", "7SWbVXmn2Ar8CqAdVZfQmZcCGmnChRp2JTfuEzyBL17V"])

The output of this command will utilize multiple "id" and return the data contained in get_multiple_pools_by_network.csv

# notes: in this example, market_cap_usd is missing because they are worthless tokens (alignment maintained with previous specification document)

id,type,name,base_token_price_usd,base_token_price_native_currency,quote_token_price_usd,quote_token_price_native_currency,address,reserve_in_usd,pool_created_at,fdv_usd,market_cap_usd,price_change_percentage_h1,price_change_percentage_h24,transactions_h1_buys,transactions_h1_sells,transactions_h24_buys,transactions_h24_sells,volume_usd_h24,dex_id,base_token_id,quote_token_id
solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP,pool,CBRL / SOL,0.000039202570225661809354830149430549655024315386744451870167117433,0.0000001843591001348,212.215310481914630139482414841618672340114008178,1.0,7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP,30879.5689,2025-08-20T21:40:53Z,39199.5454569108,,-16.322,-42.45,23,15,398,308,73496.7809809967,pumpswap,solana_5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump,solana_So11111111111111111111111111111111111111112
solana_7SWbVXmn2Ar8CqAdVZfQmZcCGmnChRp2JTfuEzyBL17V,pool,JUAN / SOL,0.000352176843423967,0.00000167,211.34,1.0,7SWbVXmn2Ar8CqAdVZfQmZcCGmnChRp2JTfuEzyBL17V,102188.9555,2025-08-23T17:05:58Z,352176.843047823,,17.717,-14.111,21,17,361,253,162894.031547696,heaven,solana_5efQfRqBwYDob34CdeYyxnYAhPLKk4Y1Dy3FFNV2C777,solana_So11111111111111111111111111111111111111112


# This component drives two functionalities:
1. data series capture for the following fields

2. provides a method to maintain cryptographic address case-sensitivity requirements for QLib integration

TODO -- re-review, kiro generated specifications for QLib address lookup support.



# Data Structure of Response:







### END Shitty API Approach ###



# Use Case A:

# 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3 **pool_address**
# 2nXahcBAsDN5nUSpHxZNM8C7KpHae7kUwbAPXjnqpump **network_address**

# example existing data structure ("pool", primary key / foreign key constraint on token data):
id: solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
address: 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
name: "WORTHLESS / SOL"
dex_id: "pumpswap"
base_token_id: **network_address**
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 5095.2274
created_at: "2025-09-08T20:09:26Z"
last_updated: 

# Use Case B:

# this token is absent from this API route, which likely explains why it wasn't integrated into the SDK
id: solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
address: 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
name: "WORTHLESS / SOL"
dex_id: "pumpswap"
base_token_id: ?
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 5095.2274
created_at: "2025-09-08T20:09:26Z"
last_updated: 

##

## Questions:
# at what point will I need to fetch **network_address** ?
# how frequently would this need to be fetched?
# how many API calls would that add to this system?

### END TODO 3


###### END FOLLOW UP LIST #####







##### TODO 2 ### [MOVED_TO_V2_SPEC]
**TODO_2**
#### New Pools by Network API Example (https://www.geckoterminal.com/dex-api):
## API Request Example:
# /networks/{network}/new_pools
# Get latest pools on a network

# https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2C%20quote_token%2C%20dex&page=1

# example response file: new_pools_by_network.json

# requirements:
- store as time series data

## existing spec (./.kiro/specs/tasks.md):
# pool addresses ("id") and network addresses ("base_token_id")

# await client.get_new_pools_by_network("solana")



# example existing data structure ("pool", primary key / foreign key constraint on token data):
id: solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
address: 4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3
name: "WORTHLESS / SOL"
dex_id: "pumpswap"
base_token_id: **network_address**
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 5095.2274
created_at: "2025-09-08T20:09:26Z"
last_updated: 

# example single item in JSON array:
{
    "id": "solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3",
    "type": "pool",
    "attributes": {
    "base_token_price_usd": "0.00000643332102829474483760551528410043118666970110576379084202492026",
    "base_token_price_native_currency": "0.0000000298229263746505",
    "quote_token_price_usd": "215.717295730008181508988345998825795099822115726",
    "quote_token_price_native_currency": "1.0",
    "base_token_price_quote_token": "0.00000002982292637",
    "quote_token_price_base_token": "33531250.0",
    "address": "4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3",
    "name": "WORTHLESS / SOL",
    "pool_created_at": "2025-09-08T20:09:26Z",
    "fdv_usd": "6433.321028",
    "market_cap_usd": null,
    "price_change_percentage": {
        "m5": "0",
        "m15": "0.004",
        "m30": "0.004",
        "h1": "0.004",
        "h6": "0.004",
        "h24": "0.004"
    },
    "transactions": {
        "m5": {
        "buys": 0,
        "sells": 0,
        "buyers": 0,
        "sellers": 0
        },
        "m15": {
        "buys": 1,
        "sells": 2,
        "buyers": 1,
        "sellers": 2
        },
        "m30": {
        "buys": 1,
        "sells": 2,
        "buyers": 1,
        "sellers": 2
        },
        "h1": {
        "buys": 1,
        "sells": 2,
        "buyers": 1,
        "sellers": 2
        },
        "h6": {
        "buys": 1,
        "sells": 2,
        "buyers": 1,
        "sellers": 2
        },
        "h24": {
        "buys": 1,
        "sells": 2,
        "buyers": 1,
        "sellers": 2
        }
    },
    "volume_usd": {
        "m5": "0.0",
        "m15": "1495.5952833145",
        "m30": "1495.5952833145",
        "h1": "1495.5952833145",
        "h6": "1495.5952833145",
        "h24": "1495.5952833145"
    },
    "reserve_in_usd": "5095.2274"
}

# "network" API Options
network *
string
(path)

network id from /networks list

Example: solana

# "include" API Parameter
include
string
(query)
network id from /networks list

Attributes for related resources to include, which will be returned under the top-level "included" key

Available resources: base_token, quote_token, dex
Example: base_token,quote_token

# "page" API Parameter
integer
(query)

Page through results (maximum: 10)

curl -X 'GET' \
  'https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2C%20quote_token%2C%20dex&page=10' \
  -H 'accept: application/json'

### Field Definitions:
id*
solana_4KzUMzZvxX4eY99SnvwWTgSc5QLoMDCFmsNjFnuxmmJ3

type

name*
WORTHLESS / SOL

base_token_price_usd
base_token_price_native_currency
quote_token_price_usd
quote_token_price_native_currency

address*
 XXXXXX - TODO, specs are required. 
 
2nXahcBAsDN5nUSpHxZNM8C7KpHae7kUwbAPXjnqpump

reserve_in_usd*
5095.2274

pool_created_at
fdv_usd
market_cap_usd
price_change_percentage_h1
price_change_percentage_h24
transactions_h1_buys
transactions_h1_sells
transactions_h24_buys
transactions_h24_sells
volume_usd_h24

dex_id*
pumpswap

base_token_id*
solana_BZJwxWB1YMsY5whCnGsVVyfvv3mkvqUrDckz3cGtR9MB

quote_token_id*
solana_So11111111111111111111111111111111111111112

network_id

created_at*
"8/30/2025  2:41:56 AM"

last_updated*
"9/2/2025 7:39"

48caJmZzkhuzVqWMoiJhPoc8DkDi66Ut8aVXkroT9vHV
Fv73EXJBRfctJzLVC3P7uQP6er6JU8b4KtDr4LQFpump

### END TODO 2


