#!/usr/bin/env python3
"""
Simplified dependency setup for NautilusTrader POC
Focuses on Python dependencies and basic environment setup
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def install_python_dependencies():
    """Install Python dependencies"""
    logger.info("Installing Python dependencies...")
    try:
        # Upgrade pip first
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                     check=True, capture_output=True)
        
        # Install requirements
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                     check=True, capture_output=True)
        
        logger.info("✓ Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr.decode()}")
        return False

def create_data_directory():
    """Create data directory structure"""
    logger.info("Creating data directory structure...")
    try:
        data_dir = Path("data3")
        data_dir.mkdir(exist_ok=True)
        
        # Create placeholder for macro_features.pkl
        readme_path = data_dir / "README.md"
        if not readme_path.exists():
            with open(readme_path, 'w') as f:
                f.write("""# Q50 Data Directory

This directory should contain the Q50 signal data files:

## Required Files:
- `macro_features.pkl`: Q50 quantile predictions with required columns:
  - q10, q50, q90: Quantile predictions
  - vol_raw, vol_risk: Volatility measures
  - prob_up: Probability of upward movement
  - economically_significant: Economic significance flag
  - high_quality: Signal quality flag
  - tradeable: Tradeable status flag

## Data Format:
The macro_features.pkl file should be a pandas DataFrame with timestamp index
and the required columns listed above.

## Integration:
Place your existing Q50 signal data file here to integrate with the
NautilusTrader POC system.
""")
        
        logger.info("✓ Data directory structure created")
        return True
    except Exception as e:
        logger.error(f"Failed to create data directory: {e}")
        return False

def validate_existing_system():
    """Validate existing Q50 system integration points"""
    logger.info("Validating existing system integration points...")
    
    validation_results = []
    
    # Check database configuration
    try:
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        db_url = config.get('database', {}).get('url', '')
        if db_url:
            logger.info("✓ Database configuration found")
            validation_results.append(True)
        else:
            logger.warning("⚠ Database configuration not found")
            validation_results.append(False)
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        validation_results.append(False)
    
    # Check for existing collector infrastructure
    collector_path = Path("gecko_terminal_collector")
    if collector_path.exists():
        logger.info("✓ Existing collector infrastructure found")
        validation_results.append(True)
    else:
        logger.warning("⚠ Collector infrastructure not found")
        validation_results.append(False)
    
    # Check for NautilusTrader POC configuration
    try:
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        if 'nautilus_poc' in config:
            logger.info("✓ NautilusTrader POC configuration found")
            validation_results.append(True)
        else:
            logger.warning("⚠ NautilusTrader POC configuration not found")
            validation_results.append(False)
    except Exception as e:
        logger.error(f"NautilusTrader config validation failed: {e}")
        validation_results.append(False)
    
    success_rate = sum(validation_results) / len(validation_results)
    logger.info(f"Integration validation: {success_rate:.1%} successful")
    
    return success_rate >= 0.5  # 50% success rate required

def create_environment_template():
    """Create environment file template"""
    logger.info("Creating environment configuration template...")
    
    env_path = Path(".env.nautilus")
    
    try:
        with open(env_path, 'w') as f:
            f.write("""# NautilusTrader POC Environment Configuration
# Copy this file to .env and fill in the values

# Solana Wallet Configuration (REQUIRED - set after Solana CLI installation)
NAUTILUS_PAYER_PUBLIC_KEY=YOUR_WALLET_PUBLIC_KEY_HERE
NAUTILUS_PRIVATE_KEY_PATH=testnet_wallet.json

# Solana Network Configuration
NAUTILUS_SOLANA_RPC_ENDPOINT=https://api.testnet.solana.com
NAUTILUS_SOLANA_NETWORK=testnet

# Trading Configuration
NAUTILUS_MAX_POSITION_SIZE=0.5
NAUTILUS_BASE_POSITION_SIZE=0.1
NAUTILUS_MAX_SLIPPAGE=5.0

# Monitoring Configuration
NAUTILUS_LOG_LEVEL=INFO
NAUTILUS_ENABLE_PERFORMANCE_TRACKING=true

# Database Configuration (inherits from main config)
# GECKO_DB_URL=postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector
""")
        
        logger.info("✓ Environment configuration template created")
        logger.info(f"Please review and customize: {env_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create environment file: {e}")
        return False

def print_next_steps():
    """Print next steps for user"""
    logger.info("\n=== Next Steps ===")
    logger.info("1. Install Solana CLI:")
    logger.info("   Windows: Download from https://github.com/solana-labs/solana/releases")
    logger.info("   macOS: brew install solana")
    logger.info("   Linux: sh -c \"$(curl -sSfL https://release.solana.com/v1.16.0/install)\"")
    logger.info("")
    logger.info("2. After installing Solana CLI, run:")
    logger.info("   python setup_nautilus_poc.py")
    logger.info("")
    logger.info("3. Place your Q50 data file in:")
    logger.info("   data3/macro_features.pkl")
    logger.info("")
    logger.info("4. Review and customize:")
    logger.info("   .env.nautilus")
    logger.info("")
    logger.info("5. Validate environment:")
    logger.info("   python validate_environment.py")

def main():
    """Main setup function"""
    logger.info("Starting NautilusTrader POC dependency setup...")
    
    steps = [
        ("Installing Python dependencies", install_python_dependencies),
        ("Creating data directory", create_data_directory),
        ("Validating existing system", validate_existing_system),
        ("Creating environment template", create_environment_template),
    ]
    
    results = []
    for step_name, step_func in steps:
        logger.info(f"\n--- {step_name} ---")
        try:
            result = step_func()
            results.append(result)
            if result:
                logger.info(f"✓ {step_name} completed successfully")
            else:
                logger.warning(f"⚠ {step_name} completed with warnings")
        except Exception as e:
            logger.error(f"✗ {step_name} failed: {e}")
            results.append(False)
    
    # Summary
    success_count = sum(results)
    total_count = len(results)
    
    logger.info(f"\n=== Setup Summary ===")
    logger.info(f"Completed: {success_count}/{total_count} steps")
    
    if success_count >= total_count - 1:  # Allow one failure
        logger.info("🎉 Basic setup completed successfully!")
        print_next_steps()
        return True
    else:
        logger.warning("⚠ Setup completed with issues")
        logger.info("Please review the warnings above and resolve any issues")
        print_next_steps()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)