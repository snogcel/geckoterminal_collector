"""
Regime Detector for variance-based market regime classification.

This module provides the RegimeDetector class that implements variance-based
regime classification using existing vol_risk percentiles and applies
regime-specific threshold adjustments for enhanced Q50 signal processing.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Detects market volatility regimes based on variance measures.
    
    This class implements variance-based regime classification using vol_risk
    percentiles and applies regime-specific threshold adjustments to enhance
    Q50 signal quality and trading decisions.
    """
    
    # Default regime thresholds based on vol_risk percentiles
    DEFAULT_PERCENTILES = {
        'low': 0.30,
        'high': 0.70,
        'extreme': 0.90
    }
    
    # Default threshold adjustments for each regime
    DEFAULT_THRESHOLD_ADJUSTMENTS = {
        'low_variance': -0.30,      # Reduce thresholds in low volatility
        'medium_variance': 0.0,     # No adjustment in medium volatility
        'high_variance': 0.40,      # Increase thresholds in high volatility
        'extreme_variance': 0.80    # Significantly increase in extreme volatility
    }
    
    # Default regime multipliers for position sizing
    DEFAULT_REGIME_MULTIPLIERS = {
        'low_variance': 0.7,        # Reduce position size in low volatility
        'medium_variance': 1.0,     # Normal position size
        'high_variance': 1.4,       # Increase position size in high volatility
        'extreme_variance': 1.8     # Maximum increase in extreme volatility
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize RegimeDetector.
        
        Args:
            config: Configuration dictionary containing:
                - regime_detection.vol_risk_percentiles: Percentile thresholds
                - regime_detection.regime_multipliers: Position size multipliers
                - regime_detection.threshold_adjustments: Threshold adjustments (optional)
        """
        self.config = config
        
        # Load regime detection configuration
        regime_config = config.get('regime_detection', {})
        
        # Volatility risk percentiles for regime classification
        self.vol_risk_percentiles = regime_config.get(
            'vol_risk_percentiles', 
            self.DEFAULT_PERCENTILES
        )
        
        # Regime multipliers for position sizing
        self.regime_multipliers = regime_config.get(
            'regime_multipliers',
            self.DEFAULT_REGIME_MULTIPLIERS
        )
        
        # Threshold adjustments for each regime
        self.threshold_adjustments = regime_config.get(
            'threshold_adjustments',
            self.DEFAULT_THRESHOLD_ADJUSTMENTS
        )
        
        # Historical volatility data for percentile calculation
        self.vol_risk_history: List[float] = []
        self.percentile_cache: Optional[Dict[str, float]] = None
        self.cache_update_threshold = 100  # Update percentiles every N new observations
        
        logger.info("RegimeDetector initialized with percentiles: %s", self.vol_risk_percentiles)
    
    def classify_regime(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify the current market regime based on volatility risk.
        
        Args:
            signal_data: Dictionary containing signal data with 'vol_risk' key
            
        Returns:
            Dictionary containing regime classification and adjustments
        """
        try:
            vol_risk = signal_data.get('vol_risk', 0.0)
            
            if vol_risk is None or np.isnan(vol_risk):
                logger.warning("Invalid vol_risk value, defaulting to medium variance regime")
                vol_risk = 0.5  # Default to medium variance
            
            # Update volatility history for percentile calculation
            self._update_vol_risk_history(vol_risk)
            
            # Calculate current percentiles if needed
            current_percentiles = self._get_current_percentiles()
            
            # Classify regime based on vol_risk percentiles
            regime_info = self._classify_vol_risk_regime(vol_risk, current_percentiles)
            
            # Add enhanced regime analysis
            regime_info.update(self._calculate_regime_enhancements(signal_data, regime_info))
            
            logger.debug(f"Classified regime: {regime_info['regime']} (vol_risk: {vol_risk:.4f})")
            
            return regime_info
            
        except Exception as e:
            logger.error(f"Error in regime classification: {e}")
            return self._get_default_regime_info()
    
    def _classify_vol_risk_regime(self, vol_risk: float, percentiles: Dict[str, float]) -> Dict[str, Any]:
        """
        Classify regime based on vol_risk percentiles.
        
        Args:
            vol_risk: Current volatility risk value
            percentiles: Current percentile thresholds
            
        Returns:
            Dictionary containing basic regime classification
        """
        if vol_risk <= percentiles['low']:
            regime = 'low_variance'
        elif vol_risk <= percentiles['high']:
            regime = 'medium_variance'
        elif vol_risk <= percentiles['extreme']:
            regime = 'high_variance'
        else:
            regime = 'extreme_variance'
        
        return {
            'regime': regime,
            'vol_risk': vol_risk,
            'vol_risk_percentile': self._calculate_percentile_rank(vol_risk),
            'threshold_adjustment': self.threshold_adjustments.get(regime, 0.0),
            'regime_multiplier': self.regime_multipliers.get(regime, 1.0),
            'percentile_thresholds': percentiles.copy()
        }
    
    def _calculate_regime_enhancements(self, signal_data: Dict[str, Any], regime_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate enhanced regime-specific adjustments.
        
        Args:
            signal_data: Original signal data
            regime_info: Basic regime classification
            
        Returns:
            Dictionary containing enhanced regime adjustments
        """
        enhancements = {}
        
        try:
            # Enhanced info ratio calculation with regime adjustment
            q50_value = signal_data.get('q50', 0.0)
            vol_raw = signal_data.get('vol_raw', 0.1)
            vol_risk = regime_info['vol_risk']
            
            # Calculate market variance including regime effects
            market_variance = vol_raw + (vol_risk * regime_info['regime_multiplier'])
            prediction_variance = vol_risk * 0.1  # Assume 10% of vol_risk as prediction uncertainty
            
            # Enhanced info ratio with regime adjustment
            if market_variance + prediction_variance > 0:
                enhanced_info_ratio = abs(q50_value) / np.sqrt(market_variance + prediction_variance)
            else:
                enhanced_info_ratio = 0.0
            
            enhancements['enhanced_info_ratio'] = enhanced_info_ratio
            enhancements['market_variance'] = market_variance
            enhancements['prediction_variance'] = prediction_variance
            
            # Regime-adjusted economic significance threshold
            base_threshold = 0.0005  # 5 bps base threshold
            regime_adjusted_threshold = base_threshold * (1 + regime_info['threshold_adjustment'])
            enhancements['regime_adjusted_threshold'] = regime_adjusted_threshold
            
            # Calculate regime-adjusted signal strength
            signal_strength = abs(q50_value) * regime_info['regime_multiplier']
            enhancements['regime_adjusted_signal_strength'] = signal_strength
            
            # Regime confidence score based on historical data
            confidence_score = self._calculate_regime_confidence(regime_info['regime'])
            enhancements['regime_confidence'] = confidence_score
            
        except Exception as e:
            logger.error(f"Error calculating regime enhancements: {e}")
            enhancements['error'] = str(e)
        
        return enhancements
    
    def _update_vol_risk_history(self, vol_risk: float) -> None:
        """
        Update the historical volatility risk data for percentile calculation.
        
        Args:
            vol_risk: New volatility risk observation
        """
        self.vol_risk_history.append(vol_risk)
        
        # Limit history size to prevent memory issues
        max_history_size = 10000
        if len(self.vol_risk_history) > max_history_size:
            self.vol_risk_history = self.vol_risk_history[-max_history_size:]
        
        # Invalidate percentile cache if we have enough new observations
        if len(self.vol_risk_history) % self.cache_update_threshold == 0:
            self.percentile_cache = None
    
    def _get_current_percentiles(self) -> Dict[str, float]:
        """
        Get current percentile thresholds, calculating from history if available.
        
        Returns:
            Dictionary containing current percentile thresholds
        """
        # Use cached percentiles if available and recent
        if self.percentile_cache is not None:
            return self.percentile_cache
        
        # Calculate percentiles from historical data if we have enough observations
        if len(self.vol_risk_history) >= 100:  # Need minimum observations for reliable percentiles
            try:
                vol_risk_array = np.array(self.vol_risk_history)
                calculated_percentiles = {
                    'low': float(np.percentile(vol_risk_array, self.vol_risk_percentiles['low'] * 100)),
                    'high': float(np.percentile(vol_risk_array, self.vol_risk_percentiles['high'] * 100)),
                    'extreme': float(np.percentile(vol_risk_array, self.vol_risk_percentiles['extreme'] * 100))
                }
                
                # Cache the calculated percentiles
                self.percentile_cache = calculated_percentiles
                
                logger.debug(f"Updated percentiles from {len(self.vol_risk_history)} observations: {calculated_percentiles}")
                
                return calculated_percentiles
                
            except Exception as e:
                logger.error(f"Error calculating percentiles from history: {e}")
        
        # Fall back to default percentiles (treating them as absolute values)
        return {
            'low': self.vol_risk_percentiles['low'],
            'high': self.vol_risk_percentiles['high'],
            'extreme': self.vol_risk_percentiles['extreme']
        }
    
    def _calculate_percentile_rank(self, vol_risk: float) -> float:
        """
        Calculate the percentile rank of the current vol_risk value.
        
        Args:
            vol_risk: Current volatility risk value
            
        Returns:
            Percentile rank (0-100)
        """
        if len(self.vol_risk_history) < 10:
            return 50.0  # Default to median if insufficient history
        
        try:
            vol_risk_array = np.array(self.vol_risk_history)
            percentile_rank = (vol_risk_array < vol_risk).mean() * 100
            return float(percentile_rank)
        except Exception as e:
            logger.error(f"Error calculating percentile rank: {e}")
            return 50.0
    
    def _calculate_regime_confidence(self, regime: str) -> float:
        """
        Calculate confidence score for the current regime classification.
        
        Args:
            regime: Current regime classification
            
        Returns:
            Confidence score (0-1)
        """
        if len(self.vol_risk_history) < 50:
            return 0.5  # Low confidence with insufficient history
        
        try:
            # Calculate regime stability over recent history
            recent_history = self.vol_risk_history[-50:]  # Last 50 observations
            recent_regimes = []
            
            for vol_risk in recent_history:
                temp_regime_info = self._classify_vol_risk_regime(vol_risk, self._get_current_percentiles())
                recent_regimes.append(temp_regime_info['regime'])
            
            # Calculate regime consistency
            regime_counts = pd.Series(recent_regimes).value_counts()
            current_regime_frequency = regime_counts.get(regime, 0) / len(recent_regimes)
            
            # Confidence based on regime consistency and transition smoothness
            confidence = min(current_regime_frequency * 1.5, 1.0)  # Cap at 1.0
            
            return float(confidence)
            
        except Exception as e:
            logger.error(f"Error calculating regime confidence: {e}")
            return 0.5
    
    def _get_default_regime_info(self) -> Dict[str, Any]:
        """
        Get default regime information for error cases.
        
        Returns:
            Dictionary containing default regime classification
        """
        return {
            'regime': 'medium_variance',
            'vol_risk': 0.5,
            'vol_risk_percentile': 50.0,
            'threshold_adjustment': 0.0,
            'regime_multiplier': 1.0,
            'enhanced_info_ratio': 0.0,
            'market_variance': 0.1,
            'prediction_variance': 0.05,
            'regime_adjusted_threshold': 0.0005,
            'regime_adjusted_signal_strength': 0.0,
            'regime_confidence': 0.5,
            'percentile_thresholds': self.vol_risk_percentiles.copy(),
            'error': 'Using default regime due to classification error'
        }
    
    def apply_regime_adjustments(self, signal_data: Dict[str, Any], regime_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply regime-specific adjustments to signal data.
        
        Args:
            signal_data: Original signal data
            regime_info: Regime classification information
            
        Returns:
            Dictionary containing regime-adjusted signal data
        """
        try:
            adjusted_signal = signal_data.copy()
            
            # Apply threshold adjustments to economic significance calculation
            prob_up = signal_data.get('prob_up', 0.5)
            q50_value = signal_data.get('q50', 0.0)
            
            # Calculate regime-adjusted expected value
            potential_gain = abs(q50_value) if q50_value > 0 else 0
            potential_loss = abs(q50_value) if q50_value < 0 else 0
            
            expected_value = (prob_up * potential_gain) - ((1 - prob_up) * potential_loss)
            regime_adjusted_threshold = regime_info.get('regime_adjusted_threshold', 0.0005)
            
            # Update economic significance with regime adjustment
            adjusted_signal['regime_adjusted_economically_significant'] = expected_value > regime_adjusted_threshold
            
            # Update signal strength with regime multiplier
            adjusted_signal['regime_adjusted_signal_strength'] = regime_info.get('regime_adjusted_signal_strength', 0.0)
            
            # Add regime information to signal
            adjusted_signal['regime_info'] = regime_info
            
            # Determine if signal is tradeable with regime considerations
            original_tradeable = signal_data.get('tradeable', False)
            regime_confidence = regime_info.get('regime_confidence', 0.5)
            
            # Require higher confidence in extreme regimes
            min_confidence_threshold = 0.3 if regime_info['regime'] != 'extreme_variance' else 0.6
            
            adjusted_signal['regime_adjusted_tradeable'] = (
                original_tradeable and 
                regime_confidence >= min_confidence_threshold and
                adjusted_signal['regime_adjusted_economically_significant']
            )
            
            return adjusted_signal
            
        except Exception as e:
            logger.error(f"Error applying regime adjustments: {e}")
            # Return original signal with error information
            error_signal = signal_data.copy()
            error_signal['regime_adjustment_error'] = str(e)
            error_signal['regime_info'] = regime_info
            return error_signal
    
    def get_regime_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about regime classification history.
        
        Returns:
            Dictionary containing regime statistics
        """
        if not self.vol_risk_history:
            return {'status': 'no_history'}
        
        try:
            # Calculate regime distribution
            regime_counts = {}
            percentiles = self._get_current_percentiles()
            
            for vol_risk in self.vol_risk_history:
                regime_info = self._classify_vol_risk_regime(vol_risk, percentiles)
                regime = regime_info['regime']
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            total_observations = len(self.vol_risk_history)
            regime_distribution = {
                regime: count / total_observations 
                for regime, count in regime_counts.items()
            }
            
            # Calculate volatility statistics
            vol_risk_array = np.array(self.vol_risk_history)
            
            return {
                'total_observations': total_observations,
                'regime_distribution': regime_distribution,
                'current_percentiles': percentiles,
                'vol_risk_stats': {
                    'mean': float(np.mean(vol_risk_array)),
                    'std': float(np.std(vol_risk_array)),
                    'min': float(np.min(vol_risk_array)),
                    'max': float(np.max(vol_risk_array)),
                    'median': float(np.median(vol_risk_array))
                },
                'cache_status': 'cached' if self.percentile_cache is not None else 'calculated'
            }
            
        except Exception as e:
            logger.error(f"Error calculating regime statistics: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def reset_history(self) -> None:
        """Reset volatility history and clear caches."""
        self.vol_risk_history.clear()
        self.percentile_cache = None
        logger.info("Regime detector history reset")
    
    def load_historical_data(self, vol_risk_data: List[float]) -> None:
        """
        Load historical volatility risk data for better regime classification.
        
        Args:
            vol_risk_data: List of historical vol_risk values
        """
        try:
            # Validate and clean data
            cleaned_data = [
                float(val) for val in vol_risk_data 
                if val is not None and not np.isnan(val) and np.isfinite(val)
            ]
            
            self.vol_risk_history.extend(cleaned_data)
            self.percentile_cache = None  # Invalidate cache
            
            logger.info(f"Loaded {len(cleaned_data)} historical vol_risk observations")
            
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")