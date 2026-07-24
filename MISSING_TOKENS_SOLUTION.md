# Missing Tokens Investigation - Complete Solution

## Your Question

> "20 tokens not found in DB - why? I think they might have been rejected, where do I start troubleshooting?"

## Quick Answer

✅ **This is usually NORMAL behavior!**

The 20 "not found" tokens likely:
1. Became inactive before being added to database
2. Didn't meet entry criteria (low score/liquidity)
3. Were monitored but filtered out correctly

## Complete Solution

### Step 1: Get Full Token Addresses (with Diagnostic)

```bash
python -m examples.cli_with_scheduler diagnose-watchlist
```

**What you'll see**:
```
=== MISSING TOKENS BREAKDOWN ===
Active missing (⚠️  CRITICAL): 0
Inactive missing (ℹ️  Normal): 20

💾 All 20 inactive missing token addresses:
   BQYc6c5hivsPrEEmTxBVjGT16setk2gmPvbv7YBxpump
   55TLkaCjVD3if5pnMdcUN3cvUh2CaSYnXSqEinqgpump
   2E9ne8wvTebVv8JK4uCEc7VZgfGNkUjDkpcD9iCwpump
   ...
   
✅ All active tokens are in database - system is healthy!
```

**What this tells you**:
- Full addresses for each missing token (easy to copy/paste)
- Whether missing tokens are active or inactive
- If action is needed

### Step 2: Investigate WHY Tokens Are Missing

```bash
python check_rejected_tokens.py
```

**What this checks**:
1. Are tokens in `enhanced_watchlist_history` table?
   - **YES** → Token was collected but rejected (filtered out)
   - **NO** → Token was never collected

2. Why were they rejected?
   - Liquidity too low
   - Score too low
   - Duplicate entry
   - Other criteria

**Sample Output**:
```
=== RESULTS ===
Found in enhanced_watchlist_history: 5
NOT in enhanced_watchlist_history: 15

=== TOKENS COLLECTED BUT NOT ADDED TO WATCHLIST (5) ===

1. TOKEN: BQYc6c5hivsPrEEmTxBVjGT16setk2gmPvbv7YBxpump
   Symbol: TOKEN
   Liquidity: $2,500
   ⚠️  LIKELY REASON: Liquidity too low ($2,500 < $5,000)

=== TOKENS NEVER COLLECTED (15) ===
These tokens appeared briefly or were from a different source.
```

### Step 3: Investigate Specific Token

If you want to dig into a specific token:

```bash
# Replace TOKEN_ADDRESS with actual address from diagnostic
python check_rejected_tokens.py watchlist_state.json config.yaml "TOKEN_ADDRESS"
```

## Understanding the Results

### Scenario A: All Missing Tokens Are Inactive ✅

```
Active missing: 0
Inactive missing: 20
```

**Interpretation**: **SYSTEM IS HEALTHY!**
- Tokens were monitored
- Became inactive before qualifying for database
- OR didn't meet quality criteria
- Filtering is working correctly

**Action**: None needed! This is expected behavior.

### Scenario B: Some Active Tokens Are Missing ⚠️

```
Active missing: 3
Inactive missing: 17
```

**Interpretation**: **NEEDS INVESTIGATION**
- Active tokens should be in database
- They're currently monitored but not in database
- Won't receive notifications

**Action**: 
1. Check why they weren't added
2. Re-run collector if needed
3. Verify entry criteria

## Investigation Tools

### Tool 1: diagnose-watchlist (CLI)

**What it does**:
- Shows which tokens are missing
- Provides **full token addresses** for investigation
- Separates active vs inactive
- Shows deactivation reasons

**When to use**: First step to identify the problem

### Tool 2: check_rejected_tokens.py

**What it does**:
- Checks if tokens exist in `enhanced_watchlist_history`
- Analyzes rejection reasons
- Shows token details (liquidity, score, DEX, etc.)
- Provides specific recommendations

**When to use**: Deep dive after seeing missing tokens

## Common Rejection Reasons

### 1. Liquidity Too Low (Most Common)

```
Token: ABC123
Liquidity: $2,500
⚠️  Rejection: Liquidity too low ($2,500 < $5,000)
```

**Why**: System filters out low-liquidity tokens to avoid rug pulls

**Action**: Normal behavior, no action needed (unless you want to lower threshold)

### 2. Score Too Low

```
Token: DEF456
Peak score: 25
⚠️  Rejection: Score too low (25 < 30)
```

**Why**: Token didn't meet minimum quality threshold

**Action**: Normal filtering, system working correctly

### 3. Never Collected

```
Token: GHI789
Status: NOT in enhanced_watchlist_history
```

**Why**: 
- Appeared between collection cycles
- From a disabled source
- Very short-lived token

**Action**: Check source configuration if recurring pattern

## Where to Look

### 1. Enhanced Watchlist Collector Code

File: `gecko_terminal_collector/collectors/enhanced_watchlist_collector.py`

Look for:
```python
# Entry criteria
MIN_SCORE = 30  # Minimum score threshold
MIN_LIQUIDITY = 5000  # Minimum liquidity ($5K)

# Rejection logic in _process_entry()
if score < MIN_SCORE:
    logger.info(f"Score too low: {score}")
    return False

if liquidity < MIN_LIQUIDITY:
    logger.info(f"Liquidity too low: ${liquidity}")
    return False
```

### 2. Configuration File

File: `config.yaml`

Check:
```yaml
enhanced_watchlist:
  enabled: true
  sources: [reference, micro, lowcap]  # Which sources are monitored
  interval: "1h"  # Collection frequency
```

### 3. Database Tables

```sql
-- Check if token was collected
SELECT * FROM enhanced_watchlist_history 
WHERE base_token_address = 'TOKEN_ADDRESS'
ORDER BY collected_at DESC;

-- Check if token in watchlist
SELECT * FROM watchlist 
WHERE network_address = 'TOKEN_ADDRESS';
```

### 4. Collector Logs

```bash
# Search for specific token
grep "TOKEN_ADDRESS" /var/log/collector.log

# Look for rejections
grep -i "reject\|filter\|skip\|too low" /var/log/collector.log | tail -50
```

## Quick Actions

### If You Want More Tokens Included

1. **Lower thresholds** in `enhanced_watchlist_collector.py`:
   ```python
   MIN_SCORE = 20  # Was 30
   MIN_LIQUIDITY = 2000  # Was 5000
   ```

2. **Add more sources** in `config.yaml`:
   ```yaml
   sources: [reference, micro, lowcap, midcap]  # Added midcap
   ```

3. **Increase collection frequency**:
   ```yaml
   interval: "30m"  # Was "1h"
   ```

4. **Re-run collector**:
   ```bash
   python -m examples.cli_with_scheduler collect-enhanced-watchlist
   ```

### If Everything Looks Normal

If investigation shows:
- ✅ All missing tokens are inactive
- ✅ Rejection reasons are valid (low liquidity, low score)
- ✅ Active tokens all in database

**You're done! System is working correctly.** 🎉

## Summary of New Features

### 1. Enhanced Diagnostic Command

```bash
python -m examples.cli_with_scheduler diagnose-watchlist
```

**Now includes**:
- Full token addresses for easy investigation
- Active vs inactive breakdown
- Deactivation reason analysis
- Direct recommendations

### 2. New Investigation Tool

```bash
python check_rejected_tokens.py
```

**Provides**:
- Deep analysis of missing tokens
- Checks enhanced_watchlist_history table
- Shows rejection reasons with specifics
- Cross-references with watchlist_state.json

### 3. Complete Documentation

- **TROUBLESHOOT_MISSING_TOKENS.md** - Step-by-step guide
- **WATCHLIST_SYNC_NOT_FOUND_EXPLAINED.md** - Detailed explanation
- **Updated CLI command** - Shows full addresses

## Your Specific Case

Based on your results:
```
✅ Tokens set to active: 1
❌ Tokens set to inactive: 50
⚠️  Tokens not found in DB: 20
```

**Most likely scenario**:
- 1 active token ← Synced successfully ✅
- 50 inactive tokens ← Synced successfully ✅
- 20 not found ← All probably inactive and filtered correctly ✅

**To confirm**:
```bash
# Run diagnostic to see breakdown
python -m examples.cli_with_scheduler diagnose-watchlist

# Look for this line:
# Active missing (⚠️  CRITICAL): 0  ← Should be 0
# Inactive missing (ℹ️  Normal): 20  ← All 20 are inactive = normal!
```

**Expected result**: All 20 missing tokens are inactive = **System is healthy!**

## Next Steps

1. **Run diagnostic** to get full token addresses:
   ```bash
   python -m examples.cli_with_scheduler diagnose-watchlist
   ```

2. **Check if action needed** (look for "Active missing"):
   - If 0 → You're done! ✅
   - If > 0 → Investigate those specific tokens

3. **Optional deep dive** (if curious):
   ```bash
   python check_rejected_tokens.py
   ```

4. **Review findings** in the output

That's it! The tools will tell you exactly what's happening and whether action is needed.
