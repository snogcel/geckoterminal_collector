#!/usr/bin/env python3
"""
Complete setup script for NautilusTrader POC
Runs all setup steps and validates the environment
"""

import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_script(script_name, description):
    """Run a Python script and return success status"""
    logger.info(f"\n=== {description} ===")
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, check=True)
        logger.info(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed")
        logger.error(f"Error: {e.stderr}")
        return False

def main():
    """Run complete setup process"""
    logger.info("Starting complete NautilusTrader POC setup...")
    
    setup_steps = [
        ("create_mock_q50_data.py", "Creating mock Q50 data"),
        ("create_test_wallet.py", "Creating test wallet"),
        ("validate_environment.py", "Validating environment"),
    ]
    
    results = []
    for script, description in setup_steps:
        if Path(script).exists():
            success = run_script(script, description)
            results.append((description, success))
        else:
            logger.warning(f"⚠ Script {script} not found, skipping {description}")
            results.append((description, False))
    
    # Summary
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    logger.info(f"\n=== Setup Summary ===")
    logger.info(f"Completed: {successful}/{total} steps")
    
    for description, success in results:
        status = "✓" if success else "✗"
        logger.info(f"{status} {description}")
    
    if successful >= total - 1:  # Allow one failure (e.g., Solana CLI)
        logger.info("\n🎉 NautilusTrader POC setup completed successfully!")
        logger.info("\n=== Next Steps ===")
        logger.info("1. Review configuration in config.yaml")
        logger.info("2. Check environment settings in .env.nautilus")
        logger.info("3. Get testnet SOL from faucet (see wallet address in logs)")
        logger.info("4. Start implementing Q50 signal integration")
        logger.info("5. Run: python -m nautilus_poc.main (when implemented)")
        return True
    else:
        logger.warning("⚠ Setup completed with issues")
        logger.info("Please resolve the issues above before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)