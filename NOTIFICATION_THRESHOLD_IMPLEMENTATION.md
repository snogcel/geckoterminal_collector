# 3rd Occurrence Notification Threshold Implementation

## Overview
Telegram notifications are now only triggered when a token appears for the **3rd time** in the `enhanced_watchlist_history` table within 24 hours.

## Implementation Details

### Flow Sequence
```
1. Store pool data
2. Store token data  
3. Store history entry (count increments)
4. Check watchlist entry → count == 3? → Send notification!
```

### Database Query
```sql
SELECT COUNT(*) 
FROM enhanced_watchlist_history 
WHERE base_token_address = ?
  AND collected_at >= NOW() - INTERVAL '24 hours'
```

### Notification Logic

| Occurrences | Action | Notification |
|-------------|--------|--------------|
| 1st time    | Store in history | ❌ No notification |
| 2nd time    | Store in history | ❌ No notification |
| **3rd time** | Store in history | ✅ **SEND NOTIFICATION** |
| 4th+ times  | Store in history | ❌ No notification |

## Key Changes

### 1. Updated `store_watchlist_entry()` Method
**Location:** `gecko_terminal_collector/database/sqlalchemy_manager.py`

- Now queries `enhanced_watchlist_history` table
- Counts occurrences in last 24 hours
- Returns `True` only when count equals exactly 3
- Added INFO-level logging with emojis for visibility

### 2. Reordered Storage Sequence
**Location:** `gecko_terminal_collector/collectors/enhanced_watchlist_collector.py`

Changed order to store history **before** checking watchlist:
```python
# OLD (incorrect):
await self._store_enhanced_watchlist_entry(entry)    # Checks count first
await self._store_enhanced_watchlist_history_entry(entry)  # Then increments

# NEW (correct):
await self._store_enhanced_watchlist_history_entry(entry)  # Increment first
await self._store_enhanced_watchlist_entry(entry)    # Then check count
```

### 3. Added Model to PostgreSQL
**Location:** `gecko_terminal_collector/database/postgresql_models.py`

Added `EnhancedWatchlistHistory` model with optimized indexes:
```python
Index('idx_enhanced_watchlist_token_time', 'base_token_address', 'collected_at')
```

### 4. Fixed Rate Limiter
**Location:** `gecko_terminal_collector/utils/enhanced_rate_limiter.py`

- Circuit breaker now requires 3+ consecutive 429s before opening
- More reasonable backoff timeouts (60s max for 429s)
- Failure count resets after 5 minutes

## Log Output

You'll now see these logs when processing entries:

```
🔍 Token SYMBOL (12345678...) has appeared 1 times in last 24h - ⏳ waiting for 3rd occurrence
🔍 Token SYMBOL (12345678...) has appeared 2 times in last 24h - ⏳ waiting for 3rd occurrence
🔍 Token SYMBOL (12345678...) has appeared 3 times in last 24h - 🔔 TRIGGERING NOTIFICATION (3rd occurrence)
```

## Benefits

1. **Reduces Noise**: No notifications for one-off appearances
2. **Confirms Consistency**: Token must appear 3 times in 24h
3. **Avoids Spam**: 4th+ occurrences don't trigger additional notifications
4. **Tunable Threshold**: Easy to change from 3 to any other number

## Testing

To test the implementation:

```python
# Simulate 3 occurrences within 24 hours
# 1st occurrence - no notification
# 2nd occurrence - no notification  
# 3rd occurrence - notification sent!
# 4th occurrence - no notification
```

## Configuration

No configuration required - the threshold is hardcoded as `3` in the logic:

```python
return history_count == 3
```

To change the threshold, modify this line in `store_watchlist_entry()`.

## Dependencies

- `enhanced_watchlist_history` table must exist
- `base_token_address` must be populated in history records
- `network_address` must be set in watchlist entries
