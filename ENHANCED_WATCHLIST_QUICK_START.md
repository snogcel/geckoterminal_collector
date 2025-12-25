# Enhanced Watchlist Quick Start Guide

## ✅ **Setup Complete!**

The Enhanced Watchlist Collector has been successfully integrated into your scheduler system. Here's how to use it:

## **Prerequisites**

1. **Database Table**: Ensure the table exists
   ```bash
   python create_enhanced_watchlist_table.py
   ```

2. **Configuration**: Your `config.yaml` should have:
   ```yaml
   enhanced_watchlist:
     enabled: true
     interval: "1h"
     sources: ["reference", "lowcap", "micro", "midcap", "oldlowcap", "oldmicro"]
   ```

3. **Source Files**: Create CSV files with naming pattern:
   - `watchlist_updated_reference.csv`
   - `watchlist_updated_lowcap.csv` 
   - `watchlist_updated_micro.csv`
   - etc.

## **Quick Commands**

### **Test Collection (Mock Mode)**
```bash
# Test with mock data (no real API calls)
python -m examples.cli_with_scheduler collect-enhanced-watchlist --mock
```

### **Run Real Collection**
```bash
# Collect from all configured sources
python -m examples.cli_with_scheduler collect-enhanced-watchlist

# Collect from specific sources only
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "reference,lowcap"
```

### **Start Automatic Scheduler**
```bash
# Start scheduler for automatic hourly collection
python -m examples.cli_with_scheduler start

# Start with mock mode for testing
python -m examples.cli_with_scheduler start --mock
```

### **Check Status**
```bash
# Show scheduler status
python -m examples.cli_with_scheduler status

# Show rate limiting status
python -m examples.cli_with_scheduler rate-limit-status
```

## **Expected Output**

### **Successful Collection**
```
=== Enhanced Watchlist Collection Results ===
Sources: reference, lowcap, micro
Success: True
Total Records: 300
Collection Time: 2025-12-17 17:00:00+00:00

=== Collection Details ===
Sources Processed: 3
Entries Processed: 300
Addresses Resolved: 300
API Calls Made: 300
Resolution Rate: 100.0%

=== Rate Usage ===
Daily Usage: 15.2%
Total Daily Requests: 1520
```

## **File Structure**

Your project should have:
```
├── config.yaml                           # Main configuration
├── enhanced_watchlist.csv                # Sample data (for old test)
├── watchlist_updated_reference.csv       # Reference source data
├── watchlist_updated_lowcap.csv         # Low cap source data
├── watchlist_updated_micro.csv          # Micro cap source data
├── watchlist_updated_midcap.csv         # Mid cap source data
├── watchlist_updated_oldlowcap.csv      # Old low cap source data
├── watchlist_updated_oldmicro.csv       # Old micro source data
└── examples/
    └── cli_with_scheduler.py             # Main CLI scheduler
```

## **CSV File Format**

Each `watchlist_updated_{source}.csv` file should have:
```csv
tokenSymbol,tokenName,poolAddress,dex,price,marketCap,liquidity,volume,priceChange5m,priceChange1h,priceChange6h,priceChange24h,transactions,makers,age,detailUrl
DINO,DINOSOL,26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o,pumpswap,0.001066,938000,130000,1100000,-0.34,-4.74,3.54,75.59,29622,3840,12d,/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o
```

## **Database Queries**

### **Check Recent Collections**
```sql
SELECT 
    source,
    COUNT(*) as entries,
    MAX(collected_at) as latest_collection
FROM enhanced_watchlist_history 
WHERE collected_at >= NOW() - INTERVAL '24 hours'
GROUP BY source;
```

### **View Recent Entries**
```sql
SELECT 
    source,
    ranking,
    token_symbol,
    price,
    market_cap,
    price_change_24h,
    collected_at
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '1 hour'
ORDER BY source, ranking
LIMIT 20;
```

## **Troubleshooting**

### **Issue: Source Files Not Found**
```
✗ Source file not found: watchlist_updated_reference.csv
```
**Solution**: Create the CSV files with the expected naming pattern

### **Issue: Database Table Missing**
```
relation "enhanced_watchlist_history" does not exist
```
**Solution**: Run `python create_enhanced_watchlist_table.py`

### **Issue: Rate Limiting**
```
Rate limiting errors in logs
```
**Solution**: Check status and reset if needed
```bash
python -m examples.cli_with_scheduler rate-limit-status
python -m examples.cli_with_scheduler reset-rate-limiter --collector enhanced_watchlist
```

## **Production Usage**

### **Hourly Automatic Collection**
```bash
# Start the scheduler to run every hour
python -m examples.cli_with_scheduler start
```

### **Monitor Collection Health**
```bash
# Check status regularly
python -m examples.cli_with_scheduler status

# Monitor logs
tail -f logs/collector.log | grep enhanced_watchlist
```

### **Data Analysis**
```sql
-- Analyze token performance across sources
SELECT 
    token_symbol,
    COUNT(DISTINCT source) as source_count,
    AVG(ranking) as avg_ranking,
    AVG(price_change_24h) as avg_24h_change
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '7 days'
GROUP BY token_symbol
HAVING COUNT(DISTINCT source) > 1
ORDER BY avg_ranking;
```

## **Key Features**

✅ **Multi-Source Support**: 6 different market segments  
✅ **Historical Tracking**: Complete ranking and price history  
✅ **Rate Limiting**: Automatic API protection  
✅ **Scheduler Integration**: Automatic hourly collection  
✅ **Mock Mode**: Testing without API calls  
✅ **Comprehensive Monitoring**: Status and error tracking  

The system is now ready for production use with your historical data going back to September 7th, 2025! 🚀