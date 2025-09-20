#!/usr/bin/env python3
"""
Test script to verify the bug fixes for the comprehensive test suite.

This script specifically tests the three main bug categories that were identified:
1. Configuration interface issues
2. Database configuration issues  
3. NautilusTrader integration issues
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from nautilus_poc.config import NautilusPOCConfig, Q50Config, PumpSwapConfig, SolanaConfig, NautilusConfig
from nautilus_poc.position_sizer import KellyPositionSizer
from nautilus_poc.risk_manager import RiskManager
from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.q50_nautilus_strategy import Q50NautilusStrategy

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_config() -> NautilusPOCConfig:
    """Create test configuration"""
    return NautilusPOCConfig(
        environment='testnet',
        q50=Q50Config(
            features_path='test_features.pkl',
            signal_tolerance_minutes=5,
            required_columns=['q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 'prob_up', 'economically_significant', 'high_quality', 'tradeable']
        ),
        pumpswap=PumpSwapConfig(
            payer_public_key='test_public_key',
            private_key_path='test_private_key.json',
            max_slippage_percent=5.0,
            base_position_size=0.1,
            max_position_size=0.5,
            min_liquidity_sol=10.0,
            max_price_impact_percent=10.0,
            stop_loss_percent=20.0,
            position_timeout_hours=24
        ),
        solana=SolanaConfig(
            network='testnet',
            rpc_endpoint='https://api.testnet.solana.com',
            commitment='confirmed'
        ),
        nautilus=NautilusConfig(
            instance_id='TEST-BUG-FIX-001',
            log_level='INFO',
            cache_database_path='test_cache.db'
        ),
        monitoring={'enable_performance_tracking': True},
        error_handling={'max_retries': 3, 'retry_delay_base': 1.0},
        regime_detection={
            'vol_risk_percentiles': {'low': 0.30, 'high': 0.70, 'extreme': 0.90},
            'regime_multipliers': {'low_variance': 0.7, 'medium_variance': 1.0, 'high_variance': 1.4, 'extreme_variance': 1.8}
        }
    )


def test_configuration_interface_fixes():
    """Test Fix 1: Configuration interface standardization"""
    logger.info("Testing configuration interface fixes...")
    
    config = create_test_config()
    
    try:
        # Test KellyPositionSizer with NautilusPOCConfig object
        position_sizer = KellyPositionSizer(config)
        assert position_sizer.pumpswap_config['base_position_size'] == 0.1
        assert position_sizer.pumpswap_config['max_position_size'] == 0.5
        logger.info("✓ KellyPositionSizer accepts NautilusPOCConfig object")
        
        # Test RiskManager with NautilusPOCConfig object
        risk_manager = RiskManager(config)
        assert risk_manager.pumpswap_config['max_position_size'] == 0.5
        assert risk_manager.pumpswap_config['stop_loss_percent'] == 20.0
        logger.info("✓ RiskManager accepts NautilusPOCConfig object")
        
        # Test with dictionary config (backward compatibility)
        dict_config = {
            'pumpswap': {
                'base_position_size': 0.1,
                'max_position_size': 0.5,
                'stop_loss_percent': 20.0,
                'max_slippage_percent': 5.0
            },
            'regime_detection': config.regime_detection
        }
        
        position_sizer_dict = KellyPositionSizer(dict_config)
        assert position_sizer_dict.pumpswap_config['base_position_size'] == 0.1
        logger.info("✓ Components maintain backward compatibility with dict configs")
        
        return True
        
    except Exception as e:
        logger.error(f"Configuration interface test failed: {e}")
        return False


def test_database_configuration_fixes():
    """Test Fix 2: Database configuration issues"""
    logger.info("Testing database configuration fixes...")
    
    try:
        # Test with host/port format (old format)
        config_dict = {
            'q50': {
                'features_path': 'test_features.pkl',
                'signal_tolerance_minutes': 5,
                'required_columns': ['q10', 'q50', 'q90']
            },
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_password'
            }
        }
        
        signal_loader = Q50SignalLoader(config_dict)
        logger.info("✓ Q50SignalLoader handles host/port database config format")
        
        # Test with URL format (new format)
        config_dict_url = {
            'q50': {
                'features_path': 'test_features.pkl',
                'signal_tolerance_minutes': 5,
                'required_columns': ['q10', 'q50', 'q90']
            },
            'database': {
                'url': 'sqlite:///test.db'
            }
        }
        
        signal_loader_url = Q50SignalLoader(config_dict_url)
        logger.info("✓ Q50SignalLoader handles URL database config format")
        
        # Test with missing database config (fallback)
        config_dict_minimal = {
            'q50': {
                'features_path': 'test_features.pkl',
                'signal_tolerance_minutes': 5,
                'required_columns': ['q10', 'q50', 'q90']
            }
        }
        
        signal_loader_minimal = Q50SignalLoader(config_dict_minimal)
        logger.info("✓ Q50SignalLoader handles missing database config with fallback")
        
        return True
        
    except Exception as e:
        logger.error(f"Database configuration test failed: {e}")
        return False


def test_nautilus_integration_fixes():
    """Test Fix 3: NautilusTrader integration issues"""
    logger.info("Testing NautilusTrader integration fixes...")
    
    try:
        config = create_test_config()
        strategy = Q50NautilusStrategy(config)
        
        # Test property access (should work now)
        initial_status = strategy.is_initialized
        assert initial_status == False
        logger.info("✓ Strategy is_initialized property getter works")
        
        # Test property setter (should work now)
        strategy.is_initialized = True
        assert strategy.is_initialized == True
        logger.info("✓ Strategy is_initialized property setter works")
        
        # Reset for clean state
        strategy.is_initialized = False
        assert strategy.is_initialized == False
        logger.info("✓ Strategy is_initialized property maintains state correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"NautilusTrader integration test failed: {e}")
        return False


def main():
    """Run all bug fix tests"""
    logger.info("🔧 Testing Bug Fixes for NautilusTrader POC")
    logger.info("=" * 50)
    
    tests = [
        ("Configuration Interface Fixes", test_configuration_interface_fixes),
        ("Database Configuration Fixes", test_database_configuration_fixes),
        ("NautilusTrader Integration Fixes", test_nautilus_integration_fixes)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 {test_name}")
        logger.info("-" * 30)
        
        try:
            if test_func():
                logger.info(f"✅ {test_name} - PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} - FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} - ERROR: {e}")
            failed += 1
    
    logger.info("\n" + "=" * 50)
    logger.info("🎯 BUG FIX TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Total Tests: {passed + failed}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("🎉 All bug fixes verified! The issues have been resolved.")
        return 0
    else:
        logger.error(f"⚠️ {failed} bug fix tests failed. Additional work needed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())