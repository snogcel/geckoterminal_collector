"""
Adaptive Threshold Calculator for PumpSwap-Aware Signal Processing

This module provides the AdaptiveThresholdCalculator class that creates
PumpSwap-aware economic significance calculation, adds price impact estimates
to threshold adjustments, and implements variance-based threshold scaling
with liquidity constraints.
"""

import logging
import math
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

from .config import NautilusPOCConfig

logger = logging.getLogger(__name__)

class ThresholdType(Enum):
    """Types of adaptive thresholds"""
    ECONOMIC_SIGNIFICANCE = "economic_significance"
    SIGNAL_STRENGTH = "signal_strength"
    EXECUTION_FEASIBILITY = "execution_feasibility"
    RISK_ADJUSTED = "risk_adjusted"

@dataclass
class ThresholdCalculationResult:
    """Result of threshold calculation"""
    threshold_type: ThresholdType
    base_threshold: float
    liquidity_adjustment: float
    price_impact_adjustment: float
    variance_adjustment: float
    regime_adjustment: float
    final_threshold: float
    threshold_components: Dict[str, float]
    calculation_details: Dict[str, Any]
    is_above_threshold: bool

@dataclass
class EconomicSignificanceResult:
    """Result of economic significance calculation"""
    expected_value: float
    potential_gain: float
    potential_loss: float
    transaction_costs: float
    price_impact_costs: float
    total_costs: float
    net_expected_value: float
    is_economically_significant: bool
    significance_margin: float
    break_even_probability: float

class AdaptiveThresholdCalculator:
    """
    Create PumpSwap-aware economic significance calculation
    
    Key Responsibilities:
    - Create PumpSwap-aware economic significance calculation
    - Add price impact estimates to threshold adjustments
    - Implement variance-based threshold scaling with liquidity constraints
    - Test against existing expected value calculations
    """
    
    def __init__(self, config: NautilusPOCConfig):
        """Initialize adaptive threshold calculator"""
        self.config = config
        
        # Base threshold parameters
        self.base_economic_threshold = config.monitoring.get('min_expected_value', 0.001)
        self.base_signal_threshold = config.regime_detection.get('base_signal_threshold', 0.01)
        self.realistic_transaction_cost = config.monitoring.get('realistic_transaction_cost', 0.0005)
        
        # Liquidity adjustment parameters
        self.liquidity_impact_weight = config.regime_detection.get('liquidity_impact_weight', 0.3)
        # self.min_liquidity_threshold = config.pumpswap.min_liquidity_sol
        self.optimal_liquidity_threshold = config.regime_detection.get('optimal_liquidity_sol', 100.0)
        
        # Price impact parameters
        # self.max_acceptable_impact = config.pumpswap.max_price_impact_percent
        self.price_impact_penalty_factor = config.regime_detection.get('price_impact_penalty_factor', 2.0)
        
        # Variance scaling parameters
        self.variance_percentiles = {
            'low': config.regime_detection.get('low_variance_percentile', 0.30),
            'high': config.regime_detection.get('high_variance_percentile', 0.70),
            'extreme': config.regime_detection.get('extreme_variance_percentile', 0.90)
        }
        
        # Regime adjustments
        self.regime_threshold_adjustments = {
            'low_variance': config.regime_detection.get('low_variance_adjustment', -0.30),
            'medium_variance': config.regime_detection.get('medium_variance_adjustment', 0.0),
            'high_variance': config.regime_detection.get('high_variance_adjustment', 0.40),
            'extreme_variance': config.regime_detection.get('extreme_variance_adjustment', 0.80)
        }
        
        # Performance tracking
        self.calculation_count = 0
        self.threshold_cache = {}
        
        logger.info("AdaptiveThresholdCalculator initialized")
    
    def calculate_economic_significance(self, signal: Dict[str, Any], 
                                      pool_data: Optional[Dict[str, Any]] = None,
                                      estimated_position_size: float = 0.1) -> EconomicSignificanceResult:
        """
        Calculate PumpSwap-aware economic significance
        
        Args:
            signal: Q50 signal data
            pool_data: PumpSwap pool data (optional)
            estimated_position_size: Estimated position size in SOL
            
        Returns:
            EconomicSignificanceResult with detailed calculation
        """
        try:
            self.calculation_count += 1
            
            # Extract signal components
            q50_value = signal.get('q50', 0)
            prob_up = signal.get('prob_up', 0.5)
            vol_risk = signal.get('vol_risk', 0.1)
            
            # Calculate potential gains and losses
            potential_gain = abs(q50_value)
            potential_loss = abs(q50_value)
            
            # Calculate transaction costs
            base_transaction_cost = self.realistic_transaction_cost
            
            # Add PumpSwap-specific costs
            price_impact_cost = self._calculate_price_impact_cost(
                pool_data, estimated_position_size
            )
            
            # Additional costs for uncertain execution
            if not pool_data:
                uncertainty_cost = base_transaction_cost * 0.5  # 50% penalty for no data
            else:
                uncertainty_cost = 0.0
            
            total_transaction_costs = base_transaction_cost + uncertainty_cost
            total_costs = total_transaction_costs + price_impact_cost
            
            # Calculate expected value
            adjusted_gain = potential_gain - total_costs
            adjusted_loss = potential_loss + total_costs
            
            expected_value = (prob_up * adjusted_gain) - ((1 - prob_up) * adjusted_loss)
            net_expected_value = expected_value
            
            # Determine economic significance
            is_economically_significant = net_expected_value > self.base_economic_threshold
            significance_margin = net_expected_value - self.base_economic_threshold
            
            # Calculate break-even probability
            if potential_gain + potential_loss > 0:
                break_even_prob = (potential_loss + total_costs) / (potential_gain + potential_loss + 2 * total_costs)
            else:
                break_even_prob = 0.5
            
            result = EconomicSignificanceResult(
                expected_value=expected_value,
                potential_gain=potential_gain,
                potential_loss=potential_loss,
                transaction_costs=total_transaction_costs,
                price_impact_costs=price_impact_cost,
                total_costs=total_costs,
                net_expected_value=net_expected_value,
                is_economically_significant=is_economically_significant,
                significance_margin=significance_margin,
                break_even_probability=break_even_prob
            )
            
            logger.debug(f"Economic significance: {is_economically_significant}, "
                        f"expected_value: {net_expected_value:.6f}, "
                        f"margin: {significance_margin:.6f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating economic significance: {e}")
            # Return conservative fallback
            return EconomicSignificanceResult(
                expected_value=0,
                potential_gain=0,
                potential_loss=0,
                transaction_costs=self.realistic_transaction_cost,
                price_impact_costs=0,
                total_costs=self.realistic_transaction_cost,
                net_expected_value=0,
                is_economically_significant=False,
                significance_margin=-self.base_economic_threshold,
                break_even_probability=0.5
            )
    
    def calculate_adaptive_threshold(self, signal: Dict[str, Any],
                                   pool_data: Optional[Dict[str, Any]] = None,
                                   threshold_type: ThresholdType = ThresholdType.ECONOMIC_SIGNIFICANCE,
                                   estimated_position_size: float = 0.1) -> ThresholdCalculationResult:
        """
        Calculate adaptive threshold with PumpSwap and variance adjustments
        
        Args:
            signal: Q50 signal data
            pool_data: PumpSwap pool data (optional)
            threshold_type: Type of threshold to calculate
            estimated_position_size: Estimated position size in SOL
            
        Returns:
            ThresholdCalculationResult with detailed calculation
        """
        try:
            # Get base threshold
            base_threshold = self._get_base_threshold(threshold_type)
            
            # Calculate adjustment components
            liquidity_adjustment = self._calculate_liquidity_adjustment(pool_data, estimated_position_size)
            price_impact_adjustment = self._calculate_price_impact_adjustment(pool_data, estimated_position_size)
            variance_adjustment = self._calculate_variance_adjustment(signal)
            regime_adjustment = self._calculate_regime_adjustment(signal)
            
            # Combine adjustments
            total_adjustment = (
                liquidity_adjustment +
                price_impact_adjustment +
                variance_adjustment +
                regime_adjustment
            )
            
            # Calculate final threshold
            final_threshold = base_threshold * (1 + total_adjustment)
            final_threshold = max(final_threshold, base_threshold * 0.1)  # Minimum 10% of base
            
            # Check if signal meets threshold
            signal_value = self._get_signal_value(signal, threshold_type)
            is_above_threshold = signal_value > final_threshold
            
            # Create detailed result
            threshold_components = {
                'base_threshold': base_threshold,
                'liquidity_adjustment': liquidity_adjustment,
                'price_impact_adjustment': price_impact_adjustment,
                'variance_adjustment': variance_adjustment,
                'regime_adjustment': regime_adjustment,
                'total_adjustment': total_adjustment,
                'signal_value': signal_value
            }
            
            calculation_details = {
                'threshold_type': threshold_type.value,
                'pool_data_available': pool_data is not None,
                'estimated_position_size': estimated_position_size,
                'adjustment_breakdown': {
                    'liquidity_factor': self._get_liquidity_factor(pool_data),
                    'price_impact_factor': self._get_price_impact_factor(pool_data, estimated_position_size),
                    'variance_regime': self._classify_variance_regime(signal),
                    'regime_multiplier': signal.get('regime_multiplier', 1.0)
                }
            }
            
            result = ThresholdCalculationResult(
                threshold_type=threshold_type,
                base_threshold=base_threshold,
                liquidity_adjustment=liquidity_adjustment,
                price_impact_adjustment=price_impact_adjustment,
                variance_adjustment=variance_adjustment,
                regime_adjustment=regime_adjustment,
                final_threshold=final_threshold,
                threshold_components=threshold_components,
                calculation_details=calculation_details,
                is_above_threshold=is_above_threshold
            )
            
            logger.debug(f"Adaptive threshold calculated: {final_threshold:.6f} "
                        f"(base: {base_threshold:.6f}, adjustment: {total_adjustment:.3f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating adaptive threshold: {e}")
            # Return conservative fallback
            base_threshold = self._get_base_threshold(threshold_type)
            return ThresholdCalculationResult(
                threshold_type=threshold_type,
                base_threshold=base_threshold,
                liquidity_adjustment=0.5,  # Conservative penalty
                price_impact_adjustment=0.5,  # Conservative penalty
                variance_adjustment=0.0,
                regime_adjustment=0.0,
                final_threshold=base_threshold * 1.5,  # Conservative increase
                threshold_components={},
                calculation_details={'error': str(e)},
                is_above_threshold=False
            )
    
    def calculate_variance_based_thresholds(self, signals: List[Dict[str, Any]],
                                          pool_data_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, float]:
        """
        Calculate variance-based threshold scaling across multiple signals
        
        Args:
            signals: List of Q50 signals
            pool_data_list: List of corresponding pool data (optional)
            
        Returns:
            Dictionary of calculated thresholds by variance regime
        """
        try:
            if not signals:
                return {}
            
            # Extract variance data
            vol_risks = [s.get('vol_risk', 0.1) for s in signals]
            vol_risk_series = pd.Series(vol_risks)
            
            # Calculate percentiles
            percentiles = {
                'low': vol_risk_series.quantile(self.variance_percentiles['low']),
                'high': vol_risk_series.quantile(self.variance_percentiles['high']),
                'extreme': vol_risk_series.quantile(self.variance_percentiles['extreme'])
            }
            
            # Calculate regime-specific thresholds
            regime_thresholds = {}
            
            for i, signal in enumerate(signals):
                vol_risk = signal.get('vol_risk', 0.1)
                pool_data = pool_data_list[i] if pool_data_list and i < len(pool_data_list) else None
                
                # Classify regime
                if vol_risk <= percentiles['low']:
                    regime = 'low_variance'
                elif vol_risk <= percentiles['high']:
                    regime = 'medium_variance'
                elif vol_risk <= percentiles['extreme']:
                    regime = 'high_variance'
                else:
                    regime = 'extreme_variance'
                
                # Calculate threshold for this regime
                if regime not in regime_thresholds:
                    threshold_result = self.calculate_adaptive_threshold(
                        signal, pool_data, ThresholdType.ECONOMIC_SIGNIFICANCE
                    )
                    regime_thresholds[regime] = threshold_result.final_threshold
            
            # Add summary statistics
            regime_thresholds['percentiles'] = percentiles
            regime_thresholds['mean_vol_risk'] = float(vol_risk_series.mean())
            regime_thresholds['std_vol_risk'] = float(vol_risk_series.std())
            
            logger.info(f"Calculated variance-based thresholds for {len(regime_thresholds)} regimes")
            
            return regime_thresholds
            
        except Exception as e:
            logger.error(f"Error calculating variance-based thresholds: {e}")
            return {}
    
    def test_against_expected_value(self, signals: List[Dict[str, Any]],
                                  pool_data_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Test adaptive thresholds against existing expected value calculations
        
        Args:
            signals: List of Q50 signals
            pool_data_list: List of corresponding pool data (optional)
            
        Returns:
            Dictionary with comparison results and statistics
        """
        try:
            if not signals:
                return {'error': 'No signals provided'}
            
            results = {
                'total_signals': len(signals),
                'adaptive_significant': 0,
                'traditional_significant': 0,
                'agreement_count': 0,
                'disagreement_count': 0,
                'adaptive_only': 0,
                'traditional_only': 0,
                'threshold_comparisons': [],
                'performance_metrics': {}
            }
            
            for i, signal in enumerate(signals):
                pool_data = pool_data_list[i] if pool_data_list and i < len(pool_data_list) else None
                
                # Calculate adaptive economic significance
                adaptive_result = self.calculate_economic_significance(signal, pool_data)
                adaptive_significant = adaptive_result.is_economically_significant
                
                # Calculate traditional expected value
                traditional_result = self._calculate_traditional_expected_value(signal)
                traditional_significant = traditional_result > self.base_economic_threshold
                
                # Track results
                if adaptive_significant:
                    results['adaptive_significant'] += 1
                if traditional_significant:
                    results['traditional_significant'] += 1
                
                # Check agreement
                if adaptive_significant == traditional_significant:
                    results['agreement_count'] += 1
                else:
                    results['disagreement_count'] += 1
                    if adaptive_significant and not traditional_significant:
                        results['adaptive_only'] += 1
                    elif traditional_significant and not adaptive_significant:
                        results['traditional_only'] += 1
                
                # Store comparison details
                comparison = {
                    'signal_index': i,
                    'adaptive_expected_value': adaptive_result.net_expected_value,
                    'traditional_expected_value': traditional_result,
                    'adaptive_significant': adaptive_significant,
                    'traditional_significant': traditional_significant,
                    'agreement': adaptive_significant == traditional_significant,
                    'price_impact_cost': adaptive_result.price_impact_costs,
                    'total_costs': adaptive_result.total_costs
                }
                results['threshold_comparisons'].append(comparison)
            
            # Calculate performance metrics
            total_signals = len(signals)
            results['performance_metrics'] = {
                'agreement_rate': results['agreement_count'] / total_signals,
                'adaptive_rate': results['adaptive_significant'] / total_signals,
                'traditional_rate': results['traditional_significant'] / total_signals,
                'adaptive_precision': results['adaptive_only'] / max(results['adaptive_significant'], 1),
                'traditional_precision': results['traditional_only'] / max(results['traditional_significant'], 1)
            }
            
            logger.info(f"Threshold testing completed: {results['agreement_count']}/{total_signals} agreement")
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing against expected value: {e}")
            return {'error': str(e)}
    
    def _get_base_threshold(self, threshold_type: ThresholdType) -> float:
        """Get base threshold for given type"""
        if threshold_type == ThresholdType.ECONOMIC_SIGNIFICANCE:
            return self.base_economic_threshold
        elif threshold_type == ThresholdType.SIGNAL_STRENGTH:
            return self.base_signal_threshold
        elif threshold_type == ThresholdType.EXECUTION_FEASIBILITY:
            return 0.5  # 50% confidence threshold
        elif threshold_type == ThresholdType.RISK_ADJUSTED:
            return self.base_economic_threshold * 2  # Higher threshold for risk
        else:
            return self.base_economic_threshold
    
    def _get_signal_value(self, signal: Dict[str, Any], threshold_type: ThresholdType) -> float:
        """Get signal value for comparison with threshold"""
        if threshold_type == ThresholdType.ECONOMIC_SIGNIFICANCE:
            # Calculate expected value
            economic_result = self.calculate_economic_significance(signal)
            return economic_result.net_expected_value
        elif threshold_type == ThresholdType.SIGNAL_STRENGTH:
            return abs(signal.get('q50', 0))
        elif threshold_type == ThresholdType.EXECUTION_FEASIBILITY:
            # Composite feasibility score
            tradeable = 1.0 if signal.get('tradeable', False) else 0.0
            high_quality = 1.0 if signal.get('high_quality', False) else 0.0
            economic_sig = 1.0 if signal.get('economically_significant', False) else 0.0
            return (tradeable + high_quality + economic_sig) / 3.0
        elif threshold_type == ThresholdType.RISK_ADJUSTED:
            q50_value = abs(signal.get('q50', 0))
            vol_risk = signal.get('vol_risk', 0.1)
            return q50_value / max(vol_risk, 0.01)  # Risk-adjusted return
        else:
            return 0.0
    
    def _calculate_price_impact_cost(self, pool_data: Optional[Dict[str, Any]], 
                                   position_size: float) -> float:
        """Calculate price impact cost for position size"""
        try:
            if not pool_data or position_size <= 0:
                return self.realistic_transaction_cost  # Default cost
            
            # Extract pool liquidity
            pool_liquidity = pool_data.get('reserve_sol', 0)
            if pool_liquidity <= 0:
                # Try USD conversion
                pool_liquidity_usd = pool_data.get('reserve_in_usd', 0)
                pool_liquidity = pool_liquidity_usd / 100  # Rough SOL conversion
            
            if pool_liquidity <= 0:
                return self.realistic_transaction_cost * 2  # Higher cost for unknown liquidity
            
            # Calculate price impact using constant product formula
            impact_ratio = position_size / (pool_liquidity + position_size)
            price_impact_percent = impact_ratio * 100
            
            # Apply impact curve (quadratic for larger trades)
            if price_impact_percent > 5:
                price_impact_percent *= (1 + (price_impact_percent - 5) * 0.1)
            
            # Convert to cost (percentage of position)
            price_impact_cost = min(price_impact_percent / 100, 0.2)  # Cap at 20%
            
            return price_impact_cost
            
        except Exception as e:
            logger.error(f"Error calculating price impact cost: {e}")
            return self.realistic_transaction_cost * 2  # Conservative fallback
    
    def _calculate_liquidity_adjustment(self, pool_data: Optional[Dict[str, Any]], 
                                      position_size: float) -> float:
        """Calculate liquidity-based threshold adjustment"""
        try:
            if not pool_data:
                return 0.5  # 50% penalty for no liquidity data
            
            pool_liquidity = pool_data.get('reserve_sol', 0)
            if pool_liquidity <= 0:
                pool_liquidity_usd = pool_data.get('reserve_in_usd', 0)
                pool_liquidity = pool_liquidity_usd / 100
            
            if pool_liquidity <= 0:
                return 0.5  # 50% penalty for unknown liquidity
            
            # Calculate liquidity factor
            if pool_liquidity >= self.optimal_liquidity_threshold:
                liquidity_factor = -0.2  # 20% bonus for excellent liquidity
            elif pool_liquidity >= self.min_liquidity_threshold * 2:
                liquidity_factor = -0.1  # 10% bonus for good liquidity
            elif pool_liquidity >= self.min_liquidity_threshold:
                liquidity_factor = 0.0  # No adjustment for minimum liquidity
            else:
                # Penalty for insufficient liquidity
                deficit_ratio = (self.min_liquidity_threshold - pool_liquidity) / self.min_liquidity_threshold
                liquidity_factor = deficit_ratio * 0.5  # Up to 50% penalty
            
            # Adjust based on position size relative to liquidity
            position_ratio = position_size / pool_liquidity
            if position_ratio > 0.25:  # More than 25% of pool
                liquidity_factor += position_ratio * 0.5  # Additional penalty
            
            return liquidity_factor * self.liquidity_impact_weight
            
        except Exception as e:
            logger.error(f"Error calculating liquidity adjustment: {e}")
            return 0.3  # Conservative penalty
    
    def _calculate_price_impact_adjustment(self, pool_data: Optional[Dict[str, Any]], 
                                         position_size: float) -> float:
        """Calculate price impact-based threshold adjustment"""
        try:
            price_impact_cost = self._calculate_price_impact_cost(pool_data, position_size)
            
            # Convert cost to threshold adjustment
            if price_impact_cost <= 0.01:  # Less than 1% impact
                return -0.1  # 10% bonus for low impact
            elif price_impact_cost <= 0.05:  # Less than 5% impact
                return 0.0  # No adjustment
            elif price_impact_cost <= 0.1:  # Less than 10% impact
                return 0.2  # 20% penalty
            else:
                # High impact penalty
                excess_impact = price_impact_cost - 0.1
                return 0.2 + (excess_impact * self.price_impact_penalty_factor)
            
        except Exception as e:
            logger.error(f"Error calculating price impact adjustment: {e}")
            return 0.2  # Conservative penalty
    
    def _calculate_variance_adjustment(self, signal: Dict[str, Any]) -> float:
        """Calculate variance-based threshold adjustment"""
        try:
            vol_risk = signal.get('vol_risk', 0.1)
            
            # Classify variance regime (using signal-specific percentiles if available)
            regime = self._classify_variance_regime(signal)
            
            # Apply regime-specific adjustment
            return self.regime_threshold_adjustments.get(regime, 0.0)
            
        except Exception as e:
            logger.error(f"Error calculating variance adjustment: {e}")
            return 0.0
    
    def _calculate_regime_adjustment(self, signal: Dict[str, Any]) -> float:
        """Calculate regime-based threshold adjustment"""
        try:
            regime_multiplier = signal.get('regime_multiplier', 1.0)
            
            # Convert multiplier to threshold adjustment
            # Higher multiplier means easier threshold (negative adjustment)
            if regime_multiplier > 1.2:
                return -0.1  # 10% easier threshold
            elif regime_multiplier > 1.0:
                return -0.05  # 5% easier threshold
            elif regime_multiplier < 0.8:
                return 0.2  # 20% harder threshold
            elif regime_multiplier < 1.0:
                return 0.1  # 10% harder threshold
            else:
                return 0.0  # No adjustment
            
        except Exception as e:
            logger.error(f"Error calculating regime adjustment: {e}")
            return 0.0
    
    def _classify_variance_regime(self, signal: Dict[str, Any]) -> str:
        """Classify variance regime for signal"""
        try:
            vol_risk = signal.get('vol_risk', 0.1)
            
            # Use global percentiles or signal-specific if available
            if 'vol_risk_percentile' in signal:
                percentile = signal['vol_risk_percentile']
                if percentile <= 0.30:
                    return 'low_variance'
                elif percentile <= 0.70:
                    return 'medium_variance'
                elif percentile <= 0.90:
                    return 'high_variance'
                else:
                    return 'extreme_variance'
            else:
                # Use absolute thresholds as fallback
                if vol_risk <= 0.05:
                    return 'low_variance'
                elif vol_risk <= 0.15:
                    return 'medium_variance'
                elif vol_risk <= 0.30:
                    return 'high_variance'
                else:
                    return 'extreme_variance'
                    
        except Exception as e:
            logger.error(f"Error classifying variance regime: {e}")
            return 'medium_variance'
    
    def _get_liquidity_factor(self, pool_data: Optional[Dict[str, Any]]) -> str:
        """Get liquidity factor classification"""
        if not pool_data:
            return 'no_data'
        
        pool_liquidity = pool_data.get('reserve_sol', 0)
        if pool_liquidity >= self.optimal_liquidity_threshold:
            return 'excellent'
        elif pool_liquidity >= self.min_liquidity_threshold * 2:
            return 'good'
        elif pool_liquidity >= self.min_liquidity_threshold:
            return 'adequate'
        else:
            return 'insufficient'
    
    def _get_price_impact_factor(self, pool_data: Optional[Dict[str, Any]], 
                                position_size: float) -> str:
        """Get price impact factor classification"""
        try:
            impact_cost = self._calculate_price_impact_cost(pool_data, position_size)
            
            if impact_cost <= 0.01:
                return 'minimal'
            elif impact_cost <= 0.05:
                return 'low'
            elif impact_cost <= 0.1:
                return 'moderate'
            else:
                return 'high'
                
        except Exception as e:
            return 'unknown'
    
    def _calculate_traditional_expected_value(self, signal: Dict[str, Any]) -> float:
        """Calculate traditional expected value for comparison"""
        try:
            q50_value = signal.get('q50', 0)
            prob_up = signal.get('prob_up', 0.5)
            
            potential_gain = abs(q50_value) - self.realistic_transaction_cost
            potential_loss = abs(q50_value) + self.realistic_transaction_cost
            
            expected_value = (prob_up * potential_gain) - ((1 - prob_up) * potential_loss)
            return expected_value
            
        except Exception as e:
            logger.error(f"Error calculating traditional expected value: {e}")
            return 0.0
    
    def get_calculation_summary(self) -> Dict[str, Any]:
        """Get summary of threshold calculations"""
        return {
            'total_calculations': self.calculation_count,
            'base_economic_threshold': self.base_economic_threshold,
            'base_signal_threshold': self.base_signal_threshold,
            'realistic_transaction_cost': self.realistic_transaction_cost,
            'liquidity_impact_weight': self.liquidity_impact_weight,
            'max_acceptable_impact': self.max_acceptable_impact,
            'variance_percentiles': self.variance_percentiles,
            'regime_adjustments': self.regime_threshold_adjustments,
            'cache_size': len(self.threshold_cache)
        }
    
    def clear_cache(self) -> None:
        """Clear the threshold calculation cache"""
        self.threshold_cache.clear()
        logger.info("AdaptiveThresholdCalculator cache cleared")