"""
Liquidity Validation Component for PumpSwap Integration

This module provides the LiquidityValidator class that validates pool liquidity
and execution feasibility for PumpSwap DEX trades.
"""

import logging
import math
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import NautilusPOCConfig

logger = logging.getLogger(__name__)

class LiquidityStatus(Enum):
    """Liquidity validation status"""
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    NO_DATA = "no_data"
    EXCESSIVE_IMPACT = "excessive_impact"
    PAIR_NOT_FOUND = "pair_not_found"

@dataclass
class LiquidityValidationResult:
    """Result of liquidity validation"""
    status: LiquidityStatus
    is_valid: bool
    pool_liquidity_sol: float
    pool_liquidity_usd: float
    estimated_price_impact: float
    max_trade_size_sol: float
    recommended_trade_size_sol: float
    validation_details: Dict[str, Any]
    error_message: Optional[str] = None

class LiquidityValidator:
    """
    Validate PumpSwap pool liquidity for trade execution
    
    Key Responsibilities:
    - Check pool liquidity sufficiency using get_pool_data()
    - Implement price impact estimation for trade sizing
    - Add execution feasibility checks with get_pair_address()
    - Validate minimum liquidity requirements before trade execution
    """
    
    def __init__(self, config: NautilusPOCConfig):
        """Initialize liquidity validator with configuration"""
        self.config = config
        # env_config = config.get_current_env_config()
        # self.min_liquidity_sol = env_config.pumpswap.min_liquidity_sol
        # self.max_price_impact = env_config.pumpswap.max_price_impact_percent
        # self.max_position_size = env_config.pumpswap.max_position_size

        self.min_liquidity_sol = 1 # Hard Code for Testing
        self.max_price_impact = 1 # Hard Code for Testing
        self.max_position_size = 1 # Hard Code for Testing
        
        # Price impact calculation parameters
        self.price_impact_model = config.regime_detection.get('price_impact_model', 'constant_product')
        # self.slippage_tolerance = env_config.pumpswap.max_slippage_percent
        
        # Liquidity quality thresholds
        self.min_volume_24h = config.monitoring.get('min_volume_24h', 1000)  # Minimum $1k daily volume
        self.min_trade_count = config.monitoring.get('min_trade_count', 10)  # Minimum trades per day
        
        logger.info(f"LiquidityValidator initialized with min_liquidity={self.min_liquidity_sol} SOL, "
                   f"max_impact={self.max_price_impact}%")
    
    def validate_buy_liquidity(self, pool_data: Dict[str, Any], signal: Dict[str, Any]) -> bool:
        """
        Validate pool has sufficient liquidity for buy order
        
        Args:
            pool_data: Pool data from PumpSwap SDK get_pool_data()
            signal: Q50 signal data with position sizing information
            
        Returns:
            bool: True if liquidity is sufficient for trade execution
        """
        try:
            validation_result = self.validate_liquidity_detailed(pool_data, signal, 'buy')
            return validation_result.is_valid
            
        except Exception as e:
            logger.error(f"Error validating buy liquidity: {e}")
            return False
    
    def validate_sell_liquidity(self, pool_data: Dict[str, Any], signal: Dict[str, Any], 
                               position_size: float) -> bool:
        """
        Validate pool has sufficient liquidity for sell order
        
        Args:
            pool_data: Pool data from PumpSwap SDK get_pool_data()
            signal: Q50 signal data
            position_size: Size of position to sell (in tokens)
            
        Returns:
            bool: True if liquidity is sufficient for sell execution
        """
        try:
            # Convert token amount to SOL equivalent for validation
            current_price = pool_data.get('price', 0)
            if current_price <= 0:
                logger.warning("Invalid price data for sell validation")
                return False
            
            sol_equivalent = position_size * current_price
            
            # Create modified signal for sell validation
            sell_signal = {**signal, 'estimated_position_size': sol_equivalent}
            
            validation_result = self.validate_liquidity_detailed(pool_data, sell_signal, 'sell')
            return validation_result.is_valid
            
        except Exception as e:
            logger.error(f"Error validating sell liquidity: {e}")
            return False
    
    def validate_liquidity_detailed(self, pool_data: Dict[str, Any], signal: Dict[str, Any], 
                                  trade_type: str = 'buy') -> LiquidityValidationResult:
        """
        Perform detailed liquidity validation with comprehensive analysis
        
        Args:
            pool_data: Pool data from PumpSwap SDK
            signal: Q50 signal data
            trade_type: 'buy' or 'sell'
            
        Returns:
            LiquidityValidationResult with detailed validation information
        """
        try:
            # Check if pool data is available
            if not pool_data:
                return LiquidityValidationResult(
                    status=LiquidityStatus.NO_DATA,
                    is_valid=False,
                    pool_liquidity_sol=0,
                    pool_liquidity_usd=0,
                    estimated_price_impact=100.0,
                    max_trade_size_sol=0,
                    recommended_trade_size_sol=0,
                    validation_details={'error': 'No pool data available'},
                    error_message="Pool data not available"
                )
            
            # Extract pool information
            pool_liquidity_sol = self._extract_pool_liquidity_sol(pool_data)
            pool_liquidity_usd = pool_data.get('reserve_in_usd', 0)
            current_price = pool_data.get('price', 0)
            volume_24h = pool_data.get('volume_24h', 0)
            
            # Get estimated trade size
            estimated_trade_size = self._get_estimated_trade_size(signal, pool_data)
            
            # Validate minimum liquidity requirement
            if pool_liquidity_sol < self.min_liquidity_sol:
                return LiquidityValidationResult(
                    status=LiquidityStatus.INSUFFICIENT,
                    is_valid=False,
                    pool_liquidity_sol=pool_liquidity_sol,
                    pool_liquidity_usd=pool_liquidity_usd,
                    estimated_price_impact=100.0,
                    max_trade_size_sol=0,
                    recommended_trade_size_sol=0,
                    validation_details={
                        'required_liquidity': self.min_liquidity_sol,
                        'actual_liquidity': pool_liquidity_sol,
                        'deficit': self.min_liquidity_sol - pool_liquidity_sol
                    },
                    error_message=f"Insufficient liquidity: {pool_liquidity_sol:.2f} < {self.min_liquidity_sol:.2f} SOL"
                )
            
            # Calculate price impact
            price_impact = self._estimate_price_impact(pool_data, estimated_trade_size, trade_type)
            
            # Check price impact threshold
            if price_impact > self.max_price_impact:
                return LiquidityValidationResult(
                    status=LiquidityStatus.EXCESSIVE_IMPACT,
                    is_valid=False,
                    pool_liquidity_sol=pool_liquidity_sol,
                    pool_liquidity_usd=pool_liquidity_usd,
                    estimated_price_impact=price_impact,
                    max_trade_size_sol=self._calculate_max_trade_size(pool_data),
                    recommended_trade_size_sol=self._calculate_recommended_trade_size(pool_data),
                    validation_details={
                        'max_allowed_impact': self.max_price_impact,
                        'estimated_impact': price_impact,
                        'trade_size': estimated_trade_size
                    },
                    error_message=f"Price impact too high: {price_impact:.2f}% > {self.max_price_impact}%"
                )
            
            # Validate pool quality metrics
            quality_check = self._validate_pool_quality(pool_data)
            
            # Calculate optimal trade sizes
            max_trade_size = self._calculate_max_trade_size(pool_data)
            recommended_trade_size = min(
                self._calculate_recommended_trade_size(pool_data),
                estimated_trade_size
            )
            
            # All validations passed
            return LiquidityValidationResult(
                status=LiquidityStatus.SUFFICIENT,
                is_valid=True,
                pool_liquidity_sol=pool_liquidity_sol,
                pool_liquidity_usd=pool_liquidity_usd,
                estimated_price_impact=price_impact,
                max_trade_size_sol=max_trade_size,
                recommended_trade_size_sol=recommended_trade_size,
                validation_details={
                    'trade_type': trade_type,
                    'estimated_trade_size': estimated_trade_size,
                    'pool_quality': quality_check,
                    'current_price': current_price,
                    'volume_24h': volume_24h,
                    'liquidity_utilization': (estimated_trade_size / pool_liquidity_sol) * 100
                }
            )
            
        except Exception as e:
            logger.error(f"Error in detailed liquidity validation: {e}")
            return LiquidityValidationResult(
                status=LiquidityStatus.NO_DATA,
                is_valid=False,
                pool_liquidity_sol=0,
                pool_liquidity_usd=0,
                estimated_price_impact=100.0,
                max_trade_size_sol=0,
                recommended_trade_size_sol=0,
                validation_details={'error': str(e)},
                error_message=f"Validation error: {str(e)}"
            )
    
    def check_pair_availability(self, mint_address: str, pair_address: Optional[str]) -> bool:
        """
        Check if trading pair is available and valid
        
        Args:
            mint_address: Token mint address
            pair_address: Pair address from get_pair_address()
            
        Returns:
            bool: True if pair is available for trading
        """
        try:
            if not pair_address:
                logger.warning(f"No pair address found for mint {mint_address}")
                return False
            
            # Validate pair address format (basic check)
            if len(pair_address) < 32:  # Solana addresses are typically 32+ characters
                logger.warning(f"Invalid pair address format: {pair_address}")
                return False
            
            # Additional pair validation could be added here
            # - Check if pair is active
            # - Validate pair contract
            # - Check for any trading restrictions
            
            logger.debug(f"Pair validation passed for {mint_address}: {pair_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking pair availability: {e}")
            return False
    
    def _extract_pool_liquidity_sol(self, pool_data: Dict[str, Any]) -> float:
        """Extract SOL liquidity from pool data"""
        # Try direct SOL reserve first
        if 'reserve_sol' in pool_data:
            return float(pool_data['reserve_sol'])
        
        # Try to convert from USD
        if 'reserve_in_usd' in pool_data:
            usd_reserve = float(pool_data['reserve_in_usd'])
            # Rough SOL price estimate (this should be improved with real price feed)
            estimated_sol_price = 100.0  # $100 per SOL estimate
            return usd_reserve / estimated_sol_price
        
        # Fallback: try to extract from other fields
        if 'liquidity' in pool_data:
            return float(pool_data['liquidity'])
        
        logger.warning("Could not extract SOL liquidity from pool data")
        return 0.0
    
    def _get_estimated_trade_size(self, signal: Dict[str, Any], pool_data: Dict[str, Any]) -> float:
        """Get estimated trade size from signal or calculate default"""
        # Try to get from signal first
        if 'estimated_position_size' in signal:
            return float(signal['estimated_position_size'])
        
        # Calculate based on signal strength and base position size
        q50_value = abs(signal.get('q50', 0))
        vol_risk = signal.get('vol_risk', 0.1)
        
        # Use Kelly sizing logic
        base_size = 0.1 / max(vol_risk * 1000, 0.1)
        signal_multiplier = min(q50_value * 100, 2.0)
        
        estimated_size = base_size * signal_multiplier
        
        # Apply configuration limits
        estimated_size = min(estimated_size, self.max_position_size)
        estimated_size = max(estimated_size, 0.01)  # Minimum trade size
        
        return estimated_size
    
    def _estimate_price_impact(self, pool_data: Dict[str, Any], trade_size_sol: float, 
                              trade_type: str = 'buy') -> float:
        """
        Estimate price impact for given trade size
        
        Uses constant product market maker model: x * y = k
        Price impact = (trade_size / (reserve + trade_size)) for buys
        """
        try:
            pool_liquidity = self._extract_pool_liquidity_sol(pool_data)
            
            if pool_liquidity <= 0:
                return 100.0  # Maximum impact if no liquidity data
            
            if trade_size_sol <= 0:
                return 0.0
            
            # Constant product AMM price impact calculation
            if trade_type == 'buy':
                # For buys: impact increases as we consume liquidity
                impact_ratio = trade_size_sol / (pool_liquidity + trade_size_sol)
            else:
                # For sells: impact based on adding liquidity back
                impact_ratio = trade_size_sol / pool_liquidity
            
            # Convert to percentage and apply impact curve
            # Real AMMs have non-linear impact curves
            price_impact = impact_ratio * 100
            
            # Apply impact curve (quadratic for larger trades)
            if price_impact > 5:
                price_impact = price_impact * (1 + (price_impact - 5) * 0.1)
            
            return min(price_impact, 100.0)  # Cap at 100%
            
        except Exception as e:
            logger.error(f"Error estimating price impact: {e}")
            return 100.0  # Conservative estimate on error
    
    def _calculate_max_trade_size(self, pool_data: Dict[str, Any]) -> float:
        """Calculate maximum feasible trade size based on price impact limits"""
        try:
            pool_liquidity = self._extract_pool_liquidity_sol(pool_data)
            
            if pool_liquidity <= 0:
                return 0.0
            
            # Binary search for max trade size that stays under impact limit
            low, high = 0.0, pool_liquidity * 0.5  # Start with max 50% of pool
            tolerance = 0.001  # 0.1% tolerance
            
            while high - low > tolerance:
                mid = (low + high) / 2
                impact = self._estimate_price_impact(pool_data, mid, 'buy')
                
                if impact <= self.max_price_impact:
                    low = mid
                else:
                    high = mid
            
            # Apply safety margin
            max_size = low * 0.9  # 10% safety margin
            
            # Respect configuration limits
            max_size = min(max_size, self.max_position_size)
            
            return max_size
            
        except Exception as e:
            logger.error(f"Error calculating max trade size: {e}")
            return self.max_position_size * 0.1  # Conservative fallback
    
    def _calculate_recommended_trade_size(self, pool_data: Dict[str, Any]) -> float:
        """Calculate recommended trade size for optimal execution"""
        try:
            pool_liquidity = self._extract_pool_liquidity_sol(pool_data)
            
            if pool_liquidity <= 0:
                return 0.01  # Minimum trade size
            
            # Recommended size targets 2-3% price impact for good execution
            target_impact = min(self.max_price_impact * 0.3, 3.0)  # 30% of max or 3%
            
            # Calculate trade size for target impact
            # Using simplified linear approximation for speed
            recommended_size = pool_liquidity * (target_impact / 100)
            
            # Apply bounds
            recommended_size = max(recommended_size, 0.01)  # Minimum
            recommended_size = min(recommended_size, self.max_position_size)  # Maximum
            
            return recommended_size
            
        except Exception as e:
            logger.error(f"Error calculating recommended trade size: {e}")
            return 0.1  # Default recommendation
    
    def _validate_pool_quality(self, pool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pool quality metrics"""
        quality_metrics = {
            'volume_check': False,
            'liquidity_check': False,
            'price_check': False,
            'overall_quality': 'poor'
        }
        
        try:
            # Volume check
            volume_24h = pool_data.get('volume_24h', 0)
            quality_metrics['volume_check'] = volume_24h >= self.min_volume_24h
            
            # Liquidity check
            pool_liquidity = self._extract_pool_liquidity_sol(pool_data)
            quality_metrics['liquidity_check'] = pool_liquidity >= self.min_liquidity_sol
            
            # Price check (ensure price is reasonable)
            price = pool_data.get('price', 0)
            quality_metrics['price_check'] = 0 < price < 1000000  # Reasonable price range
            
            # Overall quality assessment
            checks_passed = sum([
                quality_metrics['volume_check'],
                quality_metrics['liquidity_check'],
                quality_metrics['price_check']
            ])
            
            if checks_passed >= 3:
                quality_metrics['overall_quality'] = 'excellent'
            elif checks_passed >= 2:
                quality_metrics['overall_quality'] = 'good'
            elif checks_passed >= 1:
                quality_metrics['overall_quality'] = 'fair'
            else:
                quality_metrics['overall_quality'] = 'poor'
            
            quality_metrics.update({
                'volume_24h': volume_24h,
                'pool_liquidity_sol': pool_liquidity,
                'current_price': price,
                'checks_passed': checks_passed
            })
            
        except Exception as e:
            logger.error(f"Error validating pool quality: {e}")
            quality_metrics['error'] = str(e)
        
        return quality_metrics
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation configuration and thresholds"""
        return {
            'min_liquidity_sol': self.min_liquidity_sol,
            'max_price_impact_percent': self.max_price_impact,
            'max_position_size': self.max_position_size,
            'slippage_tolerance_percent': self.slippage_tolerance,
            'min_volume_24h': self.min_volume_24h,
            'price_impact_model': self.price_impact_model
        }