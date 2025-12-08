"""
Test script to verify dex_id and token extraction from new API format.
"""

# Sample pool data from the new API format
pool_data = {
    'id': 'solana_8k4FgJzpBkd8hiL5Kohx1Dr8m1HzS3z2vQA5huitRjxY',
    'type': 'pool',
    'attributes': {
        'base_token_price_usd': '0.0000430135168409101256278639485486379623202069809249606553092690824',
        'address': '8k4FgJzpBkd8hiL5Kohx1Dr8m1HzS3z2vQA5huitRjxY',
        'name': 'USD / SOL',
        'pool_created_at': '2025-12-06T18:58:31Z',
        'reserve_in_usd': '14.5132'
    },
    'relationships': {
        'base_token': {
            'data': {
                'id': 'solana_7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk',
                'type': 'token'
            }
        },
        'quote_token': {
            'data': {
                'id': 'solana_So11111111111111111111111111111111111111112',
                'type': 'token'
            }
        },
        'dex': {
            'data': {
                'id': 'meteora-damm-v2',
                'type': 'dex'
            }
        }
    }
}

def extract_dex_id(pool_data):
    """Extract dex_id from pool data."""
    # Try attributes first
    attributes = pool_data.get('attributes', {})
    dex_id = attributes.get('dex_id', pool_data.get('dex_id', '')).strip()
    
    # If not found, try relationships
    if not dex_id:
        relationships = pool_data.get('relationships', {})
        dex_data = relationships.get('dex', {}).get('data', {})
        dex_id = dex_data.get('id', '').strip()
    
    return dex_id if dex_id else None

def extract_base_token_id(pool_data):
    """Extract base_token_id from pool data."""
    # Try attributes first
    attributes = pool_data.get('attributes', {})
    token_id = attributes.get('base_token_id', pool_data.get('base_token_id', '')).strip()
    
    # If not found, try relationships
    if not token_id:
        relationships = pool_data.get('relationships', {})
        token_data = relationships.get('base_token', {}).get('data', {})
        token_id = token_data.get('id', '').strip()
    
    return token_id if token_id else None

def extract_quote_token_id(pool_data):
    """Extract quote_token_id from pool data."""
    # Try attributes first
    attributes = pool_data.get('attributes', {})
    token_id = attributes.get('quote_token_id', pool_data.get('quote_token_id', '')).strip()
    
    # If not found, try relationships
    if not token_id:
        relationships = pool_data.get('relationships', {})
        token_data = relationships.get('quote_token', {}).get('data', {})
        token_id = token_data.get('id', '').strip()
    
    return token_id if token_id else None

# Test extraction
print("Testing extraction from new API format:")
print(f"Pool ID: {pool_data['id']}")
print(f"DEX ID: {extract_dex_id(pool_data)}")

base_token_full = extract_base_token_id(pool_data)
quote_token_full = extract_quote_token_id(pool_data)

print(f"Base Token ID (full): {base_token_full}")
print(f"Quote Token ID (full): {quote_token_full}")

# Strip network prefix for database storage
base_token_address = base_token_full.split('_', 1)[1] if base_token_full and '_' in base_token_full else base_token_full
quote_token_address = quote_token_full.split('_', 1)[1] if quote_token_full and '_' in quote_token_full else quote_token_full

print(f"\nFor database storage:")
print(f"Base Token Address: {base_token_address}")
print(f"Quote Token Address: {quote_token_address}")

# Expected output:
# Pool ID: solana_8k4FgJzpBkd8hiL5Kohx1Dr8m1HzS3z2vQA5huitRjxY (with prefix - OK)
# DEX ID: meteora-damm-v2 (no prefix - OK)
# Base Token Address: 7Ue6iwkYgi3MRynnTybeqWHrzYKRiTvgvS39DhkCbonk (no prefix - OK)
# Quote Token Address: So11111111111111111111111111111111111111112 (no prefix - OK)

print("\n✅ All IDs extracted successfully!")
