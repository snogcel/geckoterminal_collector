# Pagination API Format Fix

## Issue

When switching from SDK to direct API calls for pagination support, the data format changed:

**Old Format (SDK)**:
```python
{
    'id': 'solana_xxx',
    'attributes': {
        'dex_id': 'meteora-damm-v2',
        'base_token_id': 'solana_xxx',
        'quote_token_id': 'solana_yyy'
    }
}
```

**New Format (Direct API)**:
```python
{
    'id': 'solana_xxx',
    'attributes': {
        # dex_id, base_token_id, quote_token_id NOT here
    },
    'relationships': {
        'dex': {'data': {'id': 'meteora-damm-v2'}},
        'base_token': {'data': {'id': 'solana_xxx'}},
        'quote_token': {'data': {'id': 'solana_yyy'}}
    }
}
```

## Error

```
WARNING - Pool solana_xxx has empty dex_id, skipping
WARNING - Failed to extract pool info from: {...}
```

## Solution

Updated extraction methods to check both locations:

### 1. Added Helper Methods

```python
def _extract_dex_id(self, pool_data: Dict) -> Optional[str]:
    """Extract dex_id from pool data (handles both formats)."""
    # Try attributes first (old format)
    attributes = pool_data.get('attributes', {})
    dex_id = attributes.get('dex_id', '').strip()
    
    # If not found, try relationships (new API format)
    if not dex_id:
        relationships = pool_data.get('relationships', {})
        dex_data = relationships.get('dex', {}).get('data', {})
        dex_id = dex_data.get('id', '').strip()
    
    return dex_id if dex_id else None
```

Similar methods for `_extract_base_token_id()` and `_extract_quote_token_id()`.

### 2. Updated _extract_pool_info()

```python
# Extract DEX ID from relationships if not in attributes
dex_id = get_field('dex_id', '').strip()
if not dex_id:
    relationships = pool_data.get('relationships', {})
    dex_data = relationships.get('dex', {}).get('data', {})
    dex_id = dex_data.get('id', '').strip()
```

### 3. Updated _create_history_record()

```python
'dex_id': self._extract_dex_id(pool_data),
'base_token_id': self._extract_base_token_id(pool_data),
'quote_token_id': self._extract_quote_token_id(pool_data),
```

## Testing

Created `test_dex_extraction.py` to verify extraction works:

```
Testing extraction from new API format:
Pool ID: solana_8k4FgJzpBkd8hiL5Kohx1Dr8m1HzS3z2vQA5huitRjxY
DEX ID: meteora-damm-v2
Base Token ID: solana_7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk
Quote Token ID: solana_So11111111111111111111111111111111111111112

✅ All IDs extracted successfully!
```

## Result

✅ **Fixed** - Collector now handles both old and new API formats
✅ **Backward Compatible** - Still works with SDK format if needed
✅ **Tested** - Extraction verified with real API data

The pagination implementation now correctly extracts all required IDs from the new API response format.
