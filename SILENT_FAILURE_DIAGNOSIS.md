# Diagnosing Silent Failures in Enhanced Watchlist Collection

## The Problem

Entries in your `enhanced_watchlist.csv` are **silently failing** to populate the `pools` table. The system logs:
```
"Skipping unresolved pool data for ADDRESS; continuing with next row"
```

But doesn't tell you:
- Which entries failed
- Why they failed
- What addresses were affected

## Root Cause

The `database_address_resolver.py` tries to resolve each token's address by looking it up in:
1. `pools` table
2. `tokens` table  
3. `enhanced_watchlist_history` table

If the address **isn't found in ANY of these tables**, the entry is **silently skipped** with just a log message:

```python
if not pool_data:
    logger.info(f"Skipping unresolved pool data for {address}; continuing with next row")
    return None  # ← Entry is silently dropped
```

## Why This Happens

### Scenario 1: Address Not in Database (Most Common)

Token addresses in your CSV aren't in your database yet because:
- **New tokens** that appeared after last collection cycle
- **Never collected** by other collectors (new_pools_collector, etc.)
- **Filtered out** by collection criteria
- **Data gap** - database not fully populated

### Scenario 2: Invalid detailUrl Format

CSV has malformed `detailUrl` fields:
- Empty/null values
- Wrong format (not `/solana/ADDRESS`)
- Missing network prefix

## Diagnostic Tool

I've created a tool to identify exactly which entries are failing and why:

```bash
python diagnose_watchlist_failures.py enhanced_watchlist.csv
```

### What It Checks

1. ✅ **Valid detailUrl format** - Can address be extracted?
2. ✅ **Address in pools table** - Is it a known pool?
3. ✅ **Address in tokens table** - Is it a known token?
4. ✅ **Address in history table** - Was it collected before?

### Sample Output

```
=== RESULTS ===
Total rows in CSV: 71
✅ Valid entries (can be resolved): 51
❌ Invalid detailUrl format: 0
⚠️  Not found in database: 20

=== NOT FOUND IN DATABASE (20 entries) ===

🔴 ACTIVE ENTRIES NOT IN DATABASE (1):

Row 5: shooort
  Address: 721ef9rst2coaxvg7tlx1q1xfmwsqjtwwr3qaq82yaer
  Detail URL: /solana/721EF9RST2coAxVG7tLX1q1XFmwSqjtwwR3QAQ82yAER
  Liquidity: $8266.57
  Score: 57

⚪ INACTIVE ENTRIES NOT IN DATABASE (19):
[List of inactive entries...]

=== ANALYSIS ===
Resolution success rate: 71.8%

⚠️  ISSUE: Addresses Not in Database

20 entries have valid addresses but aren't in database.

Causes:
1. TIMING: Tokens appeared after last collection cycle
2. NEW TOKENS: Never been collected before
3. FILTERED OUT: Rejected by other collectors
4. DATA GAP: Database not fully populated
```

## Solution Steps

### Step 1: Run Diagnostic

```bash
# Analyze your CSV file
python diagnose_watchlist_failures.py enhanced_watchlist.csv
```

This will show you:
- How many entries are failing
- Which specific addresses aren't in database
- Whether they're active or inactive
- Full list of problematic addresses

### Step 2: Populate Missing Data

If addresses aren't in database, run collectors to populate them:

```bash
# Collect new pools (populates pools & tokens tables)
python -m examples.cli_with_scheduler run-once --collector new_pools_solana

# Or collect from all sources
python -m examples.cli_with_scheduler collect-new-pools --network solana
```

### Step 3: Re-run Enhanced Watchlist Collector

After populating the database:

```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

Now the previously failing entries should resolve successfully.

### Step 4: Verify Resolution

```bash
# Run diagnostic again
python diagnose_watchlist_failures.py enhanced_watchlist.csv

# Should show improved success rate
```

## Understanding the Results

### Good Results ✅

```
Resolution success rate: 95%
⚪ Inactive entries not in database: 3
```

**Interpretation**: System is healthy. A few inactive/old tokens missing from database is normal.

**Action**: None needed.

### Needs Attention ⚠️

```
Resolution success rate: 70%
🔴 Active entries not in database: 5
⚪ Inactive entries not in database: 15
```

**Interpretation**: Some active tokens can't be resolved. They won't be added to watchlist.

**Action**: 
1. Run collectors to populate database
2. Check if these are very new tokens
3. Review rejection logs

### Critical Issue 🔴

```
Resolution success rate: 40%
🔴 Active entries not in database: 20
```

**Interpretation**: Major data pipeline issue. Many entries failing.

**Action**:
1. Check collector status and logs
2. Verify database population
3. Review CSV generation process

## Why Silent Failures Happen

The enhanced watchlist collector uses a **database-first approach**:

```
CSV Entry → Extract address → Look up in database → If found: Use data
                                                 → If NOT found: Skip (silent)
```

**Benefits**:
- No API calls needed (fast)
- Uses existing database cache
- Efficient for known tokens

**Drawback**:
- Unknown tokens are silently skipped
- No visibility into failures
- Requires database to be pre-populated

## Checking Collector Logs

Look for these patterns in logs:

```bash
# Silent failures
grep "Skipping unresolved pool data" /var/log/collector.log

# Count failures
grep "Skipping unresolved pool data" /var/log/collector.log | wc -l

# See specific addresses
grep "Skipping unresolved pool data" /var/log/collector.log | tail -20
```

## Preventing Silent Failures

### 1. Keep Database Populated

Run collectors regularly:
```bash
# Every hour (cron job)
0 * * * * python -m examples.cli_with_scheduler run-once --collector new_pools_solana
```

### 2. Run Diagnostic After Each Collection

```bash
# In your workflow
python -m examples.cli_with_scheduler collect-enhanced-watchlist
python diagnose_watchlist_failures.py enhanced_watchlist.csv
```

### 3. Monitor Success Rate

Set up alerts if success rate drops below 80%

### 4. Collect Before Filtering

Ensure new_pools_collector runs BEFORE enhanced_watchlist_collector:

```bash
# Good workflow
python -m examples.cli_with_scheduler run-once --collector new_pools_solana  # Populate DB first
python -m examples.cli_with_scheduler collect-enhanced-watchlist  # Then filter/add to watchlist
```

## Your Specific Case

Looking at your CSV data:
```
Row 5: shooort
- Active: True
- Liquidity: $8,266
- Score: 57
- Address: 721ef9rst2coaxvg7tlx1q1xfmwsqjtwwr3qaq82yaer
```

This is likely a **NEW TOKEN** that:
1. Just appeared in GMGN data
2. Hasn't been collected by new_pools_collector yet
3. Therefore isn't in your database
4. Gets silently skipped

**Solution**: Run new_pools_collector to add it to database, then re-run enhanced_watchlist_collector.

## Summary

**Problem**: Entries silently fail because addresses aren't in database

**Diagnostic**: `python diagnose_watchlist_failures.py`

**Solution**: Populate database with collectors, then re-run watchlist collection

**Prevention**: Run collectors in correct order and monitor success rates

The diagnostic tool will give you complete visibility into which entries are failing and why! 🎯
