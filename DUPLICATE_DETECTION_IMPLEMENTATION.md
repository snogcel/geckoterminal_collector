# Duplicate Detection Implementation for new_pools_history

## Problem Statement

The GeckoTerminal API updates pool data approximately once per minute. However, the system was configured to check for new pools every 15 seconds to quickly catch new pools. This resulted in duplicate entries in the `new_pools_history` table where the same data was stored multiple times with different `collected_at` timestamps.

### Example of Duplicated Data

Multiple rows with identical values for:
- `reserve_in_usd`
- `transactions_h1_buys`
- `transactions_h1_sells`
- `transactions_h24_buys`
- `transactions_h24_sells`
- `volume_usd_h24`

This duplication interfered with signal score calculations and wasted database storage.

## Solution

Modified the `store_new_pools_history` method in `gecko_terminal_collector/database/sqlalchemy_manager.py` to check for duplicate data before inserting new records.

### Implementation Details

The duplicate detection logic:

1. **Time Window Check**: Looks back 2 minutes for recent records of the same pool
2. **Field Comparison**: Compares the following key fields that should change when API data updates:
   - `reserve_in_usd`
   - `transactions_h1_buys`
   - `transactions_h1_sells`
   - `transactions_h24_buys`
   - `transactions_h24_sells`
   - `volume_usd_h24`
3. **Skip Duplicates**: If all fields match, the new record is skipped with a debug log message
4. **Store Changes**: If any field differs, the record is stored normally

### Benefits

- **Preserves 15-second collection frequency**: Continues to catch new pools quickly
- **Eliminates duplicate data**: Only stores records when API data actually changes
- **Improves signal accuracy**: Signal scores are calculated on actual data changes, not duplicate entries
- **Reduces storage**: Significantly reduces database size by eliminating redundant records
- **Maintains data integrity**: Still respects the unique constraint on `pool_id` + `collected_at`

## Testing

A comprehensive test script (`test_duplicate_detection.py`) was created to verify the implementation:

### Test Results

```
================================================================================
DUPLICATE DETECTION TEST
================================================================================

1. Creating first history record for pool: solana_TEST_DUPLICATE_DETECTION_POOL
   ✓ First record stored successfully

2. Attempting to store duplicate record (same data, different timestamp)
   ✓ Duplicate record was correctly skipped

3. Attempting to store record with changed data
   ✓ Record with changed data stored successfully

4. Verifying records in database
   Total records found: 2
   Expected: 2 (first record + changed data record)
   ✓ Correct number of records stored

5. Cleaning up test data
   ✓ Test data cleaned up

================================================================================
TEST PASSED: Duplicate detection working correctly!
================================================================================
```

## Code Changes

### Modified File: `gecko_terminal_collector/database/sqlalchemy_manager.py`

**Method**: `store_new_pools_history`

**Key Changes**:
- Added query to check for recent records (within 2 minutes)
- Added field comparison logic for the 6 key data fields
- Added early return when duplicate is detected
- Added debug logging for skipped duplicates

## Usage

No changes required to existing code. The duplicate detection is automatic and transparent:

```python
# Existing code continues to work as before
history_record = NewPoolsHistory(
    pool_id=pool_id,
    reserve_in_usd=reserve_usd,
    transactions_h1_buys=buys_h1,
    # ... other fields
)

# Duplicate detection happens automatically
await db_manager.store_new_pools_history(history_record)
```

## Performance Considerations

- **Minimal overhead**: Single query to check for recent records
- **Indexed query**: Uses existing index on `pool_id` and `collected_at`
- **Short time window**: Only checks last 2 minutes of data
- **Early exit**: Returns immediately when duplicate is detected

## Monitoring

The implementation includes debug logging to track duplicate detection:

```
DEBUG: Skipping duplicate new pools history record for pool {pool_id} - data unchanged since {timestamp}
```

Monitor these logs to understand how frequently duplicates are being prevented.

## Future Enhancements

Potential improvements for consideration:

1. **Configurable time window**: Make the 2-minute window configurable
2. **Configurable fields**: Allow configuration of which fields to check for duplicates
3. **Metrics tracking**: Add counters for duplicates prevented vs records stored
4. **Partial field changes**: Option to update only changed fields instead of full record

## Backward Compatibility

This change is fully backward compatible:
- No database schema changes required
- No API changes
- Existing code continues to work without modification
- Can be disabled by removing the duplicate check if needed
