#!/usr/bin/env python3
"""
Test token extraction logic.
"""

import sys
sys.path.insert(0, '.')


def extract_token_symbol_from_name(name: str, pool_id: str = '') -> str:
    """
    Extract token symbol from pool name.
    
    Args:
        name: Pool name (e.g., "TOKEN / SOL" or "TOKEN/SOL")
        pool_id: Pool ID for fallback
        
    Returns:
        Token symbol string
    """
    try:
        if not name:
            # Fallback to pool ID prefix if no name
            if pool_id:
                return f"POOL{pool_id.split('_')[-1][:6].upper()}"
            return "UNKNOWN"
        
        # Handle "TOKEN / SOL" or "TOKEN/SOL" format
        if '/' in name:
            token_part = name.split('/')[0].strip()
            # Don't uppercase if it has mixed case (preserve branding)
            return token_part if token_part else "UNKNOWN"
        
        # Handle space-separated format
        if ' ' in name:
            # Use first word
            token_part = name.split()[0].strip()
            return token_part if token_part else "UNKNOWN"
        
        # Single word name
        return name.strip() if name.strip() else "UNKNOWN"
        
    except Exception as e:
        print(f"Error extracting token symbol from name '{name}': {e}")
        return "UNKNOWN"


def test_token_extraction():
    """Test the token extraction methods."""
    
    print("=" * 80)
    print("TOKEN EXTRACTION TEST")
    print("=" * 80)
    
    # Test cases
    test_cases = [
        {
            'name': 'Uber Ai / SOL',
            'pool_id': 'solana_DJPusgin2vGuHHqtqh6tu4GPpyjjxLxFKhWJmdVobEVt',
            'expected_symbol': 'Uber Ai',
        },
        {
            'name': 'TOKEN/SOL',
            'pool_id': 'solana_ABC123',
            'expected_symbol': 'TOKEN',
        },
        {
            'name': 'MyToken / SOL',
            'pool_id': 'solana_XYZ789',
            'expected_symbol': 'MyToken',
        },
        {
            'name': 'PEPE',
            'pool_id': 'solana_PEPE123',
            'expected_symbol': 'PEPE',
        },
        {
            'name': '',
            'pool_id': 'solana_FALLBACK123',
            'expected_symbol': 'POOLFALLBA',  # Fallback to pool ID
        },
    ]
    
    print("\nTest Results:")
    print("-" * 80)
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        name = test_case['name']
        pool_id = test_case['pool_id']
        expected = test_case['expected_symbol']
        
        result = extract_token_symbol_from_name(name, pool_id)
        
        passed = result == expected
        status = "✓ PASS" if passed else "✗ FAIL"
        
        print(f"\nTest {i}: {status}")
        print(f"  Name: '{name}'")
        print(f"  Pool ID: {pool_id}")
        print(f"  Expected: '{expected}'")
        print(f"  Got: '{result}'")
        
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = test_token_extraction()
    sys.exit(0 if success else 1)
