#!/usr/bin/env python3
"""
Test script for PumpSwap SDK Integration Layer

This script tests the PumpSwapExecutor and LiquidityValidator components
to ensure they work correctly with mock data.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from nautilus_poc import (
    ConfigManager, 
    PumpSwapExecutor, 
    LiquidityValidator,
    LiquidityStatus
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_liquidity_validator():
    """Test LiquidityValidator functionality"""
    logger.info("Testing LiquidityValidator...")
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    # Create validator
    validator = LiquidityValidator(config)
    
    # Test data
    good_pool_data = {
        'mint_address': 'So11111111111111111111111111111111111111112',
        'reserve_sol': 500.0,
        'reserve_in_usd': 50000,
        'price': 0.001,
        'volume_24h': 10000
    }
    
    poor_pool_data = {
        'mint_address': 'TestToken123',
        'reserve_sol': 5.0,  # Below minimum
        'reserve_in_usd': 500,
        'price': 0.001,
        'volume_24h': 100
    }
    
    test_signal = {
        'q50': 0.6,
        'vol_risk': 0.2,
        'tradeable': True,
        'economically_significant': True,
        'estimated_position_size': 1.0
    }
    
    # Test good pool
    result_good = validator.validate_liquidity_detailed(good_pool_data, test_signal, 'buy')
    logger.info(f"Good pool validation: {result_good.status.value}, valid={result_good.is_valid}")
    logger.info(f"Price impact: {result_good.estimated_price_impact:.2f}%")
    
    # Test poor pool
    result_poor = validator.validate_liquidity_detailed(poor_pool_data, test_signal, 'buy')
    logger.info(f"Poor pool validation: {result_poor.status.value}, valid={result_poor.is_valid}")
    
    # Test pair availability
    pair_available = validator.check_pair_availability(
        'So11111111111111111111111111111111111111112',
        'pair_So111111'
    )
    logger.info(f"Pair availability: {pair_available}")
    
    return result_good.is_valid and not result_poor.is_valid

async def test_pumpswap_executor():
    """Test PumpSwapExecutor functionality"""
    logger.info("Testing PumpSwapExecutor...")
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    # Create components
    validator = LiquidityValidator(config)
    executor = PumpSwapExecutor(config)
    
    # Set dependencies (in real implementation, these would be proper components)
    executor.set_dependencies(validator, None, None)  # position_manager and risk_manager are None for testing
    
    # Test signal
    test_signal = {
        'q50': 0.7,
        'vol_risk': 0.15,
        'tradeable': True,
        'economically_significant': True,
        'regime': 'medium_variance',
        'regime_multiplier': 1.2,
        'mint_address': 'So11111111111111111111111111111111111111112'
    }
    
    # Test buy execution
    logger.info("Testing buy execution...")
    buy_result = await executor.execute_buy_signal(test_signal)
    logger.info(f"Buy result: {buy_result['status']}")
    
    if buy_result['status'] == 'executed':
        logger.info(f"Transaction hash: {buy_result['transaction_hash']}")
        logger.info(f"SOL amount: {buy_result['sol_amount']}")
        logger.info(f"Execution latency: {buy_result['execution_latency_ms']}ms")
        
        # Test transaction monitoring
        if buy_result.get('transaction_hash'):
            monitor_result = await executor.monitor_transaction(buy_result['transaction_hash'])
            logger.info(f"Transaction monitoring: {monitor_result['status']}")
    
    # Test sell execution
    logger.info("Testing sell execution...")
    sell_result = await executor.execute_sell_signal(test_signal)
    logger.info(f"Sell result: {sell_result['status']}")
    
    # Get performance metrics
    metrics = executor.get_performance_metrics()
    logger.info(f"Performance metrics: {metrics}")
    
    return buy_result['status'] in ['executed', 'skipped'] and sell_result['status'] in ['executed', 'skipped']

async def test_integration():
    """Test full integration"""
    logger.info("Testing full integration...")
    
    # Test configuration loading
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    if not config_manager.validate_config(config):
        logger.warning("Configuration validation failed, but continuing with tests...")
    
    # Test components
    validator_test = await test_liquidity_validator()
    executor_test = await test_pumpswap_executor()
    
    logger.info(f"Validator test passed: {validator_test}")
    logger.info(f"Executor test passed: {executor_test}")
    
    return validator_test and executor_test

async def main():
    """Main test function"""
    logger.info("Starting PumpSwap Integration Layer tests...")
    
    try:
        success = await test_integration()
        
        if success:
            logger.info("✅ All tests passed!")
            return 0
        else:
            logger.error("❌ Some tests failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)