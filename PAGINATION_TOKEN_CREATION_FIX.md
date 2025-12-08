# Token Creation Fix for Pagination

## Issue

Foreign key violation when creating pools:

```
ForeignKeyViolation: insert or update on table "pools" violates foreign key constraint "pools_quote_token_id_fkey"
DETAIL: Key (quote_token_id)=(solana_So11111111111111111111111111111111111111112) is not present in table "tokens"
```

## Root Cause

The `_ensure_token_exists()` method was silently failing:

```python
except Exception as e:
    self.logger.error(f"Error ensuring token exists for {token_id}: {e}")
    # Don't raise for tokens - they're optional
    pass  # ❌ Silent failure!
```

This meant:
1. Token creation attempted
2. Token creation failed (for some reason)
3. Error was logged but swallowed
4. Pool creation attempted anyway
5. Foreign key violation occurred

## Solution

### 1. Raise Token Creation Errors

```python
except Exception as e:
    self.logger.error(f"Error ensuring token exists for {token_id}: {e}")
    # Raise the error so pool creation knows tokens failed
    raise  # ✅ Propagate the error
```

### 2. Add Debug Logging

```python
if base_token_id:
    self.logger.debug(f"Ensuring base token exists: {base_token_id}")
    await self._ensure_token_exists(base_token_id)
if quote_token_id:
    self.logger.debug(f"Ensuring quote token exists: {quote_token_id}")
    await self._ensure_token_exists(quote_token_id)
```

## Next Steps

With this fix, we'll now see the actual error that's preventing token creation. Possible causes:

1. **Database manager method missing**: `store_token()` doesn't exist
2. **Database connection issue**: Session not working properly
3. **Token model issue**: TokenModel fields don't match database schema
4. **Duplicate key**: Token already exists but query failed

The error will now be visible in logs, allowing us to fix the underlying issue.

## Expected Behavior

After fix:
1. Token creation attempted
2. If it fails, error is raised with details
3. Pool creation is skipped (no foreign key violation)
4. Error is logged with full context
5. We can fix the actual root cause

## Testing

Monitor logs for:
```
DEBUG - Ensuring base token exists: solana_xxx
DEBUG - Ensuring quote token exists: solana_yyy
ERROR - Error ensuring token exists for solana_xxx: [actual error]
ERROR - Error ensuring pool exists for solana_pool: [propagated error]
```

This will reveal the true cause of token creation failures.
