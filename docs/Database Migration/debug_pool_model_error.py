#!/usr/bin/env python3
"""
Debug the PoolModel import issue.
"""

import traceback

try:
    from gecko_terminal_collector.database.models import Pool as PoolModel, NewPoolsHistory
    print("✓ Import successful")
    print(f"PoolModel: {PoolModel}")
    print(f"NewPoolsHistory: {NewPoolsHistory}")
    
    # Try to create an instance
    pool_info = {
        'id': 'test_pool',
        'address': 'test_address',
        'name': 'Test Pool',
        'dex_id': 'test_dex',
        'base_token_id': 'test_base',
        'quote_token_id': 'test_quote',
        'reserve_usd': 1000.0
    }
    
    pool = PoolModel(**pool_info)
    print(f"✓ PoolModel instance created: {pool}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("Full traceback:")
    traceback.print_exc()