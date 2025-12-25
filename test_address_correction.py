#!/usr/bin/env python3
"""
Test script to verify base58 address correction is working properly.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.utils.address_parser import SolanaAddressParser


def test_base58_correction():
    """Test the base58 address correction functionality."""
    
    print("🧪 Testing Base58 Address Correction")
    print("=" * 50)
    
    # Test cases with known lowercase addresses and their expected corrections
    test_cases = [
        {
            'lowercase': 'ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9',
            'description': 'SANTA token pool address from CSV'
        },
        {
            'lowercase': '26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o',
            'description': 'DINO token pool address from CSV'
        },
        {
            'lowercase': '3ismqtviyuhggvmbxoui7h5fwq5ktjwaeonvcnq1uqds',
            'description': 'CALVIN token pool address from CSV'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        lowercase = test_case['lowercase']
        description = test_case['description']
        
        print(f"\nTest {i}: {description}")
        print(f"Input (lowercase): {lowercase}")
        
        # Test the correction
        corrected = SolanaAddressParser.correct_case_sensitivity(lowercase)
        
        print(f"Output (corrected): {corrected}")
        
        # Validate both addresses
        lowercase_valid = SolanaAddressParser.is_valid_solana_address(lowercase)
        corrected_valid = SolanaAddressParser.is_valid_solana_address(corrected) if corrected else False
        
        print(f"Lowercase valid: {lowercase_valid}")
        print(f"Corrected valid: {corrected_valid}")
        
        # Check if correction changed the case
        if corrected and corrected != lowercase:
            print(f"✅ Case correction applied: {lowercase} → {corrected}")
        elif corrected == lowercase:
            print(f"ℹ️  No case correction needed (already valid)")
        else:
            print(f"❌ Case correction failed")
        
        # Test the manual base58 approach you provided
        try:
            import base58
            raw = base58.b58decode(lowercase)
            restored = base58.b58encode(raw).decode("utf-8")
            print(f"Manual base58 result: {restored}")
            
            if restored == corrected:
                print(f"✅ Method matches manual approach")
            else:
                print(f"⚠️  Method differs from manual approach")
                print(f"   Method: {corrected}")
                print(f"   Manual: {restored}")
        except Exception as e:
            print(f"❌ Manual base58 test failed: {e}")


def test_url_extraction():
    """Test URL extraction with corrected addresses."""
    
    print("\n" + "=" * 50)
    print("🧪 Testing URL Extraction with Address Correction")
    print("=" * 50)
    
    test_urls = [
        "/solana/ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9",
        "/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o",
        "/solana/3ismqtviyuhggvmbxoui7h5fwq5ktjwaeonvcnq1uqds"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\nTest {i}: {url}")
        
        # Extract and correct the address
        corrected_address = SolanaAddressParser.extract_pool_address_from_url(url)
        
        print(f"Extracted and corrected: {corrected_address}")
        
        if corrected_address:
            valid = SolanaAddressParser.is_valid_solana_address(corrected_address)
            print(f"Valid: {valid}")
            
            if valid:
                print(f"✅ Successfully extracted and corrected address")
            else:
                print(f"❌ Extracted address is invalid")
        else:
            print(f"❌ Failed to extract address")


def test_enhanced_parser_integration():
    """Test the enhanced parser with corrected addresses."""
    
    print("\n" + "=" * 50)
    print("🧪 Testing Enhanced Parser Integration")
    print("=" * 50)
    
    # Sample CSV row data
    test_row = {
        'tokenSymbol': 'SANTA',
        'tokenName': 'SANTA',
        'poolAddress': 'test_pool',  # This will be overridden by URL extraction
        'dex': 'Raydium',
        'price': '0.006221',
        'marketCap': '1000000',
        'liquidity': '113000',
        'volume': '268000',
        'priceChange5m': '-0.21',
        'priceChange1h': '-6.71',
        'priceChange6h': '-12.52',
        'priceChange24h': '-14.82',
        'transactions': '106224',
        'makers': '104729',
        'age': '1y',
        'detailUrl': '/solana/ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9'
    }
    
    print("Test row data:")
    print(f"  Token: {test_row['tokenSymbol']} ({test_row['tokenName']})")
    print(f"  Detail URL: {test_row['detailUrl']}")
    
    # Test address extraction
    extracted_address = SolanaAddressParser.extract_pool_address_from_url(test_row['detailUrl'])
    
    print(f"\nExtracted address: {extracted_address}")
    
    if extracted_address:
        valid = SolanaAddressParser.is_valid_solana_address(extracted_address)
        print(f"Address valid: {valid}")
        
        if valid:
            print(f"✅ Address extraction and correction successful")
            print(f"   This address should work with GeckoTerminal API")
        else:
            print(f"❌ Extracted address is still invalid")
    else:
        print(f"❌ Address extraction failed")


def main():
    """Run all address correction tests."""
    
    try:
        test_base58_correction()
        test_url_extraction()
        test_enhanced_parser_integration()
        
        print("\n" + "=" * 50)
        print("✅ Address correction testing completed!")
        print("\nIf all tests passed, the base58 correction should now work properly")
        print("and resolve the 404 errors you were seeing.")
        
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()