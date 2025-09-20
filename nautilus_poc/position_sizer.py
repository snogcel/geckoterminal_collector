"""
Kelly Position Sizing with Liquidity Constraints

This module implements the Kelly criterion-based position sizing with variance scaling,
regime adjustments, and PumpSwap liquidity constraints as specified in requirements 3.1-3.4, 3.7.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class PositionSizeResult:
    """Result of position size calculation"""
    recommended_size: float
    base_size: float
    signal_multiplier: float
    regime_multiplier: float
    liquidity_constraint: float
    final_size: float
    reasoning: str
    constraints_applied: list

class KellyPositionSizer:
    """
    Kelly criterion-based position sizer with liquidity constraints
    
    Implements inverse variance scaling with signal strength enhancement,
    regime-based adjustments, and PumpSwap liquidity validation.
    """
    
    def __init__(self, config):
        """
        Initialize Kelly position sizer
        
        Args:
            config: Configuration (NautilusPOCConfig object or dictionary)
        """
        self.config = config
        
        # Handle both NautilusPOCConfig objects and dictionaries
        if hasattr(config, 'pumpswap'):
            # NautilusPOCConfig object
            self.pumpswap_config = {
                'base_position_size': config.pumpswap.base_position_size,
                'max_position_size': config.pumpswap.max_position_size,
                'max_slippage_percent': config.pumpswap.max_slippage_percent,
                'min_liquidity_sol': config.pumpswap.min_liquidity_sol,
                'max_price_impact_percent': config.pumpswap.max_price_impact_percent
            }
            self.regime_config = config.regime_detection if hasattr(config, 'regime_detection') else {}
        else:
            # Dictionary config
            self.pumpswap_config = config.get('pumpswap', {})
            self.regime_config = config.get('regime_detection', {})
        
        # Position sizing parameters
        self.base_position_factor = self.pumpswap_config.get('base_position_size', 0.1)
        self.max_position_size = self.pumpswap_config.get('max_position_size', 0.5)
        self.min_position_size = 0.01  # Minimum 1% position
        self.max_pool_utilization = 0.25  # Maximum 25% of pool liquidity
        
        # Signal strength parameters
        self.max_signal_multiplier = 2.0
        self.info_ratio_threshold = self.regime_config.get('effective_info_ratio_threshold', 1.0)
        
        # Variance scaling parameters
        self.variance_scale_factor = 1000
        self.min_variance_divisor = 0.1
        
        logger.info("KellyPositionSizer initialized with config")
    
    def calculate_position_size(
        self, 
        signal_data: Dict[str, Any], 
        pool_data: Optional[Dict[str, Any]] = None,
        current_balance: Optional[float] = None
    ) -> PositionSizeResult:
        """
        Calculate position size using Kelly criterion with liquidity constraints
        
        Args:
            signal_data: Q50 signal data with regime information
            pool_data: PumpSwap pool liquidity data
            current_balance: Current wallet balance in SOL
            
        Returns:
            PositionSizeResult with detailed calculation breakdown
        """
        try:
            # Step 1: Calculate base size using inverse variance scaling
            base_size = self._calculate_base_size(signal_data)
            
            # Step 2: Calculate signal strength multiplier
            signal_multiplier = self._calculate_signal_multiplier(signal_data)
            
            # Step 3: Apply regime multiplier
            regime_multiplier = self._get_regime_multiplier(signal_data)
            
            # Step 4: Calculate raw Kelly position
            raw_position = base_size * signal_multiplier * regime_multiplier
            
            # Step 5: Apply liquidity constraints
            liquidity_constraint, pool_constraint_reason = self._apply_liquidity_constraints(
                raw_position, pool_data
            )
            
            # Step 6: Apply position limits and balance constraints
            final_size, constraints_applied = self._apply_position_limits(
                liquidity_constraint, current_balance
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                base_size, signal_multiplier, regime_multiplier, 
                raw_position, liquidity_constraint, final_size
            )
            
            # Track constraints applied
            all_constraints = []
            if pool_constraint_reason:
                all_constraints.append(pool_constraint_reason)
            all_constraints.extend(constraints_applied)
            
            result = PositionSizeResult(
                recommended_size=raw_position,
                base_size=base_size,
                signal_multiplier=signal_multiplier,
                regime_multiplier=regime_multiplier,
                liquidity_constraint=liquidity_constraint,
                final_size=final_size,
                reasoning=reasoning,
                constraints_applied=all_constraints
            )
            
            logger.info(f"Position size calculated: {final_size:.4f} SOL (base: {base_size:.4f}, "
                       f"signal: {signal_multiplier:.2f}x, regime: {regime_multiplier:.2f}x)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return safe default position
            return PositionSizeResult(
                recommended_size=self.base_position_factor,
                base_size=self.base_position_factor,
                signal_multiplier=1.0,
                regime_multiplier=1.0,
                liquidity_constraint=self.base_position_factor,
                final_size=self.base_position_factor,
                reasoning=f"Error in calculation, using default: {e}",
                constraints_applied=["error_fallback"]
            )
    
    def _calculate_base_size(self, signal_data: Dict[str, Any]) -> float:
        """
        Calculate base position size using inverse variance scaling
        
        Formula: base_size = 0.1 / max(vol_risk * 1000, 0.1)
        
        Args:
            signal_data: Signal data containing vol_risk
            
        Returns:
            Base position size
        """
        vol_risk = signal_data.get('vol_risk', 0.1)
        
        # Apply inverse variance scaling as per requirement 3.1
        variance_divisor = max(vol_risk * self.variance_scale_factor, self.min_variance_divisor)
        base_size = self.base_position_factor / variance_divisor
        
        # Ensure base size is within reasonable bounds
        base_size = max(min(base_size, self.max_position_size), self.min_position_size)
        
        logger.debug(f"Base size calculation: vol_risk={vol_risk:.4f}, "
                    f"divisor={variance_divisor:.4f}, base_size={base_size:.4f}")
        
        return base_size
    
    def _calculate_signal_multiplier(self, signal_data: Dict[str, Any]) -> float:
        """
        Calculate signal strength multiplier with enhanced info ratio
        
        Args:
            signal_data: Signal data containing q50 and enhanced_info_ratio
            
        Returns:
            Signal strength multiplier (capped at max_signal_multiplier)
        """
        q50_value = abs(signal_data.get('q50', 0))
        enhanced_info_ratio = signal_data.get('enhanced_info_ratio', 1.0)
        
        # Calculate signal strength as per requirement 3.2
        if self.info_ratio_threshold > 0:
            info_ratio_factor = min(
                enhanced_info_ratio / self.info_ratio_threshold, 
                self.max_signal_multiplier
            )
        else:
            info_ratio_factor = 1.0
        
        # Combine Q50 strength with info ratio
        signal_strength = q50_value * info_ratio_factor
        signal_multiplier = min(signal_strength, self.max_signal_multiplier)
        
        logger.debug(f"Signal multiplier: q50={q50_value:.4f}, "
                    f"info_ratio={enhanced_info_ratio:.4f}, multiplier={signal_multiplier:.4f}")
        
        return max(signal_multiplier, 0.1)  # Minimum multiplier
    
    def _get_regime_multiplier(self, signal_data: Dict[str, Any]) -> float:
        """
        Get regime multiplier based on variance percentiles
        
        Args:
            signal_data: Signal data containing regime information
            
        Returns:
            Regime-based multiplier
        """
        regime = signal_data.get('regime', 'medium_variance')
        regime_multiplier = signal_data.get('regime_multiplier', 1.0)
        
        # Use regime multiplier from signal data if available
        if regime_multiplier and regime_multiplier > 0:
            final_multiplier = regime_multiplier
        else:
            # Fallback to default regime multipliers
            regime_multipliers = {
                'low_variance': 0.7,      # -30% adjustment
                'medium_variance': 1.0,   # No adjustment
                'high_variance': 1.4,     # +40% adjustment
                'extreme_variance': 1.8   # +80% adjustment
            }
            final_multiplier = regime_multipliers.get(regime, 1.0)
        
        logger.debug(f"Regime multiplier: regime={regime}, multiplier={final_multiplier:.2f}")
        
        return final_multiplier
    
    def _apply_liquidity_constraints(
        self, 
        position_size: float, 
        pool_data: Optional[Dict[str, Any]]
    ) -> Tuple[float, Optional[str]]:
        """
        Apply PumpSwap liquidity constraints
        
        Args:
            position_size: Calculated position size
            pool_data: Pool liquidity data
            
        Returns:
            Tuple of (constrained_position_size, constraint_reason)
        """
        if not pool_data:
            logger.warning("No pool data available, using original position size")
            return position_size, None
        
        # Extract pool liquidity in SOL (rough conversion from USD)
        pool_liquidity_usd = pool_data.get('reserve_in_usd', 0)
        pool_liquidity_sol = pool_liquidity_usd / 100  # Rough USD to SOL conversion
        
        if pool_liquidity_sol <= 0:
            logger.warning("Invalid pool liquidity data, using original position size")
            return position_size, None
        
        # Apply maximum pool utilization constraint (25% of pool)
        max_position_by_liquidity = pool_liquidity_sol * self.max_pool_utilization
        
        if position_size > max_position_by_liquidity:
            constrained_size = max_position_by_liquidity
            constraint_reason = f"liquidity_cap_25%_of_{pool_liquidity_sol:.2f}_SOL"
            
            logger.info(f"Position size constrained by liquidity: "
                       f"{position_size:.4f} -> {constrained_size:.4f} SOL")
            
            return constrained_size, constraint_reason
        
        return position_size, None
    
    def _apply_position_limits(
        self, 
        position_size: float, 
        current_balance: Optional[float]
    ) -> Tuple[float, list]:
        """
        Apply position size limits and balance constraints
        
        Args:
            position_size: Position size after liquidity constraints
            current_balance: Current wallet balance
            
        Returns:
            Tuple of (final_position_size, constraints_applied)
        """
        constraints_applied = []
        final_size = position_size
        
        # Apply maximum position size limit
        if final_size > self.max_position_size:
            final_size = self.max_position_size
            constraints_applied.append(f"max_position_cap_{self.max_position_size}")
        
        # Apply minimum position size limit
        if final_size < self.min_position_size:
            final_size = self.min_position_size
            constraints_applied.append(f"min_position_floor_{self.min_position_size}")
        
        # Apply balance constraints if available
        if current_balance is not None:
            # Reserve some balance for transaction fees
            fee_reserve = 0.01  # Reserve 0.01 SOL for fees
            available_balance = max(current_balance - fee_reserve, 0)
            
            if final_size > available_balance:
                final_size = available_balance
                constraints_applied.append(f"balance_limit_{available_balance:.4f}_SOL")
            
            # Ensure we don't use more than 90% of available balance
            max_balance_usage = available_balance * 0.9
            if final_size > max_balance_usage:
                final_size = max_balance_usage
                constraints_applied.append(f"balance_safety_90%_{max_balance_usage:.4f}_SOL")
        
        return max(final_size, 0), constraints_applied
    
    def _generate_reasoning(
        self, 
        base_size: float, 
        signal_multiplier: float, 
        regime_multiplier: float,
        raw_position: float, 
        liquidity_constraint: float, 
        final_size: float
    ) -> str:
        """Generate human-readable reasoning for position size calculation"""
        reasoning_parts = [
            f"Base size (inverse variance): {base_size:.4f} SOL",
            f"Signal strength multiplier: {signal_multiplier:.2f}x",
            f"Regime adjustment: {regime_multiplier:.2f}x",
            f"Raw Kelly position: {raw_position:.4f} SOL"
        ]
        
        if liquidity_constraint != raw_position:
            reasoning_parts.append(f"After liquidity constraints: {liquidity_constraint:.4f} SOL")
        
        if final_size != liquidity_constraint:
            reasoning_parts.append(f"Final position (after limits): {final_size:.4f} SOL")
        
        return " | ".join(reasoning_parts)
    
    def validate_signal_data(self, signal_data: Dict[str, Any]) -> bool:
        """
        Validate that signal data contains required fields for position sizing
        
        Args:
            signal_data: Signal data to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['q50', 'vol_risk', 'tradeable']
        optional_fields = ['enhanced_info_ratio', 'regime', 'regime_multiplier']
        
        missing_required = [field for field in required_fields if field not in signal_data]
        
        if missing_required:
            logger.error(f"Missing required signal fields: {missing_required}")
            return False
        
        # Check for reasonable values
        vol_risk = signal_data.get('vol_risk', 0)
        if vol_risk <= 0:
            logger.warning("vol_risk is zero or negative, using minimum value")
        
        q50 = signal_data.get('q50', 0)
        if abs(q50) > 1:
            logger.warning(f"q50 value seems unusually large: {q50}")
        
        return True
    
    def get_position_size_summary(self, result: PositionSizeResult) -> Dict[str, Any]:
        """
        Get a summary of position size calculation for logging/monitoring
        
        Args:
            result: Position size calculation result
            
        Returns:
            Summary dictionary
        """
        return {
            'final_position_size_sol': result.final_size,
            'base_size_sol': result.base_size,
            'signal_multiplier': result.signal_multiplier,
            'regime_multiplier': result.regime_multiplier,
            'recommended_size_sol': result.recommended_size,
            'constraints_applied': result.constraints_applied,
            'reasoning': result.reasoning
        }