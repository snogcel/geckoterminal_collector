


# Comprehensive New Pools & Watchlist System Testing

This document outlines the comprehensive testing approach for the integrated new pools collection, history data capture, signal analysis, and watchlist functionality.

## Overview

The testing suite now includes:
- **Watchlist CRUD operations** - Complete create, read, update, delete functionality
- **New pools collection** - Enhanced collection with auto-watchlist integration
- **History data capture** - Systematic tracking in new_pools_history table
- **Signal analysis** - Trading signal detection and scoring
- **Database validation** - Performance and data quality checks
- **Integration testing** - End-to-end workflow validation

## Testing Scripts Available

### 1. Comprehensive System Test
```bash
python test_comprehensive_new_pools_system.py
```
This is the main test script that covers all aspects of the system.

### 2. Debug New Pools History Issues
```bash
python debug_new_pools_history.py
```
Focused debugging script for new_pools_history data capture issues.

### 3. Original Watchlist Test
```bash
python examples/test_enhanced_watchlist_cli.py
```
Original comprehensive watchlist functionality test.

## Recommended Testing Approach
1. Use the Existing Test Script
The most comprehensive way is to run the existing test script:

python examples/test_enhanced_watchlist_cli.py
This script tests all watchlist operations:

Adding entries with all fields
Listing in different formats (table, CSV, JSON)
Updating specific fields
Removing entries
Verification of changes

2. Manual CLI Testing
For more targeted testing, use these CLI commands:

# Add a test entry
python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_test123 --symbol TEST --name "Test Token" --active true

# List all entries
python -m gecko_terminal_collector.cli list-watchlist --format table

# List only active entries
python -m gecko_terminal_collector.cli list-watchlist --active-only --format json

# Update an entry
python -m gecko_terminal_collector.cli update-watchlist --pool-id solana_test123 --name "Updated Test Token" --active false

# Remove the test entry
python -m gecko_terminal_collector.cli remove-watchlist --pool-id solana_test123 --force
3. Test with Real Pool Data
If you want to test with actual pool data from your new pools collection:

# First, collect some new pools
python -m gecko_terminal_collector.cli collect-new-pools --network solana --auto-watchlist --min-liquidity 1000

# Then list what was added to the watchlist
python -m gecko_terminal_collector.cli list-watchlist --format table

# Analyze the discovery results
python -m gecko_terminal_collector.cli analyze-pool-discovery --days 1 --format table
4. Database Verification
You can also verify the watchlist data directly in the database:

Created

test_watchlist_db.py


python test_watchlist_db.py
5. Integration Testing with New Pools Collection
Test the full workflow of discovering and adding pools to watchlist:

# Run new pools collection with auto-watchlist enabled
python -m gecko_terminal_collector.cli collect-new-pools \
  --network solana \
  --auto-watchlist \
  --min-liquidity 5000 \
  --min-volume 1000 \
  --min-activity-score 70 \
  --dry-run

# If the dry-run looks good, run it for real
python -m gecko_terminal_collector.cli collect-new-pools \
  --network solana \
  --auto-watchlist \
  --min-liquidity 5000 \
  --min-volume 1000 \
  --min-activity-score 70
Quick Start Testing Sequence
Here's a quick sequence to test everything:

# 1. Run the comprehensive test script
python examples/test_enhanced_watchlist_cli.py

# 2. Check database directly
python test_watchlist_db.py

# 3. Test with real data collection
python -m gecko_terminal_collector.cli collect-new-pools --network solana --auto-watchlist --dry-run

# 4. Verify the results
python -m gecko_terminal_collector.cli list-watchlist --format table
## New Pools History Testing

### Debug Common Issues
The `debug_new_pools_history.py` script specifically helps identify:

1. **Table Structure Issues** - Missing columns, indexes, constraints
2. **Collection Gaps** - Missing data collection periods
3. **Data Quality Problems** - Null values, anomalies, inconsistencies
4. **Signal Analysis Issues** - Missing signal scores, trend data
5. **Performance Problems** - Slow queries, missing indexes
6. **Pool Lifecycle Issues** - Unusual tracking patterns

### Key Areas to Monitor

#### Data Capture Issues
```bash
# Check for recent collection activity
SELECT COUNT(*) FROM new_pools_history WHERE collected_at > NOW() - INTERVAL '1 hour';

# Look for data quality issues
SELECT COUNT(*) FROM new_pools_history 
WHERE collected_at > NOW() - INTERVAL '6 hours'
AND (volume_usd_h24 IS NULL OR reserve_in_usd IS NULL);
```

#### Signal Analysis Validation
```bash
# Check signal score distribution
SELECT 
    AVG(signal_score) as avg_score,
    COUNT(CASE WHEN signal_score >= 70 THEN 1 END) as high_signals
FROM new_pools_history 
WHERE collected_at > NOW() - INTERVAL '6 hours'
AND signal_score IS NOT NULL;
```

#### Collection Frequency
```bash
# Verify collection is happening regularly
SELECT 
    DATE_TRUNC('hour', collected_at) as hour,
    COUNT(*) as records
FROM new_pools_history
WHERE collected_at > NOW() - INTERVAL '12 hours'
GROUP BY DATE_TRUNC('hour', collected_at)
ORDER BY hour DESC;
```

## Troubleshooting Common Issues

### Issue 1: No Recent History Records
**Symptoms:** `debug_new_pools_history.py` shows no recent records
**Solutions:**
- Check if new pools collector is running
- Verify API connectivity
- Check database connection
- Review collector configuration

### Issue 2: Missing Signal Analysis Data
**Symptoms:** signal_score, volume_trend, liquidity_trend are NULL
**Solutions:**
- Verify signal analysis is enabled in config
- Check SignalAnalyzer initialization
- Review signal calculation logic
- Test with sample data

### Issue 3: Collection Gaps
**Symptoms:** Missing data for certain time periods
**Solutions:**
- Check scheduler configuration
- Review error logs
- Verify system resources
- Check API rate limits

### Issue 4: Data Quality Issues
**Symptoms:** Null values, anomalous data, inconsistent formats
**Solutions:**
- Review data validation logic
- Check API response format changes
- Verify data transformation code
- Add additional validation rules

## Complete Testing Workflow

### Step 1: Run Comprehensive Test
```bash
python test_comprehensive_new_pools_system.py
```

### Step 2: Debug Specific Issues
```bash
python debug_new_pools_history.py
```

### Step 3: Test Individual Components
```bash
# Test new pools collection
python -m gecko_terminal_collector.cli collect-new-pools --network solana --dry-run

# Test watchlist integration
python examples/test_enhanced_watchlist_cli.py

# Test signal analysis
python -m gecko_terminal_collector.cli analyze-pool-signals --network solana --hours 6
```

### Step 4: Validate Database State
```bash
python test_watchlist_db.py
```

This comprehensive testing approach will help you identify and resolve issues with the new_pools_history data capture process while ensuring the entire integrated system works correctly.