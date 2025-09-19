"""
Test script for Q50 Signal Integration Foundation.

This script tests the Q50SignalLoader and RegimeDetector implementations
to ensure they work correctly with the existing system.
"""

import asyncio
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pickle

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.regime_detector import RegimeDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_q50_data():
    """Create mock Q50 data for testing if the real file doesn't exist."""
    logger.info("Creating mock Q50 data for testing")
    
    # Create date range
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='1H')
    
    # Generate synthetic Q50 data
    np.random.seed(42)  # For reproducible results
    n_samples = len(dates)
    
    # Generate correlated features
    vol_raw = np.random.exponential(0.1, n_samples)
    vol_risk = vol_raw * np.random.uniform(0.5, 2.0, n_samples)
    
    # Generate Q50 values with some correlation to volatility
    q50 = np.random.normal(0, 0.1, n_samples) + (vol_risk - vol_risk.mean()) * 0.5
    q10 = q50 - np.random.exponential(0.05, n_samples)
    q90 = q50 + np.random.exponential(0.05, n_samples)
    
    # Generate probability and quality indicators
    prob_up = 0.5 + (q50 * 2)  # Probability correlated with Q50
    prob_up = np.clip(prob_up, 0.1, 0.9)
    
    economically_significant = np.abs(q50) > 0.05
    high_quality = vol_risk < np.percentile(vol_risk, 80)
    tradeable = economically_significant & high_quality
    
    # Create DataFrame
    data = pd.DataFrame({
        'q10': q10,
        'q50': q50,
        'q90': q90,
        'vol_raw': vol_raw,
        'vol_risk': vol_risk,
        'prob_up': prob_up,
        'economically_significant': economically_significant,
        'high_quality': high_quality,
        'tradeable': tradeable
    }, index=dates)
    
    return data


async def test_q50_signal_loader():
    """Test the Q50SignalLoader implementation."""
    logger.info("Testing Q50SignalLoader...")
    
    # Configuration
    config = {
        'q50': {
            'features_path': 'data3/macro_features.pkl',
            'signal_tolerance_minutes': 5,
            'required_columns': [
                'q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
                'prob_up', 'economically_significant', 'high_quality', 'tradeable'
            ]
        },
        'database': {
            'url': 'sqlite:///test_nautilus.db',
            'pool_size': 5,
            'echo': False,
            'timeout': 30
        }
    }
    
    # Create mock data if real file doesn't exist
    features_path = Path(config['q50']['features_path'])
    if not features_path.exists():
        logger.info("Real features file not found, creating mock data")
        features_path.parent.mkdir(parents=True, exist_ok=True)
        mock_data = create_mock_q50_data()
        
        with open(features_path, 'wb') as f:
            pickle.dump(mock_data, f)
        
        logger.info(f"Created mock data with {len(mock_data)} samples")
    
    # Initialize signal loader
    signal_loader = Q50SignalLoader(config)
    
    try:
        # Test signal loading
        success = await signal_loader.load_signals()
        assert success, "Failed to load signals"
        logger.info("✓ Signal loading successful")
        
        # Test signal statistics
        stats = signal_loader.get_signal_statistics()
        logger.info(f"✓ Signal statistics: {stats['total_signals']} signals loaded")
        
        # Test signal retrieval
        test_timestamp = pd.Timestamp('2024-06-15 12:00:00')
        signal = await signal_loader.get_signal_for_timestamp(test_timestamp)
        
        if signal:
            logger.info(f"✓ Retrieved signal for {test_timestamp}: q50={signal['q50']:.4f}")
        else:
            logger.warning("No signal found for test timestamp")
        
        # Test latest signal
        latest_signal = signal_loader.get_latest_signal()
        if latest_signal:
            logger.info(f"✓ Latest signal: {latest_signal['timestamp']}, q50={latest_signal['q50']:.4f}")
        
        # Test health check
        health = signal_loader.health_check()
        logger.info(f"✓ Health check: {health}")
        
        return signal_loader
        
    except Exception as e:
        logger.error(f"Error testing Q50SignalLoader: {e}")
        raise
    finally:
        await signal_loader.close_async()


def test_regime_detector():
    """Test the RegimeDetector implementation."""
    logger.info("Testing RegimeDetector...")
    
    # Configuration
    config = {
        'regime_detection': {
            'vol_risk_percentiles': {
                'low': 0.30,
                'high': 0.70,
                'extreme': 0.90
            },
            'regime_multipliers': {
                'low_variance': 0.7,
                'medium_variance': 1.0,
                'high_variance': 1.4,
                'extreme_variance': 1.8
            }
        }
    }
    
    # Initialize regime detector
    regime_detector = RegimeDetector(config)
    
    try:
        # Test with different volatility scenarios
        test_signals = [
            {'vol_risk': 0.1, 'q50': 0.05, 'vol_raw': 0.08, 'prob_up': 0.6},  # Low volatility
            {'vol_risk': 0.5, 'q50': -0.03, 'vol_raw': 0.12, 'prob_up': 0.4},  # Medium volatility
            {'vol_risk': 0.8, 'q50': 0.08, 'vol_raw': 0.15, 'prob_up': 0.7},  # High volatility
            {'vol_risk': 0.95, 'q50': -0.12, 'vol_raw': 0.25, 'prob_up': 0.3},  # Extreme volatility
        ]
        
        for i, signal_data in enumerate(test_signals):
            # Classify regime
            regime_info = regime_detector.classify_regime(signal_data)
            logger.info(f"✓ Test signal {i+1}: regime={regime_info['regime']}, "
                       f"vol_risk={signal_data['vol_risk']}, "
                       f"multiplier={regime_info['regime_multiplier']}")
            
            # Apply regime adjustments
            adjusted_signal = regime_detector.apply_regime_adjustments(signal_data, regime_info)
            logger.info(f"  Adjusted tradeable: {adjusted_signal.get('regime_adjusted_tradeable', False)}")
        
        # Test regime statistics
        stats = regime_detector.get_regime_statistics()
        logger.info(f"✓ Regime statistics: {stats}")
        
        # Test with historical data
        historical_vol_risk = np.random.exponential(0.3, 1000)  # Generate test history
        regime_detector.load_historical_data(historical_vol_risk.tolist())
        
        updated_stats = regime_detector.get_regime_statistics()
        logger.info(f"✓ Updated statistics with history: {updated_stats['total_observations']} observations")
        
        return regime_detector
        
    except Exception as e:
        logger.error(f"Error testing RegimeDetector: {e}")
        raise


async def test_integration():
    """Test integration between Q50SignalLoader and RegimeDetector."""
    logger.info("Testing Q50 and Regime integration...")
    
    # Configuration
    config = {
        'q50': {
            'features_path': 'data3/macro_features.pkl',
            'signal_tolerance_minutes': 5,
        },
        'database': {
            'url': 'sqlite:///test_nautilus.db',
            'pool_size': 5,
            'echo': False,
            'timeout': 30
        },
        'regime_detection': {
            'vol_risk_percentiles': {
                'low': 0.30,
                'high': 0.70,
                'extreme': 0.90
            },
            'regime_multipliers': {
                'low_variance': 0.7,
                'medium_variance': 1.0,
                'high_variance': 1.4,
                'extreme_variance': 1.8
            }
        }
    }
    
    # Initialize components
    signal_loader = Q50SignalLoader(config)
    regime_detector = RegimeDetector(config)
    
    try:
        # Load signals
        success = await signal_loader.load_signals()
        assert success, "Failed to load signals"
        
        # Test integration with multiple signals
        test_timestamps = [
            pd.Timestamp('2024-03-15 10:00:00'),
            pd.Timestamp('2024-06-15 14:30:00'),
            pd.Timestamp('2024-09-15 16:45:00'),
        ]
        
        for timestamp in test_timestamps:
            # Get signal
            signal = await signal_loader.get_signal_for_timestamp(timestamp)
            
            if signal:
                # Classify regime
                regime_info = regime_detector.classify_regime(signal)
                
                # Apply adjustments
                adjusted_signal = regime_detector.apply_regime_adjustments(signal, regime_info)
                
                logger.info(f"✓ Integrated test for {timestamp}:")
                logger.info(f"  Original q50: {signal['q50']:.4f}, tradeable: {signal.get('tradeable', False)}")
                logger.info(f"  Regime: {regime_info['regime']}, multiplier: {regime_info['regime_multiplier']}")
                logger.info(f"  Adjusted tradeable: {adjusted_signal.get('regime_adjusted_tradeable', False)}")
            else:
                logger.warning(f"No signal found for {timestamp}")
        
        logger.info("✓ Integration test completed successfully")
        
    except Exception as e:
        logger.error(f"Error in integration test: {e}")
        raise
    finally:
        await signal_loader.close_async()


async def main():
    """Run all tests."""
    logger.info("Starting Q50 Signal Integration Foundation tests...")
    
    try:
        # Test individual components
        await test_q50_signal_loader()
        test_regime_detector()
        
        # Test integration
        await test_integration()
        
        logger.info("🎉 All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Tests failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())