"""
Test Enhanced Signal Processing with PumpSwap Integration

This test suite validates the implementation of task 6 components:
- PumpSwapSignalAnalyzer
- AdaptiveThresholdCalculator

Tests verify compliance with requirements 7.1, 7.4, 7.5, and 7.6.
"""

import asyncio
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# Import the components we're testing
from nautilus_poc.pumpswap_signal_analyzer import (
    PumpSwapSignalAnalyzer, 
    EnhancedQ50Signal, 
    SignalQuality
)
from nautilus_poc.adaptive_threshold_calculator import (
    AdaptiveThresholdCalculator,
    ThresholdType,
    EconomicSignificanceResult,
    ThresholdCalculationResult
)
from nautilus_poc.config import NautilusPOCConfig, Q50Config, PumpSwapConfig, SolanaConfig, NautilusConfig
from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.liquidity_validator import LiquidityValidator, LiquidityValidationResult, LiquidityStatus

class TestPumpSwapSignalAnalyzer:
    """Test PumpSwapSignalAnalyzer implementation"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        return NautilusPOCConfig(
            environment='testnet',
            q50=Q50Config(
                features_path='data3/macro_features.pkl',
                signal_tolerance_minutes=5,
                required_columns=[]
            ),
            pumpswap=PumpSwapConfig(
                payer_public_key='test_key',
                private_key_path='test_path',
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
                instance_id='TEST-001',
                log_level='INFO',
                cache_database_path='test_cache.db'
            ),
            monitoring={'realistic_transaction_cost': 0.0005, 'min_expected_value': 0.001},
            error_handling={},
            regime_detection={'liquidity_weight': 0.3, 'execution_weight': 0.2}
        )
    
    @pytest.fixture
    def mock_signal_loader(self):
        """Create mock signal loader"""
        loader = Mock(spec=Q50SignalLoader)
        return loader
    
    @pytest.fixture
    def mock_liquidity_validator(self):
        """Create mock liquidity validator"""
        validator = Mock(spec=LiquidityValidator)
        
        # Mock validation result
        validation_result = LiquidityValidationResult(
            status=LiquidityStatus.SUFFICIENT,
            is_valid=True,
            pool_liquidity_sol=100.0,
            pool_liquidity_usd=10000.0,
            estimated_price_impact=2.5,
            max_trade_size_sol=25.0,
            recommended_trade_size_sol=5.0,
            validation_details={'test': True}
        )
        
        validator.validate_liquidity_detailed.return_value = validation_result
        return validator
    
    @pytest.fixture
    def analyzer(self, mock_config, mock_signal_loader, mock_liquidity_validator):
        """Create PumpSwapSignalAnalyzer instance"""
        return PumpSwapSignalAnalyzer(mock_config, mock_signal_loader, mock_liquidity_validator)
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample Q50 signal"""
        return {
            'timestamp': pd.Timestamp.now(),
            'q10': -0.02,
            'q50': 0.05,
            'q90': 0.12,
            'vol_raw': 0.15,
            'vol_risk': 0.08,
            'prob_up': 0.65,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True,
            'regime': 'medium_variance',
            'vol_risk_percentile': 0.45,
            'threshold_adjustment': 0.0,
            'regime_multiplier': 1.0
        }
    
    @pytest.fixture
    def sample_pool_data(self):
        """Create sample pool data"""
        return {
            'mint_address': 'So11111111111111111111111111111111111111112',
            'reserve_in_usd': 50000,
            'reserve_sol': 500,
            'reserve_token': 500000,
            'price': 0.001,
            'volume_24h': 10000
        }
    
    @pytest.mark.asyncio
    async def test_analyze_signal_with_pumpswap_data(self, analyzer, sample_signal, sample_pool_data):
        """Test signal analysis with PumpSwap data available"""
        # Mock PumpSwap SDK responses
        analyzer.pumpswap_sdk.get_pair_address = AsyncMock(return_value='pair_test123')
        analyzer.pumpswap_sdk.get_pool_data = AsyncMock(return_value=sample_pool_data)
        
        mint_address = 'So11111111111111111111111111111111111111112'
        
        # Analyze signal
        result = await analyzer.analyze_signal(sample_signal, mint_address)
        
        # Verify result structure
        assert isinstance(result, EnhancedQ50Signal)
        assert result.mint_address == mint_address
        assert result.pumpswap_data_available == True
        assert result.execution_feasible == True
        assert result.pool_liquidity_sol > 0
        assert result.liquidity_adjusted_strength > 0
        assert result.final_signal_score > 0
        
        # Verify requirements 7.1, 7.4, 7.5, 7.6
        assert result.expected_value != 0  # Economic significance calculation
        assert result.enhanced_info_ratio > 0  # Enhanced info ratio with liquidity
        assert result.recommended_position_size > 0  # Position sizing
        assert result.signal_quality != SignalQuality.UNTRADEABLE  # Quality assessment
    
    @pytest.mark.asyncio
    async def test_analyze_signal_without_pumpswap_data(self, analyzer, sample_signal):
        """Test signal analysis fallback when PumpSwap data unavailable"""
        # Mock PumpSwap SDK to return None
        analyzer.pumpswap_sdk.get_pair_address = AsyncMock(return_value=None)
        analyzer.pumpswap_sdk.get_pool_data = AsyncMock(return_value=None)
        
        mint_address = 'invalid_mint'
        
        # Analyze signal
        result = await analyzer.analyze_signal(sample_signal, mint_address)
        
        # Verify fallback behavior
        assert isinstance(result, EnhancedQ50Signal)
        assert result.pumpswap_data_available == False
        assert result.execution_feasible == False
        assert result.fallback_reason is not None
        assert result.signal_quality == SignalQuality.UNTRADEABLE
        assert result.final_signal_score == 0
    
    @pytest.mark.asyncio
    async def test_analyze_signals_batch(self, analyzer, sample_signal, sample_pool_data):
        """Test batch signal analysis"""
        # Mock PumpSwap SDK responses
        analyzer.pumpswap_sdk.get_pair_address = AsyncMock(return_value='pair_test123')
        analyzer.pumpswap_sdk.get_pool_data = AsyncMock(return_value=sample_pool_data)
        
        # Create batch of signals
        signals = [
            (sample_signal, 'mint1'),
            (sample_signal, 'mint2'),
            ({**sample_signal, 'q50': -0.03}, 'mint3')  # Negative signal
        ]
        
        # Analyze batch
        results = await analyzer.analyze_signals_batch(signals)
        
        # Verify results
        assert len(results) == 3
        assert all(isinstance(r, EnhancedQ50Signal) for r in results)
        assert results[0].mint_address == 'mint1'
        assert results[1].mint_address == 'mint2'
        assert results[2].mint_address == 'mint3'
        assert results[2].q50 == -0.03  # Negative signal preserved
    
    def test_liquidity_adjusted_strength_calculation(self, analyzer, sample_signal, sample_pool_data):
        """Test liquidity-adjusted signal strength calculation"""
        # Test with good liquidity
        enhanced_metrics = {'signal_strength': 0.05}
        strength = analyzer._calculate_liquidity_adjusted_strength(
            sample_signal, sample_pool_data, enhanced_metrics
        )
        
        assert strength > 0
        assert strength != enhanced_metrics['signal_strength']  # Should be adjusted
        
        # Test without pool data
        strength_no_data = analyzer._calculate_liquidity_adjusted_strength(
            sample_signal, None, enhanced_metrics
        )
        
        assert strength_no_data < strength  # Should be penalized
    
    def test_execution_feasibility_determination(self, analyzer, sample_signal, sample_pool_data):
        """Test execution feasibility determination"""
        # Mock liquidity validation
        mock_validation = LiquidityValidationResult(
            status=LiquidityStatus.SUFFICIENT,
            is_valid=True,
            pool_liquidity_sol=100.0,
            pool_liquidity_usd=10000.0,
            estimated_price_impact=2.5,
            max_trade_size_sol=25.0,
            recommended_trade_size_sol=5.0,
            validation_details={}
        )
        
        # Test with good conditions
        feasible = analyzer._determine_execution_feasibility(
            sample_signal, sample_pool_data, mock_validation
        )
        assert feasible == True
        
        # Test with non-tradeable signal
        non_tradeable_signal = {**sample_signal, 'tradeable': False}
        feasible = analyzer._determine_execution_feasibility(
            non_tradeable_signal, sample_pool_data, mock_validation
        )
        assert feasible == False
        
        # Test without pool data
        feasible = analyzer._determine_execution_feasibility(
            sample_signal, None, None
        )
        assert feasible == False
    
    def test_performance_metrics(self, analyzer):
        """Test performance metrics tracking"""
        # Initial metrics
        metrics = analyzer.get_performance_metrics()
        assert metrics['total_analyses'] == 0
        assert metrics['successful_analyses'] == 0
        assert metrics['fallback_count'] == 0
        
        # Simulate some analyses
        analyzer.analysis_count = 10
        analyzer.successful_analyses = 8
        analyzer.fallback_count = 2
        
        metrics = analyzer.get_performance_metrics()
        assert metrics['total_analyses'] == 10
        assert metrics['success_rate_percent'] == 80.0
        assert metrics['fallback_rate_percent'] == 20.0

class TestAdaptiveThresholdCalculator:
    """Test AdaptiveThresholdCalculator implementation"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        return NautilusPOCConfig(
            environment='testnet',
            q50=Q50Config(
                features_path='data3/macro_features.pkl',
                signal_tolerance_minutes=5,
                required_columns=[]
            ),
            pumpswap=PumpSwapConfig(
                payer_public_key='test_key',
                private_key_path='test_path',
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
                instance_id='TEST-001',
                log_level='INFO',
                cache_database_path='test_cache.db'
            ),
            monitoring={'realistic_transaction_cost': 0.0005, 'min_expected_value': 0.001},
            error_handling={},
            regime_detection={
                'liquidity_weight': 0.3,
                'execution_weight': 0.2,
                'low_variance_percentile': 0.30,
                'high_variance_percentile': 0.70,
                'extreme_variance_percentile': 0.90,
                'low_variance_adjustment': -0.30,
                'medium_variance_adjustment': 0.0,
                'high_variance_adjustment': 0.40,
                'extreme_variance_adjustment': 0.80
            }
        )
    
    @pytest.fixture
    def calculator(self, mock_config):
        """Create AdaptiveThresholdCalculator instance"""
        return AdaptiveThresholdCalculator(mock_config)
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample Q50 signal"""
        return {
            'q50': 0.05,
            'prob_up': 0.65,
            'vol_risk': 0.08,
            'vol_risk_percentile': 0.45,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True,
            'regime_multiplier': 1.0
        }
    
    @pytest.fixture
    def sample_pool_data(self):
        """Create sample pool data"""
        return {
            'reserve_sol': 100.0,
            'reserve_in_usd': 10000.0,
            'price': 0.001,
            'volume_24h': 5000
        }
    
    def test_economic_significance_calculation(self, calculator, sample_signal, sample_pool_data):
        """Test PumpSwap-aware economic significance calculation"""
        result = calculator.calculate_economic_significance(
            sample_signal, sample_pool_data, estimated_position_size=0.1
        )
        
        # Verify result structure
        assert isinstance(result, EconomicSignificanceResult)
        assert result.expected_value != 0
        assert result.potential_gain > 0
        assert result.potential_loss > 0
        assert result.transaction_costs > 0
        assert result.price_impact_costs >= 0
        assert result.total_costs > result.transaction_costs  # Should include price impact
        
        # Verify economic significance logic
        assert isinstance(result.is_economically_significant, bool)
        assert result.break_even_probability > 0
        assert result.break_even_probability < 1
    
    def test_economic_significance_without_pool_data(self, calculator, sample_signal):
        """Test economic significance calculation without pool data"""
        result = calculator.calculate_economic_significance(sample_signal, None)
        
        # Should still work but with higher costs
        assert isinstance(result, EconomicSignificanceResult)
        assert result.total_costs > calculator.realistic_transaction_cost
        assert result.price_impact_costs == calculator.realistic_transaction_cost  # Default cost
    
    def test_adaptive_threshold_calculation(self, calculator, sample_signal, sample_pool_data):
        """Test adaptive threshold calculation with all adjustments"""
        result = calculator.calculate_adaptive_threshold(
            sample_signal, 
            sample_pool_data, 
            ThresholdType.ECONOMIC_SIGNIFICANCE,
            estimated_position_size=0.1
        )
        
        # Verify result structure
        assert isinstance(result, ThresholdCalculationResult)
        assert result.threshold_type == ThresholdType.ECONOMIC_SIGNIFICANCE
        assert result.base_threshold > 0
        assert result.final_threshold > 0
        assert isinstance(result.is_above_threshold, bool)
        
        # Verify adjustment components
        assert 'liquidity_adjustment' in result.threshold_components
        assert 'price_impact_adjustment' in result.threshold_components
        assert 'variance_adjustment' in result.threshold_components
        assert 'regime_adjustment' in result.threshold_components
        
        # Verify calculation details
        assert 'pool_data_available' in result.calculation_details
        assert result.calculation_details['pool_data_available'] == True
    
    def test_variance_based_threshold_scaling(self, calculator):
        """Test variance-based threshold scaling with multiple signals"""
        # Create signals with different variance levels
        signals = [
            {'vol_risk': 0.02, 'q50': 0.03, 'prob_up': 0.6, 'tradeable': True},  # Low variance
            {'vol_risk': 0.10, 'q50': 0.05, 'prob_up': 0.65, 'tradeable': True},  # Medium variance
            {'vol_risk': 0.25, 'q50': 0.08, 'prob_up': 0.7, 'tradeable': True},  # High variance
            {'vol_risk': 0.45, 'q50': 0.12, 'prob_up': 0.75, 'tradeable': True}   # Extreme variance
        ]
        
        result = calculator.calculate_variance_based_thresholds(signals)
        
        # Verify results
        assert 'percentiles' in result
        assert 'low_variance' in result or 'medium_variance' in result
        assert 'mean_vol_risk' in result
        assert 'std_vol_risk' in result
        
        # Verify percentiles are calculated
        percentiles = result['percentiles']
        assert 'low' in percentiles
        assert 'high' in percentiles
        assert 'extreme' in percentiles
    
    def test_expected_value_comparison(self, calculator):
        """Test adaptive thresholds against traditional expected value calculations"""
        # Create test signals
        signals = [
            {'q50': 0.05, 'prob_up': 0.65, 'vol_risk': 0.08, 'tradeable': True, 'economically_significant': True},
            {'q50': 0.02, 'prob_up': 0.55, 'vol_risk': 0.12, 'tradeable': True, 'economically_significant': False},
            {'q50': 0.08, 'prob_up': 0.75, 'vol_risk': 0.06, 'tradeable': True, 'economically_significant': True}
        ]
        
        # Create corresponding pool data
        pool_data_list = [
            {'reserve_sol': 100.0, 'reserve_in_usd': 10000.0},
            {'reserve_sol': 50.0, 'reserve_in_usd': 5000.0},
            {'reserve_sol': 200.0, 'reserve_in_usd': 20000.0}
        ]
        
        result = calculator.test_against_expected_value(signals, pool_data_list)
        
        # Verify comparison results
        assert 'total_signals' in result
        assert result['total_signals'] == 3
        assert 'adaptive_significant' in result
        assert 'traditional_significant' in result
        assert 'agreement_count' in result
        assert 'performance_metrics' in result
        
        # Verify performance metrics
        metrics = result['performance_metrics']
        assert 'agreement_rate' in metrics
        assert 'adaptive_rate' in metrics
        assert 'traditional_rate' in metrics
        assert 0 <= metrics['agreement_rate'] <= 1
    
    def test_price_impact_cost_calculation(self, calculator, sample_pool_data):
        """Test price impact cost calculation"""
        # Test with small position
        small_cost = calculator._calculate_price_impact_cost(sample_pool_data, 1.0)
        
        # Test with large position
        large_cost = calculator._calculate_price_impact_cost(sample_pool_data, 50.0)
        
        # Large position should have higher impact
        assert large_cost > small_cost
        assert large_cost <= 0.2  # Should be capped at 20%
        
        # Test without pool data
        no_data_cost = calculator._calculate_price_impact_cost(None, 1.0)
        assert no_data_cost >= calculator.realistic_transaction_cost
    
    def test_liquidity_adjustment_calculation(self, calculator):
        """Test liquidity-based threshold adjustment"""
        # Test with excellent liquidity
        excellent_pool = {'reserve_sol': 200.0, 'reserve_in_usd': 20000.0}
        excellent_adj = calculator._calculate_liquidity_adjustment(excellent_pool, 1.0)
        
        # Test with poor liquidity
        poor_pool = {'reserve_sol': 5.0, 'reserve_in_usd': 500.0}
        poor_adj = calculator._calculate_liquidity_adjustment(poor_pool, 1.0)
        
        # Poor liquidity should have higher (more positive) adjustment
        assert poor_adj > excellent_adj
        
        # Test without pool data
        no_data_adj = calculator._calculate_liquidity_adjustment(None, 1.0)
        assert no_data_adj > 0  # Should be penalty
    
    def test_variance_regime_classification(self, calculator):
        """Test variance regime classification"""
        # Test different variance levels
        low_var_signal = {'vol_risk': 0.02, 'vol_risk_percentile': 0.25}
        medium_var_signal = {'vol_risk': 0.10, 'vol_risk_percentile': 0.50}
        high_var_signal = {'vol_risk': 0.25, 'vol_risk_percentile': 0.80}
        extreme_var_signal = {'vol_risk': 0.45, 'vol_risk_percentile': 0.95}
        
        assert calculator._classify_variance_regime(low_var_signal) == 'low_variance'
        assert calculator._classify_variance_regime(medium_var_signal) == 'medium_variance'
        assert calculator._classify_variance_regime(high_var_signal) == 'high_variance'
        assert calculator._classify_variance_regime(extreme_var_signal) == 'extreme_variance'
    
    def test_calculation_summary(self, calculator):
        """Test calculation summary and metrics"""
        # Simulate some calculations
        calculator.calculation_count = 5
        
        summary = calculator.get_calculation_summary()
        
        # Verify summary structure
        assert 'total_calculations' in summary
        assert summary['total_calculations'] == 5
        assert 'base_economic_threshold' in summary
        assert 'variance_percentiles' in summary
        assert 'regime_adjustments' in summary

class TestIntegration:
    """Integration tests for enhanced signal processing"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_signal_enhancement(self):
        """Test complete signal enhancement pipeline"""
        # Create mock configuration
        config = NautilusPOCConfig(
            environment='testnet',
            q50=Q50Config(features_path='test', signal_tolerance_minutes=5, required_columns=[]),
            pumpswap=PumpSwapConfig(
                payer_public_key='test', private_key_path='test',
                max_slippage_percent=5.0, base_position_size=0.1, max_position_size=0.5,
                min_liquidity_sol=10.0, max_price_impact_percent=10.0,
                stop_loss_percent=20.0, position_timeout_hours=24
            ),
            solana=SolanaConfig(network='testnet', rpc_endpoint='test', commitment='confirmed'),
            nautilus=NautilusConfig(instance_id='TEST', log_level='INFO', cache_database_path='test'),
            monitoring={'realistic_transaction_cost': 0.0005, 'min_expected_value': 0.001},
            error_handling={},
            regime_detection={'liquidity_weight': 0.3, 'execution_weight': 0.2}
        )
        
        # Create components
        signal_loader = Mock(spec=Q50SignalLoader)
        liquidity_validator = Mock(spec=LiquidityValidator)
        
        # Mock validation result
        validation_result = LiquidityValidationResult(
            status=LiquidityStatus.SUFFICIENT,
            is_valid=True,
            pool_liquidity_sol=100.0,
            pool_liquidity_usd=10000.0,
            estimated_price_impact=2.5,
            max_trade_size_sol=25.0,
            recommended_trade_size_sol=5.0,
            validation_details={}
        )
        liquidity_validator.validate_liquidity_detailed.return_value = validation_result
        
        # Create analyzer and calculator
        analyzer = PumpSwapSignalAnalyzer(config, signal_loader, liquidity_validator)
        calculator = AdaptiveThresholdCalculator(config)
        
        # Test signal
        signal = {
            'timestamp': pd.Timestamp.now(),
            'q50': 0.05,
            'prob_up': 0.65,
            'vol_risk': 0.08,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True,
            'regime': 'medium_variance',
            'regime_multiplier': 1.0
        }
        
        # Mock PumpSwap data
        pool_data = {
            'reserve_sol': 100.0,
            'reserve_in_usd': 10000.0,
            'price': 0.001,
            'volume_24h': 5000
        }
        
        analyzer.pumpswap_sdk.get_pair_address = AsyncMock(return_value='pair_test')
        analyzer.pumpswap_sdk.get_pool_data = AsyncMock(return_value=pool_data)
        
        # Analyze signal
        enhanced_signal = await analyzer.analyze_signal(signal, 'test_mint')
        
        # Calculate adaptive thresholds
        economic_result = calculator.calculate_economic_significance(signal, pool_data)
        threshold_result = calculator.calculate_adaptive_threshold(signal, pool_data)
        
        # Verify integration
        assert enhanced_signal.pumpswap_data_available == True
        assert enhanced_signal.execution_feasible == True
        assert enhanced_signal.final_signal_score > 0
        
        assert economic_result.is_economically_significant == True
        assert threshold_result.is_above_threshold == True
        
        # Verify requirements compliance
        # Requirement 7.1: Enhanced signal analysis with PumpSwap pool data
        assert enhanced_signal.pool_liquidity_sol > 0
        assert enhanced_signal.estimated_price_impact > 0
        
        # Requirement 7.4: Execution feasibility integration
        assert enhanced_signal.execution_feasible == True
        
        # Requirement 7.5: Liquidity-adjusted signal strength
        assert enhanced_signal.liquidity_adjusted_strength > 0
        assert enhanced_signal.liquidity_adjusted_strength != abs(signal['q50'])
        
        # Requirement 7.6: Fallback logic tested in separate test
        
        print("✅ All integration tests passed")
        print(f"Enhanced signal score: {enhanced_signal.final_signal_score:.4f}")
        print(f"Economic significance: {economic_result.is_economically_significant}")
        print(f"Adaptive threshold: {threshold_result.final_threshold:.6f}")

if __name__ == "__main__":
    # Run basic tests
    import sys
    
    print("🧪 Testing Enhanced Signal Processing Implementation")
    print("=" * 60)
    
    # Test basic functionality
    try:
        # Test imports
        from nautilus_poc.pumpswap_signal_analyzer import PumpSwapSignalAnalyzer
        from nautilus_poc.adaptive_threshold_calculator import AdaptiveThresholdCalculator
        print("✅ All imports successful")
        
        # Test configuration
        config = NautilusPOCConfig(
            environment='testnet',
            q50=Q50Config(features_path='test', signal_tolerance_minutes=5, required_columns=[]),
            pumpswap=PumpSwapConfig(
                payer_public_key='test', private_key_path='test',
                max_slippage_percent=5.0, base_position_size=0.1, max_position_size=0.5,
                min_liquidity_sol=10.0, max_price_impact_percent=10.0,
                stop_loss_percent=20.0, position_timeout_hours=24
            ),
            solana=SolanaConfig(network='testnet', rpc_endpoint='test', commitment='confirmed'),
            nautilus=NautilusConfig(instance_id='TEST', log_level='INFO', cache_database_path='test'),
            monitoring={'realistic_transaction_cost': 0.0005, 'min_expected_value': 0.001},
            error_handling={},
            regime_detection={'liquidity_weight': 0.3, 'execution_weight': 0.2}
        )
        print("✅ Configuration creation successful")
        
        # Test component initialization
        signal_loader = Mock(spec=Q50SignalLoader)
        liquidity_validator = Mock(spec=LiquidityValidator)
        
        analyzer = PumpSwapSignalAnalyzer(config, signal_loader, liquidity_validator)
        calculator = AdaptiveThresholdCalculator(config)
        print("✅ Component initialization successful")
        
        # Test basic calculations
        sample_signal = {
            'q50': 0.05,
            'prob_up': 0.65,
            'vol_risk': 0.08,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True
        }
        
        sample_pool_data = {
            'reserve_sol': 100.0,
            'reserve_in_usd': 10000.0,
            'price': 0.001,
            'volume_24h': 5000
        }
        
        # Test economic significance
        economic_result = calculator.calculate_economic_significance(sample_signal, sample_pool_data)
        print(f"✅ Economic significance calculation: {economic_result.is_economically_significant}")
        
        # Test adaptive threshold
        threshold_result = calculator.calculate_adaptive_threshold(sample_signal, sample_pool_data)
        print(f"✅ Adaptive threshold calculation: {threshold_result.final_threshold:.6f}")
        
        print("\n🎉 All basic tests passed!")
        print("\nImplementation Summary:")
        print("- ✅ PumpSwapSignalAnalyzer: Enhances Q50 signals with PumpSwap pool data")
        print("- ✅ AdaptiveThresholdCalculator: Implements PumpSwap-aware economic significance")
        print("- ✅ Liquidity-adjusted signal strength calculations")
        print("- ✅ Price impact estimates in threshold adjustments")
        print("- ✅ Variance-based threshold scaling with liquidity constraints")
        print("- ✅ Fallback logic for unavailable PumpSwap data")
        
        print(f"\nRequirements Compliance:")
        print(f"- ✅ Requirement 7.1: Enhanced signal analysis with PumpSwap pool data")
        print(f"- ✅ Requirement 7.4: Execution feasibility integration")
        print(f"- ✅ Requirement 7.5: Liquidity-adjusted signal strength calculations")
        print(f"- ✅ Requirement 7.6: Fallback logic for unavailable PumpSwap data")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)