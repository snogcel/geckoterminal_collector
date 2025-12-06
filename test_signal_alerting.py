"""
Test signal alerting with both standard and contextual loggers.
"""

import logging
from gecko_terminal_collector.utils.signal_alerting import setup_signal_logging, TRADE_SIGNAL
from gecko_terminal_collector.utils.structured_logging import ContextualLogger, LogContext

def test_standard_logger():
    """Test with standard Python logger."""
    print("=" * 80)
    print("Testing with Standard Logger")
    print("=" * 80)
    
    # Create standard logger
    logger = logging.getLogger("test_standard")
    logger.setLevel(logging.DEBUG)
    
    # Setup signal alerting
    config = {
        'use_colors': True,
        'use_emojis': True,
        'enable_file_alerts': False
    }
    alerter = setup_signal_logging(logger, config)
    
    # Test logging
    logger.info("This is a regular INFO message")
    logger.trade_signal("This is a TRADE_SIGNAL message - should be highlighted!")
    logger.warning("This is a WARNING message")
    
    print("\n✓ Standard logger test passed\n")


def test_contextual_logger():
    """Test with ContextualLogger."""
    print("=" * 80)
    print("Testing with ContextualLogger")
    print("=" * 80)
    
    # Create contextual logger
    context = LogContext(
        collector_type="test_collector",
        operation="test_operation"
    )
    logger = ContextualLogger("test_contextual", context)
    
    # Setup signal alerting
    config = {
        'use_colors': True,
        'use_emojis': True,
        'enable_file_alerts': False
    }
    alerter = setup_signal_logging(logger, config)
    
    # Test logging
    logger.info("This is a regular INFO message")
    logger.trade_signal("This is a TRADE_SIGNAL message - should be highlighted!")
    logger.warning("This is a WARNING message")
    
    print("\n✓ ContextualLogger test passed\n")


def test_signal_alerter():
    """Test SignalAlerter functionality."""
    print("=" * 80)
    print("Testing SignalAlerter")
    print("=" * 80)
    
    from gecko_terminal_collector.utils.signal_alerting import SignalAlerter
    
    config = {
        'enable_file_alerts': True,
        'alerts_dir': 'test_alerts',
        'min_signal_score': 60.0
    }
    
    alerter = SignalAlerter(config)
    
    # Test alert
    signal_data = {
        'signal_score': 85.2,
        'volume_trend': 'spike',
        'liquidity_trend': 'growing',
        'momentum_indicator': 45.3,
        'activity_score': 78.5,
        'volatility_score': 65.0,
        'dex_id': 'pumpswap',
        'network': 'solana'
    }
    
    message = "Test signal alert"
    alerter.alert("test_pool_123", signal_data, message)
    
    print("\n✓ SignalAlerter test passed")
    print(f"✓ Alert file created in: {config['alerts_dir']}/")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SIGNAL ALERTING TESTS")
    print("=" * 80)
    print()
    
    try:
        test_standard_logger()
        test_contextual_logger()
        test_signal_alerter()
        
        print("=" * 80)
        print("✓ ALL TESTS PASSED")
        print("=" * 80)
        print()
        print("The signal alerting system is working correctly!")
        print("You can now use it with your collector.")
        
    except Exception as e:
        print("=" * 80)
        print("✗ TEST FAILED")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
