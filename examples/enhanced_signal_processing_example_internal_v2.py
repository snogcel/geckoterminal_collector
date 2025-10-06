"""
Enhanced Signal Processing with PumpSwap Integration Example

This example demonstrates how to use the PumpSwapSignalAnalyzer and
AdaptiveThresholdCalculator components to enhance Q50 signals with
PumpSwap pool data and calculate adaptive thresholds.
"""

import asyncio
import pandas as pd
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the enhanced signal processing components
from nautilus_poc.pumpswap_signal_analyzer import PumpSwapSignalAnalyzer, SignalQuality
from nautilus_poc.adaptive_threshold_calculator_internal import (
    AdaptiveThresholdCalculator, 
    ThresholdType,
    EconomicSignificanceResult
)
from nautilus_poc.config import NautilusPOCConfig, Q50Config, PumpSwapConfig, SolanaConfig, NautilusConfig
from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.liquidity_validator_internal import LiquidityValidator

def create_example_config() -> NautilusPOCConfig:
    """Create example configuration for enhanced signal processing"""
    return NautilusPOCConfig(
        environment='testnet',
        environments={
            "solana": SolanaConfig,
            "pumpswap": PumpSwapConfig,
            "security": None
        },
        q50=Q50Config(
            features_path='data3/macro_features.pkl',
            signal_tolerance_minutes=5,
            required_columns=[
                'q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
                'prob_up', 'economically_significant', 'high_quality', 'tradeable'
            ]
        ),
        #pumpswap=PumpSwapConfig(
            #payer_public_key='YOUR_SOLANA_PUBLIC_KEY',
            #private_key_path='path/to/your/private/key.json',
        #    max_slippage_percent=5.0,
        #    base_position_size=0.1,
        #    max_position_size=0.5,
        #    min_liquidity_sol=10.0,
        #    max_price_impact_percent=10.0,
        #    realistic_transaction_cost=0.01
            #stop_loss_percent=20.0,
            #position_timeout_hours=24
        #),
        #solana=SolanaConfig(
        #    network='testnet',
        #    rpc_endpoint='https://api.testnet.solana.com',
        #    commitment='confirmed',
        #    cluster='test'
        #),
        nautilus=NautilusConfig(
            instance_id='ENHANCED-SIGNAL-001',
            log_level='INFO',
            cache_database_path='enhanced_signal_cache.db'
        ),
        monitoring={
            'realistic_transaction_cost': 0.0005,  # 5 bps
            'min_expected_value': 0.001,  # 10 bps minimum
            'min_volume_24h': 1000,  # $1k minimum daily volume
            'enable_performance_tracking': True
        },
        error_handling={
            'max_retries': 3,
            'retry_delay_base': 1.0,
            'circuit_breaker_threshold': 5
        },
        regime_detection={
            'liquidity_weight': 0.3,
            'execution_weight': 0.2,
            'quality_threshold': 0.6,
            'low_variance_percentile': 0.30,
            'high_variance_percentile': 0.70,
            'extreme_variance_percentile': 0.90,
            'low_variance_adjustment': -0.30,
            'medium_variance_adjustment': 0.0,
            'high_variance_adjustment': 0.40,
            'extreme_variance_adjustment': 0.80,
            'price_impact_penalty_factor': 2.0,
            'optimal_liquidity_sol': 100.0
        }
    )

def create_sample_signals() -> List[Dict[str, Any]]:
    """Create sample Q50 signals for demonstration"""
    base_time = pd.Timestamp.now()
    
    return [
        {
            'timestamp': base_time,
            'q10': -0.02,
            'q50': 0.05,  # Strong positive signal
            'q90': 0.12,
            'vol_raw': 0.15,
            'vol_risk': 0.08,  # Medium variance
            'prob_up': 0.65,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True,
            'regime': 'medium_variance',
            'vol_risk_percentile': 0.45,
            'threshold_adjustment': 0.0,
            'regime_multiplier': 1.0
        },
        {
            'timestamp': base_time + pd.Timedelta(minutes=5),
            'q10': -0.08,
            'q50': -0.03,  # Negative signal
            'q90': 0.02,
            'vol_raw': 0.25,
            'vol_risk': 0.18,  # High variance
            'prob_up': 0.35,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True,
            'regime': 'high_variance',
            'vol_risk_percentile': 0.75,
            'threshold_adjustment': 0.40,
            'regime_multiplier': 1.4
        },
        {
            'timestamp': base_time + pd.Timedelta(minutes=10),
            'q10': -0.01,
            'q50': 0.02,  # Weak signal
            'q90': 0.05,
            'vol_raw': 0.08,
            'vol_risk': 0.04,  # Low variance
            'prob_up': 0.58,
            'economically_significant': False,
            'high_quality': False,
            'tradeable': False,
            'regime': 'low_variance',
            'vol_risk_percentile': 0.25,
            'threshold_adjustment': -0.30,
            'regime_multiplier': 0.7
        }
    ]

def create_sample_pool_data() -> List[Dict[str, Any]]:
    """Create sample PumpSwap pool data"""
    return [
        {
            'mint_address': 'So11111111111111111111111111111111111111112',
            'reserve_in_usd': 100000,  # $100k liquidity
            'reserve_sol': 1000,
            'reserve_token': 1000000,
            'price': 0.001,
            'volume_24h': 25000  # $25k daily volume
        },
        {
            'mint_address': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
            'reserve_in_usd': 25000,  # $25k liquidity
            'reserve_sol': 250,
            'reserve_token': 250000,
            'price': 0.001,
            'volume_24h': 8000  # $8k daily volume
        },
        {
            'mint_address': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'reserve_in_usd': 5000,  # $5k liquidity (low)
            'reserve_sol': 50,
            'reserve_token': 50000,
            'price': 0.001,
            'volume_24h': 500  # $500 daily volume (very low)
        }
    ]

async def demonstrate_signal_analysis():
    """Demonstrate enhanced signal analysis with PumpSwap integration"""
    print("🔍 Enhanced Signal Analysis with PumpSwap Integration")
    print("=" * 60)
    
    # Create configuration and components
    config = create_example_config()
    
    # Initialize components (in real usage, these would be properly configured)
    # Convert config to dictionary format expected by Q50SignalLoader
    config_dict = {
        'q50': {
            'features_path': config.q50.features_path,
            'signal_tolerance_minutes': config.q50.signal_tolerance_minutes
        },
        'database': {
            'url': 'sqlite:///test.db'  # Mock database for example
        }
    }
    signal_loader = Q50SignalLoader(config_dict)
    liquidity_validator = LiquidityValidator(config)
    
    # Create analyzer and calculator
    analyzer = PumpSwapSignalAnalyzer(config, signal_loader, liquidity_validator)
    calculator = AdaptiveThresholdCalculator(config)
    
    # Get sample data
    signals = create_sample_signals()
    pool_data_list = create_sample_pool_data()
    mint_addresses = [pool['mint_address'] for pool in pool_data_list]
    
    print(f"Analyzing {len(signals)} signals with PumpSwap integration...\n")
    
    # Analyze each signal
    for i, (signal, mint_address, pool_data) in enumerate(zip(signals, mint_addresses, pool_data_list)):
        print(f"📊 Signal {i+1}: {mint_address[:8]}...")
        print(f"   Q50 Value: {signal['q50']:+.4f}")
        print(f"   Regime: {signal['regime']}")
        print(f"   Pool Liquidity: ${pool_data['reserve_in_usd']:,}")
        print(f"   24h Volume: ${pool_data['volume_24h']:,}")
        
        # Mock PumpSwap SDK responses for this example
        analyzer.pumpswap_sdk.get_pair_address = lambda addr: f"pair_{addr[:8]}"
        analyzer.pumpswap_sdk.get_pool_data = lambda addr: pool_data
        
        # Analyze signal
        enhanced_signal = await analyzer.analyze_signal(signal, mint_address)
        
        # Calculate economic significance
        economic_result = calculator.calculate_economic_significance(
            signal, pool_data, estimated_position_size=0.1
        )
        
        # Calculate adaptive threshold
        threshold_result = calculator.calculate_adaptive_threshold(
            signal, pool_data, ThresholdType.ECONOMIC_SIGNIFICANCE
        )
        
        # Display results
        print(f"   📈 Enhanced Analysis:")
        print(f"      Signal Quality: {enhanced_signal.signal_quality.value}")
        print(f"      Final Score: {enhanced_signal.final_signal_score:.4f}")
        print(f"      Execution Feasible: {enhanced_signal.execution_feasible}")
        print(f"      Liquidity Adjusted Strength: {enhanced_signal.liquidity_adjusted_strength:.4f}")
        print(f"      Recommended Position: {enhanced_signal.recommended_position_size:.4f} SOL")
        
        print(f"   💰 Economic Significance:")
        print(f"      Expected Value: {economic_result.net_expected_value:+.6f}")
        print(f"      Is Significant: {economic_result.is_economically_significant}")
        print(f"      Total Costs: {economic_result.total_costs:.6f}")
        print(f"      Price Impact Cost: {economic_result.price_impact_costs:.6f}")
        
        print(f"   🎯 Adaptive Threshold:")
        print(f"      Base Threshold: {threshold_result.base_threshold:.6f}")
        print(f"      Final Threshold: {threshold_result.final_threshold:.6f}")
        print(f"      Above Threshold: {threshold_result.is_above_threshold}")
        print(f"      Liquidity Adjustment: {threshold_result.liquidity_adjustment:+.3f}")
        print(f"      Price Impact Adjustment: {threshold_result.price_impact_adjustment:+.3f}")
        
        print()

async def demonstrate_batch_analysis():
    """Demonstrate batch signal analysis for efficiency"""
    print("⚡ Batch Signal Analysis")
    print("=" * 30)
    
    config = create_example_config()
    config_dict = {
        'q50': {
            'features_path': config.q50.features_path,
            'signal_tolerance_minutes': config.q50.signal_tolerance_minutes
        },
        'database': {
            'url': 'sqlite:///test.db'  # Mock database for example
        }
    }
    signal_loader = Q50SignalLoader(config_dict)
    liquidity_validator = LiquidityValidator(config)
    analyzer = PumpSwapSignalAnalyzer(config, signal_loader, liquidity_validator)
    
    # Create batch data
    signals = create_sample_signals()
    mint_addresses = [pool['mint_address'] for pool in create_sample_pool_data()]
    
    # Prepare batch input
    batch_signals = list(zip(signals, mint_addresses))
    
    print(f"Processing batch of {len(batch_signals)} signals...")
    
    # Mock SDK for batch processing
    pool_data_map = {addr: pool for addr, pool in zip(mint_addresses, create_sample_pool_data())}
    
    async def mock_get_pair_address(addr):
        return f"pair_{addr[:8]}"
    
    async def mock_get_pool_data(addr):
        return pool_data_map.get(addr)
    
    analyzer.pumpswap_sdk.get_pair_address = mock_get_pair_address
    analyzer.pumpswap_sdk.get_pool_data = mock_get_pool_data
    
    # Process batch
    results = await analyzer.analyze_signals_batch(batch_signals)
    
    # Display batch results
    print(f"\n📊 Batch Results Summary:")
    print(f"   Total Signals: {len(results)}")
    
    executable_count = sum(1 for r in results if r.execution_feasible)
    high_quality_count = sum(1 for r in results if r.signal_quality in [SignalQuality.EXCELLENT, SignalQuality.GOOD])
    
    print(f"   Execution Feasible: {executable_count}/{len(results)}")
    print(f"   High Quality: {high_quality_count}/{len(results)}")
    
    avg_score = sum(r.final_signal_score for r in results) / len(results)
    print(f"   Average Signal Score: {avg_score:.4f}")
    
    # Performance metrics
    metrics = analyzer.get_performance_metrics()
    print(f"\n⚡ Performance Metrics:")
    print(f"   Total Analyses: {metrics['total_analyses']}")
    print(f"   Success Rate: {metrics['success_rate_percent']:.1f}%")
    print(f"   Fallback Rate: {metrics['fallback_rate_percent']:.1f}%")

async def demonstrate_variance_based_thresholds():
    """Demonstrate variance-based threshold scaling"""
    print("📊 Variance-Based Threshold Scaling")
    print("=" * 40)
    
    config = create_example_config()
    calculator = AdaptiveThresholdCalculator(config)
    
    # Create signals with different variance levels
    variance_signals = [
        {'vol_risk': 0.02, 'q50': 0.03, 'prob_up': 0.6, 'tradeable': True, 'regime': 'low_variance'},
        {'vol_risk': 0.05, 'q50': 0.04, 'prob_up': 0.62, 'tradeable': True, 'regime': 'low_variance'},
        {'vol_risk': 0.10, 'q50': 0.05, 'prob_up': 0.65, 'tradeable': True, 'regime': 'medium_variance'},
        {'vol_risk': 0.15, 'q50': 0.06, 'prob_up': 0.67, 'tradeable': True, 'regime': 'medium_variance'},
        {'vol_risk': 0.25, 'q50': 0.08, 'prob_up': 0.7, 'tradeable': True, 'regime': 'high_variance'},
        {'vol_risk': 0.35, 'q50': 0.10, 'prob_up': 0.72, 'tradeable': True, 'regime': 'high_variance'},
        {'vol_risk': 0.45, 'q50': 0.12, 'prob_up': 0.75, 'tradeable': True, 'regime': 'extreme_variance'},
        {'vol_risk': 0.55, 'q50': 0.15, 'prob_up': 0.78, 'tradeable': True, 'regime': 'extreme_variance'}
    ]
    
    # Calculate variance-based thresholds
    thresholds = calculator.calculate_variance_based_thresholds(variance_signals)
    
    print("📈 Variance Regime Thresholds:")
    for regime, threshold in thresholds.items():
        if isinstance(threshold, float):
            print(f"   {regime}: {threshold:.6f}")
    
    if 'percentiles' in thresholds:
        print(f"\n📊 Variance Percentiles:")
        for level, value in thresholds['percentiles'].items():
            print(f"   {level}: {value:.4f}")
    
    print(f"\n📈 Statistics:")
    print(f"   Mean Vol Risk: {thresholds.get('mean_vol_risk', 0):.4f}")
    print(f"   Std Vol Risk: {thresholds.get('std_vol_risk', 0):.4f}")

async def demonstrate_threshold_testing():
    """Demonstrate testing adaptive thresholds against traditional calculations"""
    print("🧪 Threshold Testing vs Traditional Calculations")
    print("=" * 50)
    
    config = create_example_config()
    calculator = AdaptiveThresholdCalculator(config)
    
    # Test signals
    test_signals = create_sample_signals()
    pool_data_list = create_sample_pool_data()
    
    # Run comparison test
    comparison_results = calculator.test_against_expected_value(test_signals, pool_data_list)
    
    print("📊 Comparison Results:")
    print(f"   Total Signals: {comparison_results['total_signals']}")
    print(f"   Adaptive Significant: {comparison_results['adaptive_significant']}")
    print(f"   Traditional Significant: {comparison_results['traditional_significant']}")
    print(f"   Agreement: {comparison_results['agreement_count']}/{comparison_results['total_signals']}")
    
    metrics = comparison_results['performance_metrics']
    print(f"\n📈 Performance Metrics:")
    print(f"   Agreement Rate: {metrics['agreement_rate']:.2%}")
    print(f"   Adaptive Rate: {metrics['adaptive_rate']:.2%}")
    print(f"   Traditional Rate: {metrics['traditional_rate']:.2%}")
    
    # Show detailed comparisons
    print(f"\n🔍 Detailed Comparisons:")
    for i, comp in enumerate(comparison_results['threshold_comparisons']):
        print(f"   Signal {i+1}:")
        print(f"      Adaptive EV: {comp['adaptive_expected_value']:+.6f}")
        print(f"      Traditional EV: {comp['traditional_expected_value']:+.6f}")
        print(f"      Agreement: {comp['agreement']}")
        print(f"      Price Impact Cost: {comp['price_impact_cost']:.6f}")

async def main():
    """Main demonstration function"""
    print("🚀 Enhanced Signal Processing with PumpSwap Integration")
    print("=" * 70)
    print("This example demonstrates the implementation of Task 6:")
    print("- PumpSwapSignalAnalyzer: Enhanced signal analysis with pool data")
    print("- AdaptiveThresholdCalculator: PumpSwap-aware economic significance")
    print("=" * 70)
    print()
    
    try:
        # Run demonstrations
        await demonstrate_signal_analysis()
        print()
        
        await demonstrate_batch_analysis()
        print()
        
        await demonstrate_variance_based_thresholds()
        print()
        
        await demonstrate_threshold_testing()
        print()
        
        print("✅ All demonstrations completed successfully!")
        print("\n📋 Implementation Summary:")
        print("- Enhanced Q50 signals with PumpSwap pool data integration")
        print("- Liquidity-adjusted signal strength calculations")
        print("- Price impact estimates in threshold adjustments")
        print("- Variance-based threshold scaling with liquidity constraints")
        print("- Comprehensive fallback logic for unavailable data")
        print("- Batch processing capabilities for efficiency")
        print("- Performance monitoring and metrics tracking")
        
        print(f"\n🎯 Requirements Compliance:")
        print(f"- ✅ Requirement 7.1: Enhanced signal analysis with PumpSwap pool data")
        print(f"- ✅ Requirement 7.4: Execution feasibility integration")
        print(f"- ✅ Requirement 7.5: Liquidity-adjusted signal strength calculations")
        print(f"- ✅ Requirement 7.6: Fallback logic for unavailable PumpSwap data")
        
    except Exception as e:
        print(f"❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())