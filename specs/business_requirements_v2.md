### Requirement 2: (from business_requirements.md)
**User Story:**
I would like to monitor the top pools by network_dex every hour, this interval (and others within the system as a whole) should be configurable. The result of these queries are outlined the /specs folder in get_top_pools_by_network_dex_heaven.csv and get_top_pools_by_network_dex_pumpswap.csv for the DEX Targets "heaven" and "pumpswap". These files were generated using the following SDK commands:

API Schema: /networks/{network}/dexes/{dex}/pools
await client.get_top_pools_by_network_dex("solana", "pumpswap")
await client.get_top_pools_by_network_dex("solana", "heaven")



### Requirement 7: QLib (from business_requirements.md)
**User Story:**
As an analyst, I would like to use QLib to extract and parse the data collected from this system for predictive modeling purposes. I have placed a variety of scripts that are designed for this purpose into the /examples/qlib_scripts folder. The closest fit for this use case is likely contained in /examples/qlib_scripts/data_collector/crypto. This data collector is designed for Coin Gecko (which is related to GeckoTerminal) and could potentially allow future extensibility, so it seems like something modeled after this would be ideal.


#


### START

### TODO 4: Review existing spec for case-sensitive adjustments to this system. [IN_PROGRESS]

### TODO 5: See what's involved in migrating from SQLite to Postgres

### TODO 1: Review QLib Data Collector Test Coverage (https://github.com/man-c/pycoingecko) [PENDING]

### TODO 6: Summarize initial review of QA Tracking Sheet in /specs/QA folder: QA_09_01_2025.xlsx





# Watchlist -- cannot be troubleshoot, will consult with Kiro if necessary





### BACKLOG:

## Review how this aligns with QLib-Server

## re-review "info_recently_updated" API Route [BACKLOG LIST 1]

### END Backlog

### END











##### TODO 1 ###
## Existing Process from examples/qlib_scripts/data_collector/crypto/README.md

## TODO pull tests from this library at https://github.com/man-c/pycoingecko/tree/master/tests

# download from https://api.coingecko.com/api/v3/
python collector.py download_data --source_dir ~/.qlib/crypto_data/source/1d --start 2015-01-01 --end 2021-11-30 --delay 1 --interval 1d

## collector.py

# utilizes pycoingecko library (SDK at https://github.com/man-c/pycoingecko)

# fetches coin symbols with get_coins_markets

# fetches coin data using symbols, calls get_coin_market_chart_by_id

# uses get_cg_crypto_symbols to fetch 1d data

# normalizes data using CryptoNormalize

# get daily data example:
# python collector.py download_data --source_dir ~/.qlib/crypto_data/source/1d --start 2015-01-01 --end 2021-11-30 --delay 1 --interval 1d

# normalize
python collector.py normalize_data --source_dir ~/.qlib/crypto_data/source/1d --normalize_dir ~/.qlib/crypto_data/source/1d_nor --interval 1d --date_field_name date

# dump data
cd qlib/scripts
python dump_bin.py dump_all --csv_path ~/.qlib/crypto_data/source/1d_nor --qlib_dir ~/.qlib/qlib_data/crypto_data --freq day --date_field_name date --include_fields prices,total_volumes,market_caps

### END TODO 1


















##### BACKLOG LIST ##

### BACKLOG LIST 1: info_recently_updated API route on GeckoTerminal API

# Interesting that some tokens displayed on this list, but others didn't.

# Likely why it wasn't integrated into the SDK, but worth having another look at

# Build a route manually, but why not try to use the SDK first? -- network token identified: Fv73EXJBRfctJzLVC3P7uQP6er6JU8b4KtDr4LQFpump
https://api.geckoterminal.com/api/v2/tokens/info_recently_updated?include=network&network=solana

# Example File: info_recently_updated.json

id: solana_Fv73EXJBRfctJzLVC3P7uQP6er6JU8b4KtDr4LQFpump
type: token
attributes_address: Fv73EXJBRfctJzLVC3P7uQP6er6JU8b4KtDr4LQFpump
attributes_name: brickcoin
attributes_symbol: brick
attributes_decimals: 
attributes_image_url: https://coin-images.coingecko.com/coins/images/69015/large/md9knepw3yo2vovd381r5mer90cv.?1757256564
attributes_coingecko_coin_id: brickcoin
attributes_websites: ['https://www.brickbrick.org']
attributes_discord_url: https://discord.com/invite/switchboardxyz
attributes_telegram_handle: 
attributes_twitter_handle: by_brick_sol
attributes_description: building brick by brick
attributes_gt_score: 79.93889908
attributes_metadata_updated_at: 2025-09-07T14:50:03Z
relationships_network_data_id: solana
relationships_network_data_type: network

# info_recently_updated
/tokens/info_recently_updated
Get most recently updated 100 tokens info across all networks

include
string
(query)

network
string
(query)

### END BACKLOG LIST 1




