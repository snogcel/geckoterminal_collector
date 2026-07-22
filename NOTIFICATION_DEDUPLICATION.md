# Notification Deduplication System

## Overview
Prevents duplicate Telegram notifications for the same token within 24 hours using a database-backed tracking system.

## Implementation

### Database Table: `notification_log`

Tracks all sent notifications with timestamps:

```sql
CREATE TABLE notification_log (
    id INTEGER PRIMARY KEY,
    token_address VARCHAR(255) NOT NULL,
    token_symbol VARCHAR(50) NOT NULL,
    pool_address VARCHAR(255) NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'watchlist_entry',
    sent_at TIMESTAMP NOT NULL,
    entry_data TEXT,  -- JSON of the entry
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    INDEX idx_notification_token_time (token_address, sent_at)
);
```

### Three-Layer Filtering

```
┌─────────────────────────────────────────┐
│ 1. Check History Count                  │
│    → Must have 3 occurrences in 24h     │
└─────────────┬───────────────────────────┘
              │ ✅ Pass
              ▼
┌─────────────────────────────────────────┐
│ 2. Check Quality Criteria               │
│    → priceChange5m >= 0                 │
│    → priceChange1h >= 0                 │
│    → score >= 30                        │
│    → smart_degen_count >= 0             │
│    → liquidity >= 5000                  │
│    → dex in ['pump_amm', 'pump']        │
└─────────────┬───────────────────────────┘
              │ ✅ Pass
              ▼
┌─────────────────────────────────────────┐
│ 3. Check Notification Log               │
│    → No notification in last 24h?       │
└─────────────┬───────────────────────────┘
              │ ✅ Pass
              ▼
        Send Notification!
```

## API Methods

### `check_notification_sent_recently(token_address, hours=24)`

Checks if a notification was already sent for this token:

```python
already_notified = await db_manager.check_notification_sent_recently(
    token_address="ABC123...",
    hours=24
)
# Returns: True if notified within last 24h, False otherwise
```

### `log_notification(token_address, token_symbol, pool_address, entry_data, success, error_message)`

Logs a sent notification:

```python
await db_manager.log_notification(
    token_address="ABC123...",
    token_symbol="TOKEN",
    pool_address="pool123...",
    entry_data={...},  # Full entry dict
    success=True,
    error_message=None
)
```

## Flow Example

### First Time (1st occurrence)
```
Token appears → Store history → Count = 1 → No notification
```

### Second Time (2nd occurrence)
```
Token appears → Store history → Count = 2 → No notification
```

### Third Time (3rd occurrence)
```
Token appears → Store history → Count = 3
    ↓
Check quality criteria → ✅ Pass
    ↓
Check notification log → No recent notification
    ↓
Send Telegram notification
    ↓
Log to notification_log table
```

### Fourth Time (later same day)
```
Token appears → Store history → Count = 4
    ↓
Check quality criteria → ✅ Pass
    ↓
Check notification log → ⚠️  Already notified today
    ↓
Skip notification (prevented duplicate!)
```

### Next Day (after 24h)
```
Token appears → Store history → Count = 1 (new 24h window)
    ↓
Check notification log → Last notification was 25h ago
    ↓
Cycle repeats (will notify again on 3rd occurrence)
```

## Benefits

1. **No Spam**: Token can't trigger multiple notifications in same day
2. **Database-Backed**: Reliable, survives restarts
3. **Indexed**: Fast lookups with composite index
4. **Auditable**: Full history of all notifications
5. **Failure Tracking**: Logs both successes and failures
6. **Flexible**: Easy to adjust time window (default 24h)

## Configuration

### Change Deduplication Window

Default is 24 hours. To change:

```python
# Check last 12 hours instead
already_notified = await db_manager.check_notification_sent_recently(
    token_address, 
    hours=12  # ← Change here
)
```

### Query Notification History

```sql
-- See all notifications for a token
SELECT * FROM notification_log 
WHERE token_address = 'ABC123...'
ORDER BY sent_at DESC;

-- See failed notifications
SELECT * FROM notification_log 
WHERE success = FALSE
ORDER BY sent_at DESC;

-- Count notifications per token
SELECT token_symbol, COUNT(*) as notification_count
FROM notification_log
GROUP BY token_symbol
ORDER BY notification_count DESC;
```

## Cleanup

Old records can be cleaned up periodically:

```sql
-- Delete notifications older than 30 days
DELETE FROM notification_log 
WHERE sent_at < NOW() - INTERVAL '30 days';
```

Or add a scheduled job to do this automatically.

## Advantages Over JSON File

| Aspect | Database Table | JSON File |
|--------|---------------|-----------|
| Concurrency | ✅ Safe with locks | ❌ Race conditions |
| Reliability | ✅ ACID guarantees | ❌ Can corrupt |
| Speed | ✅ Indexed queries | ❌ Full file read |
| Scalability | ✅ Handles millions | ❌ Gets slow |
| Queryable | ✅ SQL queries | ❌ Must parse |
| Atomicity | ✅ Transaction safe | ❌ Write conflicts |

## Alternative: JSON File Approach

If you really want a JSON file (not recommended):

```python
import json
from pathlib import Path
from datetime import datetime, timedelta

class NotificationTracker:
    def __init__(self, file_path=".notification_log.json"):
        self.file_path = Path(file_path)
    
    def was_notified_recently(self, token_address, hours=24):
        if not self.file_path.exists():
            return False
        
        with open(self.file_path, 'r') as f:
            log = json.load(f)
        
        if token_address not in log:
            return False
        
        last_sent = datetime.fromisoformat(log[token_address])
        return datetime.now() - last_sent < timedelta(hours=hours)
    
    def log_notification(self, token_address):
        log = {}
        if self.file_path.exists():
            with open(self.file_path, 'r') as f:
                log = json.load(f)
        
        log[token_address] = datetime.now().isoformat()
        
        with open(self.file_path, 'w') as f:
            json.dump(log, f, indent=2)
```

**But database is better** for production use!
