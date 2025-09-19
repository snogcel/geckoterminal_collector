#!/usr/bin/env python3
"""
Create test wallet for NautilusTrader POC without requiring Solana CLI
"""

import json
import base58
from solders.keypair import Keypair
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_wallet():
    """Create a test wallet using Python Solana libraries"""
    
    # Generate new keypair
    keypair = Keypair()
    
    # Get public key
    public_key = str(keypair.pubkey())
    
    # Get private key as bytes array (compatible with Solana CLI format)
    private_key_bytes = list(keypair.secret())
    
    logger.info(f"Generated wallet:")
    logger.info(f"  Public Key: {public_key}")
    logger.info(f"  Private Key Length: {len(private_key_bytes)} bytes")
    
    return public_key, private_key_bytes

def save_wallet(private_key_bytes, filename="testnet_wallet.json"):
    """Save wallet in Solana CLI compatible format"""
    
    wallet_path = Path(filename)
    
    # Save private key in Solana CLI format (array of bytes)
    with open(wallet_path, 'w') as f:
        json.dump(private_key_bytes, f)
    
    logger.info(f"✓ Wallet saved to {wallet_path}")
    return wallet_path

def create_env_file(public_key, wallet_path):
    """Create environment file with wallet configuration"""
    
    env_content = f"""# NautilusTrader POC Environment Configuration
# Generated wallet configuration

# Solana Wallet Configuration
NAUTILUS_PAYER_PUBLIC_KEY={public_key}
NAUTILUS_PRIVATE_KEY_PATH={wallet_path}

# Solana Network Configuration (Testnet)
NAUTILUS_SOLANA_RPC_ENDPOINT=https://api.testnet.solana.com
NAUTILUS_SOLANA_NETWORK=testnet

# Trading Configuration
NAUTILUS_MAX_POSITION_SIZE=0.5
NAUTILUS_BASE_POSITION_SIZE=0.1
NAUTILUS_MAX_SLIPPAGE=5.0

# Monitoring Configuration
NAUTILUS_LOG_LEVEL=INFO
NAUTILUS_ENABLE_PERFORMANCE_TRACKING=true

# Note: This is a testnet wallet for development only
# For mainnet trading, use a secure hardware wallet
"""
    
    env_path = Path(".env.nautilus")
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    logger.info(f"✓ Environment file created: {env_path}")
    return env_path

def main():
    """Create test wallet and environment configuration"""
    logger.info("Creating test wallet for NautilusTrader POC...")
    
    try:
        # Create wallet
        public_key, private_key_bytes = create_test_wallet()
        
        # Save wallet file
        wallet_path = save_wallet(private_key_bytes)
        
        # Create environment file
        env_path = create_env_file(public_key, wallet_path)
        
        logger.info("\n=== Wallet Setup Complete ===")
        logger.info(f"Public Key: {public_key}")
        logger.info(f"Wallet File: {wallet_path}")
        logger.info(f"Environment: {env_path}")
        
        logger.info("\n=== Next Steps ===")
        logger.info("1. This is a TESTNET wallet for development only")
        logger.info("2. To get testnet SOL, use a faucet:")
        logger.info("   - https://faucet.solana.com/")
        logger.info("   - https://solfaucet.com/")
        logger.info(f"3. Send testnet SOL to: {public_key}")
        logger.info("4. Run validation: python validate_environment.py")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create wallet: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)