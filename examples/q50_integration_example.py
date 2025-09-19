"""
Example usage of Q50 Signal Integration Foundation.

This example demonstrates how to use the Q50SignalLoader and RegimeDetector
components together for enhanced signal processing in the NautilusTrader POC.
"""

import asyncio
import logging
import sys
from pathlib import Path
import pandas as pd

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.regime_detector import RegimeDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demonstrate_q50_integration():
    """Demonstrate Q50 signal integration with regime detection."""
    
    # Configuration matching the config.yaml structure
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
            'url': 'postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector',
            'pool_size': 10,
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
    logger.info("Initializing Q50 Signal Integration components...")
    signal_loader = Q50SignalLoader(config)
    regime_detector = RegimeDetector(config)
    
    try:
        # Load Q50 signals
        logger.info("Loading Q50 signals...")
        success = await signal_loader.load_signals()
        
        if not success:
            logger.error("Failed to load Q50 signals")
            return
        
        # Get signal statistics
        stats = signal_loader.get_signal_statistics()
        logger.info(f"Loaded {stats['total_signals']} Q50 signals")
        logger.info(f"Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
        logger.info(f"Tradeable signals: {stats['tradeable_signals']}")
        
        # Demonstrate signal processing workflow
        logger.info("\n" + "="*60)
        logger.info("SIGNAL PROCESSING WORKFLOW DEMONSTRATION")
        logger.info("="*60)
        
        # Get the latest signal for demonstration
        latest_signal = signal_loader.get_latest_signal()
        
        if latest_signal:
            logger.info(f"\nProcessing latest signal from: {latest_signal['timestamp']}")
            
            # Step 1: Display original signal
            logger.info("\n1. Original Q50 Signal:")
            logger.info(f"   q50 value: {latest_signal['q50']:.4f}")
            logger.info(f"   vol_risk: {latest_signal['vol_risk']:.4f}")
            logger.info(f"   prob_up: {latest_signal['prob_up']:.4f}")
            logger.info(f"   economically_significant: {latest_signal['economically_significant']}")
            logger.info(f"   tradeable: {latest_signal['tradeable']}")
            
            # Step 2: Classify regime
            logger.info("\n2. Regime Classification:")
            regime_info = regime_detector.classify_regime(latest_signal)
            logger.info(f"   Regime: {regime_info['regime']}")
            logger.info(f"   Vol risk percentile: {regime_info['vol_risk_percentile']:.1f}%")
            logger.info(f"   Threshold adjustment: {regime_info['threshold_adjustment']:.1%}")
            logger.info(f"   Regime multiplier: {regime_info['regime_multiplier']:.2f}")
            logger.info(f"   Enhanced info ratio: {regime_info.get('enhanced_info_ratio', 0):.4f}")
            
            # Step 3: Apply regime adjustments
            logger.info("\n3. Regime-Adjusted Signal:")
            adjusted_signal = regime_detector.apply_regime_adjustments(latest_signal, regime_info)
            logger.info(f"   Regime-adjusted tradeable: {adjusted_signal.get('regime_adjusted_tradeable', False)}")
            logger.info(f"   Regime-adjusted signal strength: {adjusted_signal.get('regime_adjusted_signal_strength', 0):.4f}")
            logger.info(f"   Regime confidence: {regime_info.get('regime_confidence', 0):.2f}")
            
            # Step 4: Trading decision logic
            logger.info("\n4. Trading Decision:")
            q50_value = latest_signal['q50']
            is_tradeable = adjusted_signal.get('regime_adjusted_tradeable', False)
            
            if is_tradeable:
                if q50_value > 0:
                    decision = "BUY"
                    logger.info(f"   Decision: {decision} (positive Q50 signal)")
                elif q50_value < 0:
                    decision = "SELL"
                    logger.info(f"   Decision: {decision} (negative Q50 signal)")
                else:
                    decision = "HOLD"
                    logger.info(f"   Decision: {decision} (neutral Q50 signal)")
                
                # Calculate position size suggestion
                base_size = 0.1 / max(latest_signal['vol_risk'] * 1000, 0.1)
                signal_strength = abs(q50_value) * regime_info['regime_multiplier']
                suggested_position = min(base_size * signal_strength, 0.5)
                
                logger.info(f"   Suggested position size: {suggested_position:.1%} of capital")
            else:
                decision = "HOLD"
                logger.info(f"   Decision: {decision} (signal not tradeable after regime adjustment)")
        
        # Demonstrate historical analysis
        logger.info("\n" + "="*60)
        logger.info("HISTORICAL REGIME ANALYSIS")
        logger.info("="*60)
        
        # Get regime statistics
        regime_stats = regime_detector.get_regime_statistics()
        if regime_stats.get('status') != 'no_history':
            logger.info(f"\nRegime distribution over {regime_stats['total_observations']} observations:")
            for regime, percentage in regime_stats['regime_distribution'].items():
                logger.info(f"   {regime}: {percentage:.1%}")
            
            logger.info(f"\nVolatility risk statistics:")
            vol_stats = regime_stats['vol_risk_stats']
            logger.info(f"   Mean: {vol_stats['mean']:.4f}")
            logger.info(f"   Std: {vol_stats['std']:.4f}")
            logger.info(f"   Range: {vol_stats['min']:.4f} - {vol_stats['max']:.4f}")
        
        # Demonstrate batch processing
        logger.info("\n" + "="*60)
        logger.info("BATCH SIGNAL PROCESSING EXAMPLE")
        logger.info("="*60)
        
        # Get recent signals for batch processing
        end_time = pd.Timestamp.now()
        start_time = end_time - pd.Timedelta(hours=24)  # Last 24 hours
        
        recent_signals = signal_loader.get_signals_in_range(start_time, end_time)
        
        if not recent_signals.empty:
            logger.info(f"\nProcessing {len(recent_signals)} recent signals...")
            
            # Process each signal through the regime detector
            regime_results = []
            for timestamp, signal_row in recent_signals.iterrows():
                signal_dict = signal_row.to_dict()
                signal_dict['timestamp'] = timestamp
                
                regime_info = regime_detector.classify_regime(signal_dict)
                adjusted_signal = regime_detector.apply_regime_adjustments(signal_dict, regime_info)
                
                regime_results.append({
                    'timestamp': timestamp,
                    'regime': regime_info['regime'],
                    'q50': signal_dict['q50'],
                    'original_tradeable': signal_dict.get('tradeable', False),
                    'regime_adjusted_tradeable': adjusted_signal.get('regime_adjusted_tradeable', False)
                })
            
            # Analyze batch results
            total_signals = len(regime_results)
            original_tradeable = sum(1 for r in regime_results if r['original_tradeable'])
            regime_adjusted_tradeable = sum(1 for r in regime_results if r['regime_adjusted_tradeable'])
            
            logger.info(f"   Original tradeable signals: {original_tradeable}/{total_signals} ({original_tradeable/total_signals:.1%})")
            logger.info(f"   Regime-adjusted tradeable: {regime_adjusted_tradeable}/{total_signals} ({regime_adjusted_tradeable/total_signals:.1%})")
            
            # Regime distribution in recent signals
            regime_counts = {}
            for result in regime_results:
                regime = result['regime']
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            logger.info(f"   Recent regime distribution:")
            for regime, count in regime_counts.items():
                logger.info(f"     {regime}: {count}/{total_signals} ({count/total_signals:.1%})")
        
        logger.info("\n" + "="*60)
        logger.info("DEMONSTRATION COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        raise
    finally:
        # Cleanup
        await signal_loader.close_async()


async def main():
    """Run the Q50 integration demonstration."""
    logger.info("Starting Q50 Signal Integration Foundation demonstration...")
    
    try:
        await demonstrate_q50_integration()
        logger.info("🎉 Demonstration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Demonstration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())