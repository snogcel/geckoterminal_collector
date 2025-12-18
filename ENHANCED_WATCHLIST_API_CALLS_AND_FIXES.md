# Enhanced Watchlist API Calls and Database Fixes

## API Calls Used

The Enhanced Watchlist Collector makes **one API call per entry** to resolve token addresses:

### API Call Details

**Method**: `get_pool_by_network_address(network, pool_address)`

**Endpoint**: `GET /api/v2/networks/{network}/pools/{pool_address}`

**Purpose**: Resolve base_token and quote_token addresses from the pool address extracted from the detail URL

**Example**:
```
GET /api/v2/networks/solana/pools/26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o
```

**Response Structure**:
```json
{
  "data": {
    "id": "solana_26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o",
    "type": "pool",
    "attributes": {
      "name": "DINO / SOL",
      "address": "26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o",
      "reserve_in_usd": "130000",
      ...
    },
    "relationships": {
      "base_token": {
        "data": {
          "id": "solana_base_token_address_here",
          "type": "token"
        }
      },
      "quote_token": {
        "data": {
          "id": "solana_quote_token_address_here",
          "type": "token"
        }
      }
    }
  }
}
```

### Rate Limiting

With default configuration:
- **1 second delay** between API calls
- **Batch processing**: 10 entries per batch
- **Source delay**: 2 seconds between different sources

For 100 entries per source × 6 sources = 600 API calls per hour:
- Approximately **10 minutes** of API call time per collection cycle
- Well within GeckoTerminal's rate limits (30 calls/minute)

## Database Table Missing Error Fix

### Problem
```
psycopg2.errors.UndefinedTable: relation "enhanced_watchlist_history" does not exist
```

### Solution 1: Run the Table Creation Script

```bash
python create_enhanced_watchlist_table.py
```

This script will:
1. Connect to your database
2. Create only the `enhanced_watchlist_history` table
3. Verify the table was created successfully
4. List all columns in the new table

### Solution 2: Recreate All Tables

If you want to recreate all tables (⚠️ **WARNING: This will drop existing data**):

```python
from gecko_terminal_collector.database.models import Base
from gecko_terminal_collector.database.connection import DatabaseConnection
from gecko_terminal_collector.config.manager import ConfigManager

# Load config
config_manager = ConfigManager()
config = config_manager.load_config()

# Create connection
connection = DatabaseConnection(config.database)
connection.initialize()

# Drop and recreate all tables
Base.metadata.drop_all(bind=connection.engine)
Base.metadata.create_all(bind=connection.engine)
```

### Solution 3: Manual SQL Creation

If you prefer to create the table manually:

```sql
CREATE TABLE enhanced_watchlist_history (
    id SERIAL PRIMARY KEY,
    
    -- Source and identification
    source VARCHAR(50) NOT NULL,
    ranking INTEGER NOT NULL,
    
    -- Token and pool identification
    token_symbol VARCHAR(50) NOT NULL,
    token_name VARCHAR(200),
    pool_address VARCHAR(255) NOT NULL,
    base_token_address VARCHAR(255),
    quote_token_address VARCHAR(255),
    quote_token_symbol VARCHAR(50),
    
    -- Network and DEX information
    network VARCHAR(50) NOT NULL,
    dex VARCHAR(100) NOT NULL,
    
    -- Price and market data
    price NUMERIC(30, 18),
    market_cap NUMERIC(20, 4),
    liquidity NUMERIC(20, 4),
    volume NUMERIC(20, 4),
    
    -- Price changes
    price_change_5m NUMERIC(10, 4),
    price_change_1h NUMERIC(10, 4),
    price_change_6h NUMERIC(10, 4),
    price_change_24h NUMERIC(10, 4),
    
    -- Activity metrics
    transactions INTEGER,
    makers INTEGER,
    age VARCHAR(50),
    
    -- URLs and metadata
    detail_url VARCHAR(500),
    
    -- Timestamps
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    data_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Additional metadata
    metadata_json TEXT DEFAULT '{}',
    
    -- Unique constraint
    CONSTRAINT uq_enhanced_watchlist_history_source_ranking_time 
        UNIQUE(source, ranking, collected_at)
);

-- Create indexes for common queries
CREATE INDEX idx_enhanced_watchlist_history_source ON enhanced_watchlist_history(source);
CREATE INDEX idx_enhanced_watchlist_history_token_symbol ON enhanced_watchlist_history(token_symbol);
CREATE INDEX idx_enhanced_watchlist_history_collected_at ON enhanced_watchlist_history(collected_at);
CREATE INDEX idx_enhanced_watchlist_history_ranking ON enhanced_watchlist_history(ranking);
```

## Mock Client Setup for Testing

To test the enhanced watchlist collector without making real API calls, create a mock data file:

### Create Mock Pool Data File

**File**: `specs/get_pool_by_network_address.csv`

```csv
id,type,address,name,base_token_id,quote_token_id,base_token_address,quote_token_address,reserve_in_usd,volume_24h,price_change_24h
solana_26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o,pool,26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o,DINO / SOL,solana_DinoBase123,solana_So11111111111111111111111111111111111112,DinoBase123,So11111111111111111111111111111111111112,130000,1100000,75.59
solana_EDuApEtcGbaeqKvAsTtrX1ERU12U1PB5yJpRCD3TeZxM,pool,EDuApEtcGbaeqKvAsTtrX1ERU12U1PB5yJpRCD3TeZxM,PEPPA / SOL,solana_PeppaBase456,solana_So11111111111111111111111111111111111112,PeppaBase456,So11111111111111111111111111111111111112,224000,285000,663
```

### Update Test Script

The test script should use `use_mock=True` when initializing the collector:

```python
collector = EnhancedWatchlistCollector(
    config=config,
    db_manager=db_manager,
    metadata_tracker=metadata_tracker,
    use_mock=True,  # This uses MockGeckoTerminalClient
    watchlist_sources=['reference', 'lowcap', 'micro']
)
```

## Testing Workflow

### 1. Create the Database Table
```bash
python create_enhanced_watchlist_table.py
```

### 2. Create Mock Data File
```bash
# Create the specs directory if it doesn't exist
mkdir -p specs

# Create the mock pool data file
# (Use the CSV content shown above)
```

### 3. Run the Test
```bash
python test_enhanced_watchlist_history.py
```

### Expected Output

```
2025-12-17 16:00:00 - INFO - Created test file: watchlist_updated_reference.csv
2025-12-17 16:00:00 - INFO - Created test file: watchlist_updated_lowcap.csv
2025-12-17 16:00:00 - INFO - Created test file: watchlist_updated_micro.csv
2025-12-17 16:00:01 - INFO - Database manager initialized successfully
2025-12-17 16:00:01 - INFO - Starting enhanced watchlist collection test...
2025-12-17 16:00:01 - INFO - Processing source: reference from file: watchlist_updated_reference.csv
2025-12-17 16:00:02 - INFO - Processed 2 valid entries from reference
2025-12-17 16:00:02 - INFO - Source reference: 2 entries stored
2025-12-17 16:00:03 - INFO - Processing source: lowcap from file: watchlist_updated_lowcap.csv
2025-12-17 16:00:04 - INFO - Processed 2 valid entries from lowcap
2025-12-17 16:00:04 - INFO - Source lowcap: 2 entries stored
2025-12-17 16:00:05 - INFO - Processing source: micro from file: watchlist_updated_micro.csv
2025-12-17 16:00:06 - INFO - Processed 2 valid entries from micro
2025-12-17 16:00:06 - INFO - Source micro: 2 entries stored
2025-12-17 16:00:06 - INFO - Enhanced watchlist collection completed: 6 total entries stored
2025-12-17 16:00:06 - INFO - Collection Result: Success
2025-12-17 16:00:06 - INFO - Records Collected: 6
```

## Production Deployment

### 1. Ensure Database Table Exists
```bash
python create_enhanced_watchlist_table.py
```

### 2. Place Source Files
Ensure your 6 source CSV files are in the correct location:
- `watchlist_updated_reference.csv`
- `watchlist_updated_lowcap.csv`
- `watchlist_updated_micro.csv`
- `watchlist_updated_midcap.csv`
- `watchlist_updated_oldlowcap.csv`
- `watchlist_updated_oldmicro.csv`

### 3. Configure Collection
Update `config.yaml`:
```yaml
enhanced_watchlist:
  enabled: true
  interval: "1h"
  sources:
    - "reference"
    - "lowcap"
    - "micro"
    - "midcap"
    - "oldlowcap"
    - "oldmicro"
```

### 4. Run Collection
```bash
# One-time collection
python -m gecko_terminal_collector.cli collect-enhanced-watchlist

# Or add to scheduler for hourly collection
python examples/cli_with_scheduler.py start
```

## Monitoring

### Check Collection Status
```sql
SELECT 
    collector_type,
    last_run,
    last_success,
    run_count,
    error_count,
    success_rate
FROM collection_metadata
WHERE collector_type = 'enhanced_watchlist_collector';
```

### Check Historical Data
```sql
SELECT 
    source,
    COUNT(*) as entry_count,
    MIN(collected_at) as earliest,
    MAX(collected_at) as latest
FROM enhanced_watchlist_history
GROUP BY source
ORDER BY source;
```

### Check Recent Entries
```sql
SELECT 
    source,
    ranking,
    token_symbol,
    price,
    market_cap,
    collected_at
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '1 hour'
ORDER BY source, ranking
LIMIT 20;
```

## Troubleshooting

### Issue: API Rate Limit Errors
**Solution**: Increase delays in config:
```yaml
enhanced_watchlist:
  rate_limiting:
    delay_between_calls: 2.0  # Increase from 1.0
    delay_between_sources: 5.0  # Increase from 2.0
```

### Issue: Missing Token Addresses
**Solution**: Check if pool addresses are valid and exist in GeckoTerminal

### Issue: Duplicate Entry Errors
**Solution**: The unique constraint prevents duplicates. This is expected behavior and entries are skipped.

### Issue: Slow Collection
**Solution**: Reduce batch size or increase delays:
```yaml
enhanced_watchlist:
  rate_limiting:
    batch_size: 5  # Reduce from 10
```