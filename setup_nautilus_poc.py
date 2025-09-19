#!/usr/bin/env python3
"""
Setup script for NautilusTrader POC environment
Handles dependency installation, wallet setup, and environment validation
"""

import os
import sys
import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NautilusPOCSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_path = self.project_root / "config.yaml"
        self.requirements_path = self.project_root / "requirements.txt"
        self.data_dir = self.project_root / "data3"
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from config.yaml"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        logger.info("Installing Python dependencies...")
        try:
            # Upgrade pip first
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                         check=True, capture_output=True)
            
            # Install requirements
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(self.requirements_path)], 
                         check=True, capture_output=True)
            
            logger.info("✓ Python dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            logger.error(f"Error output: {e.stderr.decode() if e.stderr else 'No error output'}")
            return False
    
    def setup_solana_cli(self) -> bool:
        """Setup Solana CLI for testnet"""
        logger.info("Setting up Solana CLI...")
        try:
            # Check if solana CLI is installed
            result = subprocess.run(["solana", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Solana CLI not found. Installation instructions:")
                self._print_solana_install_instructions()
                return False
            
            logger.info(f"Solana CLI version: {result.stdout.strip()}")
            
            # Configure for testnet
            subprocess.run(["solana", "config", "set", "--url", "https://api.testnet.solana.com"], 
                         check=True, capture_output=True)
            
            logger.info("✓ Solana CLI configured for testnet")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup Solana CLI: {e}")
            return False
        except FileNotFoundError:
            logger.warning("Solana CLI not found. Installation instructions:")
            self._print_solana_install_instructions()
            return False
    
    def _print_solana_install_instructions(self):
        """Print platform-specific Solana CLI installation instructions"""
        import platform
        system = platform.system().lower()
        
        logger.info("=== Solana CLI Installation Instructions ===")
        
        if system == "windows":
            logger.info("For Windows:")
            logger.info("1. Download the installer from: https://github.com/solana-labs/solana/releases")
            logger.info("2. Or use PowerShell:")
            logger.info("   Invoke-WebRequest -Uri https://release.solana.com/v1.16.0/solana-install-init-x86_64-pc-windows-msvc.exe -OutFile solana-install-init.exe")
            logger.info("   .\\solana-install-init.exe")
            logger.info("3. Restart your terminal after installation")
        elif system == "darwin":  # macOS
            logger.info("For macOS:")
            logger.info("1. Using Homebrew: brew install solana")
            logger.info("2. Or using the installer:")
            logger.info("   sh -c \"$(curl -sSfL https://release.solana.com/v1.16.0/install)\"")
        else:  # Linux
            logger.info("For Linux:")
            logger.info("sh -c \"$(curl -sSfL https://release.solana.com/v1.16.0/install)\"")
        
        logger.info("\nAfter installation, restart your terminal and run this setup again.")
        logger.info("Documentation: https://docs.solana.com/cli/install-solana-cli-tools")
    
    def create_testnet_wallet(self) -> Optional[str]:
        """Create or load testnet wallet"""
        logger.info("Setting up testnet wallet...")
        
        wallet_path = self.project_root / "testnet_wallet.json"
        
        try:
            if wallet_path.exists():
                logger.info("Using existing testnet wallet")
                # Get public key
                result = subprocess.run(["solana", "address", "-k", str(wallet_path)], 
                                      capture_output=True, text=True, check=True)
                public_key = result.stdout.strip()
            else:
                # Create new wallet
                logger.info("Creating new testnet wallet...")
                subprocess.run(["solana-keygen", "new", "--outfile", str(wallet_path), "--no-bip39-passphrase"], 
                             check=True, capture_output=True)
                
                # Get public key
                result = subprocess.run(["solana", "address", "-k", str(wallet_path)], 
                                      capture_output=True, text=True, check=True)
                public_key = result.stdout.strip()
            
            logger.info(f"Wallet public key: {public_key}")
            
            # Check balance
            balance_result = subprocess.run(["solana", "balance", public_key], 
                                          capture_output=True, text=True)
            if balance_result.returncode == 0:
                balance = balance_result.stdout.strip()
                logger.info(f"Current balance: {balance}")
                
                if "0 SOL" in balance:
                    logger.info("Requesting testnet SOL airdrop...")
                    subprocess.run(["solana", "airdrop", "2", public_key], 
                                 capture_output=True)
                    logger.info("✓ Airdrop requested (may take a few moments)")
            
            return public_key
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Wallet setup skipped - Solana CLI required: {e}")
            logger.info("Install Solana CLI first, then run setup again for wallet creation")
            return None
    
    def create_data_directory(self) -> bool:
        """Create data directory structure"""
        logger.info("Creating data directory structure...")
        try:
            self.data_dir.mkdir(exist_ok=True)
            
            # Create placeholder for macro_features.pkl
            placeholder_path = self.data_dir / "README.md"
            if not placeholder_path.exists():
                with open(placeholder_path, 'w') as f:
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
    
    def validate_q50_integration_points(self) -> bool:
        """Validate existing Q50 system integration points"""
        logger.info("Validating Q50 system integration points...")
        
        validation_results = []
        
        # Check database connection
        try:
            config = self.load_config()
            db_url = config.get('database', {}).get('url', '')
            if db_url:
                logger.info("✓ Database configuration found")
                validation_results.append(True)
            else:
                logger.warning("⚠ Database configuration not found")
                validation_results.append(False)
        except Exception as e:
            logger.error(f"Database validation failed: {e}")
            validation_results.append(False)
        
        # Check for existing collector infrastructure
        collector_path = self.project_root / "gecko_terminal_collector"
        if collector_path.exists():
            logger.info("✓ Existing collector infrastructure found")
            validation_results.append(True)
        else:
            logger.warning("⚠ Collector infrastructure not found")
            validation_results.append(False)
        
        # Check for QLib integration
        try:
            import qlib
            logger.info("✓ QLib available for integration")
            validation_results.append(True)
        except ImportError:
            logger.info("ℹ QLib not installed (optional)")
            validation_results.append(True)  # Not required
        
        # Check data directory
        if self.data_dir.exists():
            logger.info("✓ Data directory exists")
            validation_results.append(True)
        else:
            logger.warning("⚠ Data directory not found")
            validation_results.append(False)
        
        success_rate = sum(validation_results) / len(validation_results)
        logger.info(f"Integration validation: {success_rate:.1%} successful")
        
        return success_rate >= 0.75  # 75% success rate required
    
    def create_environment_file(self, public_key: Optional[str] = None) -> bool:
        """Create environment file template"""
        logger.info("Creating environment configuration...")
        
        env_path = self.project_root / ".env.nautilus"
        
        try:
            with open(env_path, 'w') as f:
                f.write("""# NautilusTrader POC Environment Configuration
# Copy this file to .env and fill in the values

# Solana Wallet Configuration (REQUIRED)
NAUTILUS_PAYER_PUBLIC_KEY=""" + (public_key or "YOUR_WALLET_PUBLIC_KEY_HERE") + """
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
    
    def run_setup(self) -> bool:
        """Run complete setup process"""
        logger.info("Starting NautilusTrader POC setup...")
        
        steps = [
            ("Installing dependencies", self.install_dependencies),
            ("Setting up Solana CLI", self.setup_solana_cli),
            ("Creating data directory", self.create_data_directory),
            ("Validating Q50 integration", self.validate_q50_integration_points),
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
        
        # Wallet setup (optional)
        logger.info("\n--- Setting up testnet wallet ---")
        public_key = self.create_testnet_wallet()
        
        # Environment file creation
        logger.info("\n--- Creating environment configuration ---")
        self.create_environment_file(public_key)
        
        # Summary
        success_count = sum(results)
        total_count = len(results)
        
        logger.info(f"\n=== Setup Summary ===")
        logger.info(f"Completed: {success_count}/{total_count} steps")
        
        if success_count == total_count:
            logger.info("🎉 Setup completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Review and customize .env.nautilus")
            logger.info("2. Place your Q50 data file in data3/macro_features.pkl")
            logger.info("3. Run the POC with: python -m nautilus_poc.main")
            return True
        else:
            logger.warning("⚠ Setup completed with some issues")
            logger.info("Please review the warnings above and resolve any issues")
            return False

def main():
    """Main setup function"""
    setup = NautilusPOCSetup()
    success = setup.run_setup()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()