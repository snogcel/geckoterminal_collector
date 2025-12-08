# Token ID Format Fix

## Issue

Foreign key violation when creating pools because token IDs had incorrect format:

```
ForeignKeyViolation: Key (quote_token_id)=(solana_So11111111111111111111111111111111111111112) 
is not present in table "tokens"
```

## Root Cause

**Mismatch between API format and database schema:**

### API Returns (with network prefix):
```
base_token_id: "solana_7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk"
quote_token_id: "solana_So11111111111111111111111111111111111111112"
```

### Database Expects (without network prefix):
```sql
-- tokens table
id: "7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk"  -- Just the address
network: "solana"  -- Network stored separately

-- pools table references tokens.id
base_token_id: "7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk"  -- Must match tokens.id
quote_token_id: "So11111111111111111111111111111111111111112"
```

### What Was Happening:
1. API returns: `solana_So11111111111111111111111111111111111111112`
2. Code stored in pool: `solana_So11111111111111111111111111111111111111112` ❌
3. Token created with ID: `solana_So11111111111111111111111111111111111111112` ❌
4. Foreign key lookup failed (no match)

## Solution

Strip network prefix from token IDs before database storage:

### 1. Updated `_extract_pool_info()`

```python
# Strip network prefix from token IDs for database storage
# Token IDs come as "solana_ADDRESS" but database expects just "ADDRESS"
if base_token_id and '_' in base_token_id:
    base_token_id = base_token_id.split('_', 1)[1]
if quote_token_id and '_' in quote_token_id:
    quote_token_id = quote_token_id.split('_', 1)[1]
```

### 2. Updated Helper Methods

```python
def _extract_base_token_id(self, pool_data: Dict) -> Optional[str]:
    """Returns address without network prefix for database storage."""
    # ... extraction logic ...
    
    # Strip network prefix (e.g., "solana_ADDRESS" -> "ADDRESS")
    if token_id and '_' in token_id:
        token_id = token_id.split('_', 1)[1]
    
    return token_id if token_id else None
```

### 3. Updated `_ensure_token_exists()`

```python
async def _ensure_token_exists(self, token_address: str) -> None:
    """
    Ensure token exists in the database, create if it doesn't.
    
    Args:
        token_address: Token address (without network prefix)
    """
    # Token ID in database is just the address (no network prefix)
    # Network is stored separately
    address = token_address
    network = self.network
    
    token_data = {
        'id': address,  # Just the address, no network prefix
        'address': address,
        'network': network,
        # ...
    }
```

## Correct Format

| Field | API Format | Database Format | Notes |
|-------|-----------|-----------------|-------|
| **Pool ID** | `solana_8k4F...` | `solana_8k4F...` | ✅ Keep prefix |
| **DEX ID** | `meteora-damm-v2` | `meteora-damm-v2` | ✅ No prefix |
| **Base Token** | `solana_7Ue6...` | `7Ue6...` | ⚠️ Strip prefix |
| **Quote Token** | `solana_So11...` | `So11...` | ⚠️ Strip prefix |

## Testing

```bash
python test_dex_extraction.py
```

Output:
```
Pool ID: solana_8k4FgJzpBkd8hiL5Kohx1Dr8m1HzS3z2vQA5huitRjxY
DEX ID: meteora-damm-v2
Base Token Address: 7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk
Quote Token Address: So11111111111111111111111111111111111111112
✅ All IDs extracted successfully!
```

## Result

✅ **Fixed** - Token IDs now stored without network prefix  
✅ **Foreign keys work** - Pools can reference tokens correctly  
✅ **Consistent with schema** - Matches existing database design  
✅ **Tested** - Verified with extraction test

The pagination implementation now correctly handles token ID formats for database storage.
