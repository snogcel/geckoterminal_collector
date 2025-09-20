"""
Test Position Sizing and Risk Management Components

This script tests the KellyPositionSizer and RiskManager implementations
to verify they work according to the requirements.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nautilus_poc.position_sizer import KellyPositionSizer, PositionSizeResult
from nautilus_poc.risk_manager import RiskManager, RiskLevel, CircuitBreakerState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_kelly_position_sizer():
    """Test KellyPositionSizer functionality"""
    logger.info("Testing KellyPositionSizer...")
    
    # Test configuration
    config = {
        'pumpswap': {
            'base_position_size': 0.1,
            'max_position_size': 0.5,
            'min_liquidity_sol': 10.0,
            'max_price_impact_percent': 10.0
        },
        'regime_detection': {
            'effective_info_ratio_threshold': 1.0
        }
    }
    
    # Initialize position sizer
    position_sizer = KellyPositionSizer(config)
    
    # Test signal data
    test_signals = [
        {
            'q50': 0.3,
            'vol_risk': 0.05,
            'enhanced_info_ratio': 1.5,
            'regime': 'low_variance',
            'regime_multiplier': 0.7,
            'tradeable': True,
            'economically_significant': True,
            'high_quality': True
        },
        {
            'q50': -0.2,
            'vol_risk': 0.15,
            'enhanced_info_ratio': 2.0,
            'regime': 'high_variance',
            'regime_multiplier': 1.4,
            'tradeable': True,
            'economically_significant': True,
            'high_quality': True
        },
        {
            'q50': 0.1,
            'vol_risk': 0.001,  # Very low variance
            'enhanced_info_ratio': 0.8,
            'regime': 'extreme_variance',
            'regime_multiplier': 1.8,
            'tradeable': True,
            'economically_significant': False,
            'high_quality': False
        }
    ]
    
    # Test pool data
    pool_data = {
        'reserve_in_usd': 5000,  # $5000 pool = ~50 SOL
        'current_price': 0.1
    }
    
    current_balance = 2.0  # 2 SOL balance
    
    for i, signal in enumerate(test_signals):
        logger.info(f"\n--- Test Signal {i+1} ---")
        logger.info(f"Q50: {signal['q50']}, Vol Risk: {signal['vol_risk']}, "
                   f"Regime: {signal['regime']}")
        
        # Validate signal data
        is_valid = position_sizer.validate_signal_data(signal)
        logger.info(f"Signal validation: {is_valid}")
        
        if is_valid:
            # Calculate position size
            result = position_sizer.calculate_position_size(
                signal, pool_data, current_balance
            )
            
            logger.info(f"Position Size Result:")
            logger.info(f"  Final Size: {result.final_size:.4f} SOL")
            logger.info(f"  Base Size: {result.base_size:.4f} SOL")
            logger.info(f"  Signal Multiplier: {result.signal_multiplier:.2f}x")
            logger.info(f"  Regime Multiplier: {result.regime_multiplier:.2f}x")
            logger.info(f"  Constraints Applied: {result.constraints_applied}")
            logger.info(f"  Reasoning: {result.reasoning}")
            
            # Get summary
            summary = position_sizer.get_position_size_summary(result)
            logger.info(f"  Summary: {summary}")
    
    logger.info("KellyPositionSizer tests completed successfully!")

def test_risk_manager():
    """Test RiskManager functionality"""
    logger.info("\nTesting RiskManager...")
    
    # Test configuration
    config = {
        'pumpswap': {
            'max_position_size': 0.5,
            'stop_loss_percent': 20.0,
            'take_profit_percent': 50.0,
            'position_timeout_hours': 24,
            'min_balance_sol': 0.1
        },
        'error_handling': {
            'failure_threshold': 3,
            'recovery_timeout': 60,  # 1 minute for testing
            'half_open_max_attempts': 2
        }
    }
    
    # Initialize risk manager
    risk_manager = RiskManager(config)
    
    # Test trade validation
    logger.info("\n--- Testing Trade Validation ---")
    
    test_cases = [
        {
            'position_size': 0.2,
            'signal_data': {
                'q50': 0.3,
                'vol_risk': 0.05,
                'tradeable': True,
                'economically_significant': True,
                'high_quality': True
            },
            'current_balance': 1.0,
            'description': 'Valid trade'
        },
        {
            'position_size': 0.8,  # Too large
            'signal_data': {
                'q50': 0.2,
                'vol_risk': 0.1,
                'tradeable': True,
                'economically_significant': True,
                'high_quality': True
            },
            'current_balance': 1.0,
            'description': 'Position too large'
        },
        {
            'position_size': 0.2,
            'signal_data': {
                'q50': 0.1,
                'vol_risk': 0.05,
                'tradeable': False,  # Not tradeable
                'economically_significant': False,
                'high_quality': False
            },
            'current_balance': 1.0,
            'description': 'Non-tradeable signal'
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"\nTest Case {i+1}: {test_case['description']}")
        
        validation_result = risk_manager.validate_trade_full(
            test_case['position_size'],
            test_case['signal_data'],
            test_case['current_balance']
        )
        
        logger.info(f"  Valid: {validation_result.is_valid}")
        logger.info(f"  Risk Level: {validation_result.risk_level.value}")
        logger.info(f"  Action: {validation_result.recommended_action}")
        logger.info(f"  Reasons: {validation_result.reasons}")
        logger.info(f"  Warnings: {validation_result.warnings}")
    
    # Test circuit breaker
    logger.info("\n--- Testing Circuit Breaker ---")
    
    # Test normal operation
    can_trade = risk_manager.can_execute_trade()
    logger.info(f"Can execute trade (initial): {can_trade}")
    
    status = risk_manager.get_circuit_breaker_status()
    logger.info(f"Circuit breaker status: {status.state.value}, failures: {status.failure_count}")
    
    # Simulate failures
    logger.info("Simulating trade failures...")
    for i in range(4):  # Exceed failure threshold
        error_data = {
            'error_type': 'NetworkError',
            'error_message': f'Simulated failure {i+1}',
            'timestamp': datetime.now()
        }
        risk_manager.record_trade_failure(error_data)
        
        status = risk_manager.get_circuit_breaker_status()
        can_trade = risk_manager.can_execute_trade()
        logger.info(f"After failure {i+1}: state={status.state.value}, can_trade={can_trade}")
    
    # Test position risk assessment
    logger.info("\n--- Testing Position Risk Assessment ---")
    
    position_risk = risk_manager.assess_position_risk(
        mint_address="test_token",
        current_price=0.08,  # 20% loss
        entry_price=0.10,
        position_size=100,
        entry_time=datetime.now() - timedelta(hours=2)
    )
    
    logger.info(f"Position Risk Assessment:")
    logger.info(f"  Current Value: {position_risk.current_value_sol:.4f} SOL")
    logger.info(f"  Unrealized P&L: {position_risk.unrealized_pnl_percent:.2f}%")
    logger.info(f"  Time Held: {position_risk.time_held_hours:.1f} hours")
    logger.info(f"  Stop Loss Triggered: {position_risk.stop_loss_triggered}")
    logger.info(f"  Risk Level: {position_risk.risk_level.value}")
    
    should_close, reason = risk_manager.should_close_position(position_risk)
    logger.info(f"  Should Close: {should_close}, Reason: {reason}")
    
    # Test wallet balance validation
    logger.info("\n--- Testing Wallet Balance Validation ---")
    
    balance_validation = risk_manager.validate_wallet_balance(0.05)  # Low balance
    logger.info(f"Balance validation (0.05 SOL):")
    logger.info(f"  Sufficient: {balance_validation['is_sufficient']}")
    logger.info(f"  Warnings: {balance_validation['warnings']}")
    logger.info(f"  Recommendations: {balance_validation['recommendations']}")
    
    # Get risk summary
    logger.info("\n--- Risk Management Summary ---")
    risk_summary = risk_manager.get_risk_summary()
    logger.info(f"Risk Summary: {risk_summary}")
    
    logger.info("RiskManager tests completed successfully!")

def main():
    """Run all tests"""
    logger.info("Starting Position Sizing and Risk Management Tests")
    logger.info("=" * 60)
    
    try:
        # Test position sizer
        test_kelly_position_sizer()
        
        # Test risk manager
        test_risk_manager()
        
        logger.info("\n" + "=" * 60)
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)