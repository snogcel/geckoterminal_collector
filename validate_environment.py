#!/usr/bin/env python3
"""
Environment validation script for NautilusTrader POC
Validates all dependencies, configuration, and integration points
"""

import sys
import subprocess
import importlib
from pathlib import Path
import logging
import yaml
from typing import List, Tuple, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnvironmentValidator:
    """Validates NautilusTrader POC environment setup"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.validation_results = []
    
    def validate_python_dependencies(self) -> bool:
        """Validate Python package dependencies"""
        logger.info("Validating Python dependencies...")
        
        required_packages = [
            # Core dependencies
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('sqlalchemy', 'sqlalchemy'),
            ('pydantic', 'pydantic'),
            ('yaml', 'pyyaml'),
            
            # NautilusTrader dependencies
            ('nautilus_trader', 'nautilus_trader'),
            ('msgspec', 'msgspec'),
            ('redis', 'redis'),
            
            # Solana dependencies
            ('solana', 'solana'),
            ('solders', 'solders'),
            ('anchorpy', 'anchorpy'),
            
            # Crypto dependencies
            ('cryptography', 'cryptography'),
            ('base58', 'base58'),
        ]
        
        missing_packages = []
        for import_name, package_name in required_packages:
            try:
                importlib.import_module(import_name)
                logger.info(f"✓ {package_name}")
            except ImportError:
                logger.error(f"✗ {package_name} - Missing")
                missing_packages.append(package_name)
        
        if missing_packages:
            logger.error(f"Missing packages: {', '.join(missing_packages)}")
            logger.error("Run: pip install -r requirements.txt")
            return False
        
        logger.info("✓ All Python dependencies available")
        return True
    
    def validate_solana_cli(self) -> bool:
        """Validate Solana CLI installation and configuration"""
        logger.info("Validating Solana CLI...")
        
        try:
            # Check Solana CLI version
            result = subprocess.run(["solana", "--version"], 
                                  capture_output=True, text=True, check=True)
            logger.info(f"✓ Solana CLI: {result.stdout.strip()}")
            
            # Check configuration
            config_result = subprocess.run(["solana", "config", "get"], 
                                         capture_output=True, text=True, check=True)
            logger.info("✓ Solana CLI configuration:")
            for line in config_result.stdout.strip().split('\n'):
                logger.info(f"  {line}")
            
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("✗ Solana CLI not found or not configured")
            logger.error("Install: https://docs.solana.com/cli/install-solana-cli-tools")
            return False
    
    def validate_wallet_setup(self) -> bool:
        """Validate testnet wallet setup"""
        logger.info("Validating wallet setup...")
        
        wallet_path = self.project_root / "testnet_wallet.json"
        env_path = self.project_root / ".env.nautilus"
        
        if not wallet_path.exists():
            logger.warning("⚠ Testnet wallet not found")
            logger.info("Run create_test_wallet.py to create wallet")
            return False
        
        try:
            # Load wallet using Python Solana libraries
            import json
            from solders.keypair import Keypair
            
            with open(wallet_path, 'r') as f:
                private_key_bytes = json.load(f)
            
            # Create keypair from private key (Solana uses 32-byte secret key)
            if len(private_key_bytes) == 32:
                # Convert to 64-byte format expected by Keypair.from_bytes
                keypair = Keypair.from_seed(bytes(private_key_bytes))
            else:
                keypair = Keypair.from_bytes(bytes(private_key_bytes))
            address = str(keypair.pubkey())
            
            logger.info(f"✓ Wallet address: {address}")
            
            # Check if environment file exists
            if env_path.exists():
                logger.info("✓ Environment configuration found")
                
                # Validate environment file contains the correct public key
                with open(env_path, 'r') as f:
                    env_content = f.read()
                    if address in env_content:
                        logger.info("✓ Environment file matches wallet")
                    else:
                        logger.warning("⚠ Environment file may not match wallet")
            else:
                logger.warning("⚠ Environment file not found")
            
            # Note about balance checking
            logger.info("ℹ To check balance, use Solana explorer or faucet")
            logger.info(f"  Testnet explorer: https://explorer.solana.com/address/{address}?cluster=testnet")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Wallet validation failed: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate configuration files"""
        logger.info("Validating configuration...")
        
        config_path = self.project_root / "config.yaml"
        if not config_path.exists():
            logger.error("✗ config.yaml not found")
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check for nautilus_poc section
            if 'nautilus_poc' not in config:
                logger.error("✗ nautilus_poc section missing from config.yaml")
                return False
            
            nautilus_config = config['nautilus_poc']
            
            # Validate required sections
            required_sections = ['q50', 'pumpswap', 'solana', 'nautilus']
            for section in required_sections:
                if section not in nautilus_config:
                    logger.error(f"✗ {section} section missing from nautilus_poc config")
                    return False
                logger.info(f"✓ {section} configuration found")
            
            # Check Q50 required columns
            q50_config = nautilus_config.get('q50', {})
            required_columns = q50_config.get('required_columns', [])
            expected_columns = ['q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
                              'prob_up', 'economically_significant', 'high_quality', 'tradeable']
            
            if set(required_columns) != set(expected_columns):
                logger.warning("⚠ Q50 required_columns may be incomplete")
            else:
                logger.info("✓ Q50 required columns configured")
            
            logger.info("✓ Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Configuration validation failed: {e}")
            return False
    
    def validate_data_directory(self) -> bool:
        """Validate data directory and Q50 integration points"""
        logger.info("Validating data directory...")
        
        data_dir = self.project_root / "data3"
        if not data_dir.exists():
            logger.error("✗ data3 directory not found")
            return False
        
        logger.info("✓ data3 directory exists")
        
        # Check for macro_features.pkl
        features_file = data_dir / "macro_features.pkl"
        if features_file.exists():
            logger.info("✓ macro_features.pkl found")
            
            # Try to validate the file structure
            try:
                import pandas as pd
                df = pd.read_pickle(features_file)
                logger.info(f"✓ macro_features.pkl loaded: {df.shape}")
                
                # Check required columns
                expected_columns = ['q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
                                  'prob_up', 'economically_significant', 'high_quality', 'tradeable']
                missing_columns = [col for col in expected_columns if col not in df.columns]
                
                if missing_columns:
                    logger.warning(f"⚠ Missing columns in macro_features.pkl: {missing_columns}")
                else:
                    logger.info("✓ All required Q50 columns present")
                
            except Exception as e:
                logger.warning(f"⚠ Could not validate macro_features.pkl: {e}")
        else:
            logger.warning("⚠ macro_features.pkl not found - required for Q50 integration")
            logger.info("Place your Q50 signal data file in data3/macro_features.pkl")
        
        return True
    
    def validate_database_connection(self) -> bool:
        """Validate database connection"""
        logger.info("Validating database connection...")
        
        try:
            config_path = self.project_root / "config.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            db_config = config.get('database', {})
            db_url = db_config.get('url', '')
            
            if not db_url:
                logger.warning("⚠ Database URL not configured")
                return False
            
            # Try to connect
            from sqlalchemy import create_engine
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text("SELECT 1"))
                logger.info("✓ Database connection successful")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠ Database connection failed: {e}")
            logger.info("Database connection is optional for basic POC functionality")
            return False
    
    def validate_project_structure(self) -> bool:
        """Validate project structure"""
        logger.info("Validating project structure...")
        
        required_files = [
            "config.yaml",
            "requirements.txt",
            "setup_nautilus_poc.py",
            "nautilus_poc/__init__.py",
            "nautilus_poc/config.py",
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                logger.info(f"✓ {file_path}")
            else:
                logger.error(f"✗ {file_path} - Missing")
                missing_files.append(file_path)
        
        if missing_files:
            logger.error(f"Missing files: {', '.join(missing_files)}")
            return False
        
        logger.info("✓ Project structure validation passed")
        return True
    
    def run_validation(self) -> bool:
        """Run complete environment validation"""
        logger.info("Starting NautilusTrader POC environment validation...")
        
        validation_steps = [
            ("Project Structure", self.validate_project_structure),
            ("Python Dependencies", self.validate_python_dependencies),
            ("Configuration", self.validate_configuration),
            ("Data Directory", self.validate_data_directory),
            ("Solana CLI", self.validate_solana_cli),
            ("Wallet Setup", self.validate_wallet_setup),
            ("Database Connection", self.validate_database_connection),
        ]
        
        results = []
        for step_name, step_func in validation_steps:
            logger.info(f"\n--- {step_name} ---")
            try:
                result = step_func()
                results.append((step_name, result))
                if result:
                    logger.info(f"✓ {step_name} validation passed")
                else:
                    logger.warning(f"⚠ {step_name} validation failed")
            except Exception as e:
                logger.error(f"✗ {step_name} validation error: {e}")
                results.append((step_name, False))
        
        # Summary
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        logger.info(f"\n=== Validation Summary ===")
        logger.info(f"Passed: {passed}/{total} validations")
        
        for step_name, result in results:
            status = "✓" if result else "✗"
            logger.info(f"{status} {step_name}")
        
        if passed == total:
            logger.info("🎉 Environment validation completed successfully!")
            logger.info("Ready to run NautilusTrader POC")
            return True
        else:
            logger.warning("⚠ Environment validation completed with issues")
            logger.info("Please resolve the issues above before running the POC")
            return False

def main():
    """Main validation function"""
    validator = EnvironmentValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()