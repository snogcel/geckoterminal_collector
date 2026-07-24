# Troubleshooting Missing Tokens - Complete Guide

## Quick Diagnosis

```bash
# Step 1: See which tokens are missing
python -m examples.cli_with_scheduler diagnose-watchlist

# Step 2: Investigate WHY they're missing
python check_rejected_tokens.py
```

## Understanding the Output

### Token Status Flow

```
Token appears → Monitored → Enhanced Watchlist History → Evaluated → Watchlist Table
                                      ↓                        ↓
                               (collected data)         (passed criteria)
```

**Missing tokens** can be at different stages:
1. **Never collected** - Not in enhanced_watchlist_history
2. **Collected but rejected** - In enhanced_watchlist_history but not in watchlist
3. **Added then removed** - Was in watchlist, now deleted

## Investigation Tools

### Tool 1: diagnose-watchlist (CLI Command)

**Purpose**: Shows which tokens are missing and provides full addresses

```bash
python -m examples.cli_with_scheduler diagnose-watchlist
```

**Output includes**:
- Full token addresses (for copying)
- Active vs inactive breakdown
- Deactivation reasons
- How to investigate further

**When to use**: First step to identify missing tokens

### Tool 2: check_rejected_tokens.py

**Purpose**: Deep dive into WHY tokens are missing

```bash
# Check all missing tokens
python check_rejected_tokens.py

# Check specific token
python check_rejected_tokens.py watchlist_state.json config.yaml TOKEN_ADDRESS
```

**What it checks**:
1. Are tokens in `enhanced_watchlist_history` table?
2. If yes → Why weren't they added to watchlist?
3. If no → Why were they never collected?

**Output analysis**:
- Tokens collected but filtered → Check rejection logic
- Tokens never collected → Check source configuration

## Common Scenarios

### Scenario 1: Token in History, Not in Watchlist ✅

```
Token: ABC123...
Status: Found in enhanced_watchlist_history
Times collected: 3
Liquidity: $2,500
⚠️  LIKELY REASON: Liquidity too low ($2,500 < $5,000)
```

**What this means**:
- Token WAS collected successfully
- Filtered out due to low liquidity (or other criteria)
- System is working correctly

**Action**: If you want this token included, adjust filter criteria

### Scenario 2: Token Never Collected ⚠️

```
Token: XYZ789...
Status: NOT in enhanced_watchlist_history
```

**What this means**:
- Token was never collected by enhanced_watchlist_collector
- Might be from a different source
- Timing issue (appeared between cycles)

**Action**: Check source configuration and collection schedule

### Scenario 3: Active Token Missing 🔴

```
Token: DEF456...
Status: ACTIVE but not in database
Peak score: 85
Liquidity: $50,000
```

**What this means**:
- High-quality token that should be in database
- Potential issue with collector logic

**Action Required**: Investigate immediately

## Investigation Steps

### Step 1: Get Full Token Addresses

```bash
python -m examples.cli_with_scheduler diagnose-watchlist > missing_tokens.txt
```

This saves all token addresses to a file for easy copying.

### Step 2: Check Collection History

```bash
# Run deep investigation
python check_rejected_tokens.py
```

Look for:
- "Found in enhanced_watchlist_history" → Filtering issue
- "NOT in enhanced_watchlist_history" → Collection issue

### Step 3: Check Specific Token

Pick a token address from the diagnostic output:

```bash
python check_rejected_tokens.py watchlist_state.json config.yaml "YOUR_TOKEN_ADDRESS_HERE"
```

### Step 4: Check Database Directly

```sql
-- Check if token in history
SELECT * FROM enhanced_watchlist_history 
WHERE base_token_address = 'TOKEN_ADDRESS'
ORDER BY collected_at DESC;

-- Check if token in watchlist
SELECT * FROM watchlist 
WHERE network_address = 'TOKEN_ADDRESS';

-- Check collection frequency
SELECT 
    DATE(collected_at) as date,
    COUNT(*) as collections
FROM enhanced_watchlist_history
WHERE base_token_address = 'TOKEN_ADDRESS'
GROUP BY DATE(collected_at);
```

### Step 5: Check Collector Logs

```bash
# Search for token in logs
grep "TOKEN_ADDRESS" /var/log/collector.log

# Look for rejections
grep -i "reject\|filter\|skip" /var/log/collector.log | grep "TOKEN_ADDRESS"

# Check recent enhanced watchlist runs
grep "enhanced_watchlist" /var/log/collector.log | tail -50
```

## Common Rejection Reasons

### 1. Liquidity Too Low

**Log message**: `"Skipping token, liquidity too low: $2,500 < $5,000"`

**Check in code**:
```python
# In enhanced_watchlist_collector.py
MIN_LIQUIDITY = 5000  # Check this threshold
```

**Solution**: Adjust `MIN_LIQUIDITY` or accept that low-liquidity tokens are filtered

### 2. Score Too Low

**Log message**: `"Token score too low: 25 < 30"`

**Check in code**:
```python
# In enhanced_watchlist_collector.py
MIN_SCORE = 30  # Check this threshold
```

**Solution**: Adjust scoring threshold or improve score calculation

### 3. Address Resolution Failed

**Log message**: `"Failed to resolve token address for pool_address"`

**Causes**:
- Database address resolver couldn't find token
- API didn't return token address
- Token not in pools or tokens table

**Solution**: Check `database_address_resolver.py` logs

### 4. Duplicate Entry

**Log message**: `"Token already in watchlist, skipping"`

**Check**:
```sql
SELECT * FROM watchlist WHERE network_address = 'TOKEN_ADDRESS';
```

**Solution**: If duplicate check is wrong, review duplicate detection logic

### 5. Filtered DEX

**Log message**: `"Skipping token from filtered DEX: raydium"`

**Check in config**:
```yaml
enhanced_watchlist:
  excluded_dexes: [raydium, orca]  # Check this list
```

**Solution**: Remove DEX from exclusion list if needed

## Checking Enhanced Watchlist Collector Logic

### File to Review
`gecko_terminal_collector/collectors/enhanced_watchlist_collector.py`

### Key Methods to Check

1. **`_process_entry()`** - Main entry processing
   - Where tokens get added to watchlist
   - Check rejection conditions

2. **`_calculate_score()`** - Score calculation
   - How scores are computed
   - Threshold checks

3. **`_resolve_token_address()`** - Address resolution
   - How token addresses are resolved
   - Failure handling

4. **`_should_add_to_watchlist()`** - Entry criteria
   - All conditions that must be met
   - Filtering logic

### Example Investigation

```python
# Look for this pattern in enhanced_watchlist_collector.py

async def _process_entry(self, entry):
    # ... code ...
    
    # CHECK THIS: Minimum score
    if score < self.MIN_SCORE:
        logger.info(f"Score too low: {score} < {self.MIN_SCORE}")
        return False
    
    # CHECK THIS: Liquidity threshold
    if liquidity < self.MIN_LIQUIDITY:
        logger.info(f"Liquidity too low: ${liquidity} < ${self.MIN_LIQUIDITY}")
        return False
    
    # CHECK THIS: Duplicate detection
    if self._is_duplicate(token_address):
        logger.info(f"Duplicate entry: {token_address}")
        return False
```

## Quick Fixes

### If Criteria Too Strict

Edit `enhanced_watchlist_collector.py`:

```python
# Lower minimum score
MIN_SCORE = 20  # Was 30

# Lower minimum liquidity
MIN_LIQUIDITY = 2000  # Was 5000
```

Then re-run collector:
```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist
```

### If Source Missing

Edit `config.yaml`:

```yaml
enhanced_watchlist:
  enabled: true
  sources: [reference, micro, lowcap, midcap]  # Add missing sources
  interval: "1h"
```

### If Timing Issue

Check collection frequency:
```yaml
enhanced_watchlist:
  interval: "30m"  # Collect more frequently
```

## Verification After Changes

```bash
# 1. Re-run collector
python -m examples.cli_with_scheduler collect-enhanced-watchlist

# 2. Check if tokens now in database
python -m examples.cli_with_scheduler diagnose-watchlist

# 3. Sync status
python -m examples.cli_with_scheduler sync-watchlist-status

# 4. Verify results
python check_rejected_tokens.py
```

## When Everything Looks Normal

If investigation shows:
- ✅ Missing tokens are all inactive
- ✅ Active tokens all in database
- ✅ Rejection reasons are valid (low score, low liquidity)

**This is EXPECTED behavior!** The system is working correctly.

## When Action Is Needed

If investigation shows:
- 🔴 Active high-score tokens missing
- 🔴 Good tokens never collected
- 🔴 All tokens being rejected

**Investigate collector configuration and logic.**

## Export Missing Tokens for Analysis

```bash
# Save diagnostic output
python -m examples.cli_with_scheduler diagnose-watchlist > missing_analysis.txt

# Save rejection analysis
python check_rejected_tokens.py > rejection_analysis.txt

# Review both files
cat missing_analysis.txt
cat rejection_analysis.txt
```

## Summary Checklist

- [ ] Run `diagnose-watchlist` to see which tokens are missing
- [ ] Get full token addresses from diagnostic output
- [ ] Run `check_rejected_tokens.py` for deep analysis
- [ ] Check if tokens in `enhanced_watchlist_history`
- [ ] Review rejection reasons (liquidity, score, etc.)
- [ ] Check collector logs for specific tokens
- [ ] Verify source configuration in `config.yaml`
- [ ] Review collector logic in `enhanced_watchlist_collector.py`
- [ ] If needed, adjust criteria and re-run collector
- [ ] Verify fixes with `diagnose-watchlist` again

## Key Insight

**Most missing tokens are EXPECTED!**

The watchlist system is designed to:
1. Monitor MANY tokens (watchlist_state.json)
2. Filter to BEST tokens (database watchlist table)
3. Only notify on QUALIFIED tokens

Missing tokens = Filtering is working correctly! ✅

Only investigate if:
- Active tokens are missing
- High-quality tokens (score > 70) not in database
- Pattern of incorrectly rejected tokens
