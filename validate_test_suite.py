#!/usr/bin/env python3
"""
Test Suite Validation Script

This script validates that the comprehensive test suite can be imported
and basic functionality works before running the full test suite.
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_imports():
    """Validate that all test components can be imported"""
    logger.info("Validating test suite imports...")
    
    try:
        # Test core imports
        import pandas as pd
        import numpy as np
        logger.info("✓ Core dependencies (pandas, numpy)")
        
        # Test nautilus_poc imports
        from nautilus_poc.config import NautilusPOCConfig
        from nautilus_poc.signal_loader import Q50SignalLoader
        from nautilus_poc.regime_detector import RegimeDetector
        from nautilus_poc.pumpswap_executor import PumpSwapExecutor
        from nautilus_poc.liquidity_validator import LiquidityValidator
        from nautilus_poc.position_sizer import KellyPositionSizer
        from nautilus_poc.risk_manager import RiskManager
        from nautilus_poc.q50_nautilus_strategy import Q50NautilusStrategy
        logger.info("✓ NautilusPOC components")
        
        # Test comprehensive test suite import
        from test_nautilus_poc_comprehensive import TestDataGenerator
        logger.info("✓ Comprehensive test suite")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False


def validate_test_data_generation():
    """Validate test data generation"""
    logger.info("Validating test data generation...")
    
    try:
        from test_nautilus_poc_comprehensive import TestDataGenerator
        
        # Test configuration generation
        config = TestDataGenerator.create_test_config()
        assert config.environment == 'testnet'
        logger.info("✓ Test configuration generation")
        
        # Test Q50 data generation
        q50_data = TestDataGenerator.create_test_q50_data(10)
        assert len(q50_data) == 10
        assert 'q50' in q50_data.columns
        logger.info("✓ Q50 test data generation")
        
        # Test pool data generation
        pool_data = TestDataGenerator.create_test_pool_data()
        assert 'mint_address' in pool_data
        assert 'reserve_sol' in pool_data
        logger.info("✓ Pool test data generation")
        
        # Test mock tick generation
        mock_tick = TestDataGenerator.create_mock_tick()
        assert hasattr(mock_tick, 'bid_price')
        assert hasattr(mock_tick, 'ask_price')
        logger.info("✓ Mock tick generation")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Test data generation failed: {e}")
        return False


def validate_basic_functionality():
    """Validate basic functionality of key components"""
    logger.info("Validating basic component functionality...")
    
    try:
        from test_nautilus_poc_comprehensive import TestDataGenerator
        from nautilus_poc.regime_detector import RegimeDetector
        from nautilus_poc.position_sizer import KellyPositionSizer
        
        config = TestDataGenerator.create_test_config()
        
        # Test regime detector
        regime_detector = RegimeDetector({'regime_detection': config.regime_detection})
        test_signal = {'vol_risk': 0.3, 'q50': 0.5, 'prob_up': 0.6, 'vol_raw': 0.2}
        regime_info = regime_detector.classify_regime(test_signal)
        assert 'regime' in regime_info
        logger.info("✓ RegimeDetector basic functionality")
        
        # Test position sizer (convert config to dict format)
        config_dict = {
            'pumpswap': {
                'base_position_size': config.pumpswap.base_position_size,
                'max_position_size': config.pumpswap.max_position_size
            },
            'regime_detection': config.regime_detection
        }
        position_sizer = KellyPositionSizer(config_dict)
        pool_data = TestDataGenerator.create_test_pool_data()
        position_result = position_sizer.calculate_position_size(test_signal, pool_data)
        assert position_result.recommended_size > 0
        logger.info("✓ KellyPositionSizer basic functionality")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Basic functionality validation failed: {e}")
        return False


def main():
    """Main validation function"""
    logger.info("🔍 Validating NautilusTrader POC Test Suite")
    logger.info("=" * 50)
    
    validations = [
        ("Import Validation", validate_imports),
        ("Test Data Generation", validate_test_data_generation),
        ("Basic Functionality", validate_basic_functionality)
    ]
    
    all_passed = True
    
    for name, validation_func in validations:
        logger.info(f"\n📋 {name}")
        logger.info("-" * 30)
        
        try:
            if validation_func():
                logger.info(f"✅ {name} - PASSED")
            else:
                logger.error(f"❌ {name} - FAILED")
                all_passed = False
        except Exception as e:
            logger.error(f"❌ {name} - ERROR: {e}")
            all_passed = False
    
    logger.info("\n" + "=" * 50)
    if all_passed:
        logger.info("🎉 All validations passed! Test suite is ready to run.")
        logger.info("Run the full test suite with: python run_comprehensive_tests.py")
    else:
        logger.error("❌ Some validations failed. Please fix issues before running tests.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())