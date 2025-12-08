# Summary

Hello, I've found several improvements that should be made to the new_pools_history process (pagination and expanded fields). This will require an updated table schema to support more granular data readings (m5, m15m, m30, h1, h6, h24) as well as an update to support pagination. The overall goal of this change is to make the new_pools_history process more efficient and to catch pools that are not being captured with the existing process.

Secondly, I am seeing that the auto-watchlist functionality works well for flagging new pools, but over time creates issues with API rate limits due to the lower survivorship rate of these pools. I'd like to propose creating OHLCV_data_history and trades_history tables, to track whether or not NEW data has been observed for these tables. If no new data has been observed for some configurable period of time, then the entry should be removed from the watchlist.

Finally, these changes should remain aligned with the installation process outlined in installation.md


# Requirement 1: OHLCV_data_history and trades_history tables

Disable watchlist entry when no new data OHLCV or trade data is observed over a 30 minute period. It's been observed that the survivorship rate of these pools is often very short-lived, and by keeping them active I am running into rate limiting problems. I think the best way to accomplish this will be to create a OHLCV_data_history and trades_history and use that as triggers to remove entries from the watchlist.

# Requirement 2: Enable pagination for new_pools_history
Initial research shows that the following queries will provide structured data for the last 5 minutes of trading activity:

https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=1
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=2
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=3
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=4
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=5
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=6
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=7
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=8
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=9
https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token%2Cquote_token%2Cdex&include_gt_community_data=false&page=10

## Expand data being collected

### Presently new_pools_history uses the following schema:

id
pool_id
collected_at
discovery_source
api_response_data
address
base_token_id
base_token_price_native_currency
base_token_price_usd
dex_id
fdv_usd
market_cap_usd
name
network_id
pool_created_at
price_change_percentage_h1
price_change_percentage_h24
quote_token_id
quote_token_price_native_currency
quote_token_price_usd
reserve_in_usd
transactions_h1_buys
transactions_h1_sells
transactions_h24_buys
transactions_h24_sells
type
volume_usd_h24
signal_score
volume_trend
liquidity_trend
momentum_indicator
activity_score
volatility_score

### The JSON files provided in the /specs/v6/data_sample provides the following basic structure:
	
Value.id	
Value.type	
Value.attributes.base_token_price_usd	
Value.attributes.base_token_price_native_currency	
Value.attributes.quote_token_price_usd	
Value.attributes.quote_token_price_native_currency	
Value.attributes.base_token_price_quote_token	
Value.attributes.quote_token_price_base_token	
Value.attributes.address
Value.attributes.name
Value.attributes.pool_created_at
Value.attributes.fdv_usd
Value.attributes.market_cap_usd
Value.attributes.price_change_percentage.m5
Value.attributes.price_change_percentage.m15
Value.attributes.price_change_percentage.m30
Value.attributes.price_change_percentage.h1
Value.attributes.price_change_percentage.h6
Value.attributes.price_change_percentage.h24
Value.attributes.transactions.m5.buys
Value.attributes.transactions.m5.sells
Value.attributes.transactions.m5.buyers
Value.attributes.transactions.m5.sellers
Value.attributes.transactions.m15.buys
Value.attributes.transactions.m15.sells
Value.attributes.transactions.m15.buyers
Value.attributes.transactions.m15.sellers
Value.attributes.transactions.m30.buys
Value.attributes.transactions.m30.sells
Value.attributes.transactions.m30.buyers
Value.attributes.transactions.m30.sellers
Value.attributes.transactions.h1.buys
Value.attributes.transactions.h1.sells
Value.attributes.transactions.h1.buyers
Value.attributes.transactions.h1.sellers
Value.attributes.transactions.h6.buys
Value.attributes.transactions.h6.sells
Value.attributes.transactions.h6.buyers
Value.attributes.transactions.h6.sellers
Value.attributes.transactions.h24.buys
Value.attributes.transactions.h24.sells
Value.attributes.transactions.h24.buyers
Value.attributes.transactions.h24.sellers
Value.attributes.volume_usd.m5
Value.attributes.volume_usd.m15
Value.attributes.volume_usd.m30
Value.attributes.volume_usd.h1
Value.attributes.volume_usd.h6
Value.attributes.volume_usd.h24
Value.attributes.reserve_in_usd
Value.relationships.base_token.data.id
Value.relationships.base_token.data.type
Value.relationships.quote_token.data.id
Value.relationships.quote_token.data.type
Value.relationships.dex.data.id
Value.relationships.dex.data.type

The existing logic for new_pools_history should allow for this history to be tracked, however the table schema itself will need to be expanded to accommodate m5, m15m, m30, h1, h6, h24 readings.


# Requirement 3: Update existing database migration / creation scripts to include new_pools_history

The schema change outlined above is incompatible with current deployments, and should remain aligned with the steps outlined in docs/installation.md




