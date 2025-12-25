#!/usr/bin/env python3
"""
Debug script to understand base58 encoding and find the correct replacements.
"""

import base58

def analyze_base58():
    """Analyze base58 alphabet and test different replacements."""
    
    print("Base58 Alphabet Analysis")
    print("=" * 40)
    
    # Base58 alphabet (Bitcoin/Solana standard)
    base58_alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    print(f"Base58 alphabet: {base58_alphabet}")
    print(f"Length: {len(base58_alphabet)}")
    
    # Characters excluded from base58
    excluded = ['0', 'O', 'I', 'l']
    print(f"Excluded characters: {excluded}")
    
    # Test problematic addresses
    problematic_addresses = [
        "ejuwjjff9rcdm6ndrh84awhzfbcybytckzvsbspltwh9",
        "26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o"
    ]
    
    print("\nAnalyzing problematic addresses:")
    for addr in problematic_addresses:
        print(f"\nAddress: {addr}")
        
        # Find invalid characters
        invalid_chars = []
        for char in addr:
            if char not in base58_alphabet:
                invalid_chars.append(char)
        
        print(f"Invalid characters: {set(invalid_chars)}")
        
        # Try different replacement strategies
        strategies = [
            {'l': '1'},  # lowercase L -> number 1
            {'l': 'i'},  # lowercase L -> lowercase i  
            {'l': 'L'},  # lowercase L -> uppercase L
            {'l': 'j'},  # lowercase L -> j (similar shape)
        ]
        
        for i, strategy in enumerate(strategies, 1):
            print(f"\nStrategy {i}: {strategy}")
            
            corrected = addr
            for old, new in strategy.items():
                corrected = corrected.replace(old, new)
            
            print(f"Corrected: {corrected}")
            
            # Test if it's valid base58
            try:
                decoded = base58.b58decode(corrected)
                if len(decoded) == 32:  # Solana addresses are 32 bytes
                    # Try to re-encode
                    reencoded = base58.b58encode(decoded).decode('utf-8')
                    print(f"✅ Valid! Re-encoded: {reencoded}")
                else:
                    print(f"❌ Wrong length: {len(decoded)} bytes (expected 32)")
            except Exception as e:
                print(f"❌ Invalid base58: {e}")


def test_known_good_addresses():
    """Test with known good Solana addresses."""
    
    print("\n" + "=" * 40)
    print("Testing Known Good Addresses")
    print("=" * 40)
    
    # Some known Solana addresses (these should work)
    known_addresses = [
        "So11111111111111111111111111111111111112",  # Wrapped SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    ]
    
    for addr in known_addresses:
        print(f"\nTesting: {addr}")
        
        try:
            decoded = base58.b58decode(addr)
            print(f"✅ Valid base58, {len(decoded)} bytes")
            
            reencoded = base58.b58encode(decoded).decode('utf-8')
            print(f"Re-encoded: {reencoded}")
            
            if reencoded == addr:
                print("✅ Encoding/decoding consistent")
            else:
                print("❌ Encoding/decoding inconsistent")
                
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    analyze_base58()
    test_known_good_addresses()