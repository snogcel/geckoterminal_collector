"""
PumpSwap Signal Analyzer for Enhanced Q50 Signal Processing

This module provides the PumpSwapSignalAnalyzer class that enhances existing
Q50 signal analysis with PumpSwap pool data, integrating execution feasibility
into signal scoring and providing liquidity-adjusted signal strength calculations.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
import numpy as np

from .config import NautilusPOCConfig
from .signal_loader import Q50SignalLoader
from .liquidity_validator import LiquidityValidator, LiquidityValidationResult

logger = logging.getLogger(__name__)

class SignalQuality(Enum):
    """Enhanced signal quality classification"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNTRADEABLE = "untradeable"

@dataclass
class EnhancedQ50Signal:
    """Enhanced Q50 signal with PumpSwap integration"""
    # Original Q50 fields
    timestamp: pd.Timestamp
    q10: float
    q50: float
    q90: float
    vol_raw: float
    vol_risk: float
    prob_up: float
    economically_significant: bool
    high_quality: bool
    tradeable: bool
    
    # Regime classification
    regime: str
    vol_risk_percentile: float
    threshold_adjustment: float
    regime_multiplier: float
    
    # PumpSwap integration
    mint_address: str
    pair_address: Optional[str]
    pool_liquidity_sol: float
    pool_liquidity_usd: float
    estimated_price_impact: float
    execution_feasible: bool
    liquidity_validation: LiquidityValidationResult
    
    # Enhanced signal metrics
    liquidity_adjusted_strength: float
    execution_adjusted_q50: float
    final_signal_score: float
    recommended_position_size: float
    max_position_by_liquidity: float
    
    # Economic calculations
    expected_value: float
    enhanced_info_ratio: float
    kelly_multiplier: float
    
    # Signal quality assessment
    signal_quality: SignalQuality
    quality_score: float
    quality_factors: Dict[str, float]
    
    # Fallback handling
    pumpswap_data_available: bool
    fallback_reason: Optional[str]

class PumpSwapSignalAnalyzer:
    """
    Enhance existing signal analysis with PumpSwap pool data
    
    Key Responsibilities:
    - Enhance existing signal analysis with PumpSwap pool data
    - Integrate execution feasibility into signal scoring
    - Add liquidity-adjusted signal strength calculations
    - Create fallback logic for unavailable PumpSwap data
    """
    
    def __init__(self, config: NautilusPOCConfig, signal_loader: Q50SignalLoader):
        """Initialize PumpSwap signal analyzer"""
        self.config = config
        self.signal_loader = signal_loader
        #self.liquidity_validator = liquidity_validator
        
        # PumpSwap SDK integration (mock for now)
        try:
            # from pumpswap_sdk.sdk.pumpswap_sdk import PumpSwapSDK
            from .pumpswap_executor import PumpSwapSDK
            self.pumpswap_sdk = PumpSwapSDK()
        except ImportError:
            # Mock SDK for development
            self.pumpswap_sdk = self._create_mock_sdk()
        
        # Signal enhancement parameters
        self.liquidity_weight = config.regime_detection.get('liquidity_weight', 0.3)
        self.execution_weight = config.regime_detection.get('execution_weight', 0.2)
        self.quality_threshold = config.regime_detection.get('quality_threshold', 0.6)
        
        # Economic significance parameters
        self.realistic_transaction_cost = config.monitoring.get('realistic_transaction_cost', 0.0005)
        self.min_expected_value = config.monitoring.get('min_expected_value', 0.001)
        
        # Performance tracking
        self.analysis_count = 0
        self.successful_analyses = 0
        self.fallback_count = 0
        self.cache = {}
        
        logger.info("PumpSwapSignalAnalyzer initialized")
    
    async def analyze_signal(self, base_signal: Dict[str, Any], 
                           mint_address: str) -> EnhancedQ50Signal:
        """
        Analyze and enhance Q50 signal with PumpSwap data
        
        Args:
            base_signal: Original Q50 signal from signal loader
            mint_address: Token mint address for PumpSwap integration
            
        Returns:
            EnhancedQ50Signal with comprehensive analysis
        """
        start_time = time.time()
        self.analysis_count += 1
        
        try:
            logger.debug(f"Analyzing signal for {mint_address}")
            
            # Get PumpSwap pool data
            pool_data, pair_address = await self._get_pumpswap_data(mint_address)
            pumpswap_available = pool_data is not None
            
            # Perform liquidity validation if data available
            liquidity_validation = None
            if pumpswap_available:
                liquidity_validation = self.liquidity_validator.validate_liquidity_detailed(
                    pool_data, base_signal, 'buy'
                )
            
            # Calculate enhanced signal metrics
            enhanced_metrics = self._calculate_enhanced_metrics(
                base_signal, pool_data, liquidity_validation
            )
            
            # Determine execution feasibility
            execution_feasible = self._determine_execution_feasibility(
                base_signal, pool_data, liquidity_validation
            )
            
            # Calculate liquidity-adjusted signal strength
            liquidity_adjusted_strength = self._calculate_liquidity_adjusted_strength(
                base_signal, pool_data, enhanced_metrics
            )
            
            # Calculate execution-adjusted Q50
            execution_adjusted_q50 = self._calculate_execution_adjusted_q50(
                base_signal, pool_data, execution_feasible
            )
            
            # Calculate final signal score
            final_signal_score = self._calculate_final_signal_score(
                base_signal, enhanced_metrics, liquidity_adjusted_strength, execution_feasible
            )
            
            # Assess signal quality
            signal_quality, quality_score, quality_factors = self._assess_signal_quality(
                base_signal, pool_data, enhanced_metrics, execution_feasible
            )
            
            # Calculate position sizing recommendations
            recommended_position, max_position = self._calculate_position_recommendations(
                base_signal, pool_data, enhanced_metrics
            )
            
            # Create enhanced signal
            enhanced_signal = EnhancedQ50Signal(
                # Original Q50 fields
                timestamp=pd.Timestamp(base_signal.get('timestamp', pd.Timestamp.now())),
                q10=base_signal.get('q10', 0),
                q50=base_signal.get('q50', 0),
                q90=base_signal.get('q90', 0),
                vol_raw=base_signal.get('vol_raw', 0),
                vol_risk=base_signal.get('vol_risk', 0.1),
                prob_up=base_signal.get('prob_up', 0.5),
                economically_significant=base_signal.get('economically_significant', False),
                high_quality=base_signal.get('high_quality', False),
                tradeable=base_signal.get('tradeable', False),
                
                # Regime classification
                regime=base_signal.get('regime', 'unknown'),
                vol_risk_percentile=base_signal.get('vol_risk_percentile', 0.5),
                threshold_adjustment=base_signal.get('threshold_adjustment', 0.0),
                regime_multiplier=base_signal.get('regime_multiplier', 1.0),
                
                # PumpSwap integration
                mint_address=mint_address,
                pair_address=pair_address,
                pool_liquidity_sol=pool_data.get('reserve_sol', 0) if pool_data else 0,
                pool_liquidity_usd=pool_data.get('reserve_in_usd', 0) if pool_data else 0,
                estimated_price_impact=liquidity_validation.estimated_price_impact if liquidity_validation else 100.0,
                execution_feasible=execution_feasible,
                liquidity_validation=liquidity_validation,
                
                # Enhanced signal metrics
                liquidity_adjusted_strength=liquidity_adjusted_strength,
                execution_adjusted_q50=execution_adjusted_q50,
                final_signal_score=final_signal_score,
                recommended_position_size=recommended_position,
                max_position_by_liquidity=max_position,
                
                # Economic calculations
                expected_value=enhanced_metrics.get('expected_value', 0),
                enhanced_info_ratio=enhanced_metrics.get('enhanced_info_ratio', 0),
                kelly_multiplier=enhanced_metrics.get('kelly_multiplier', 1.0),
                
                # Signal quality assessment
                signal_quality=signal_quality,
                quality_score=quality_score,
                quality_factors=quality_factors,
                
                # Fallback handling
                pumpswap_data_available=pumpswap_available,
                fallback_reason=None if pumpswap_available else "PumpSwap data unavailable"
            )
            
            # Update performance tracking
            self.successful_analyses += 1
            if not pumpswap_available:
                self.fallback_count += 1
            
            analysis_time = (time.time() - start_time) * 1000
            logger.debug(f"Signal analysis completed in {analysis_time:.2f}ms")
            
            return enhanced_signal
            
        except Exception as e:
            logger.error(f"Error analyzing signal for {mint_address}: {e}")
            # Return fallback signal
            return self._create_fallback_signal(base_signal, mint_address, str(e))
    
    async def analyze_signals_batch(self, signals: List[Tuple[Dict[str, Any], str]]) -> List[EnhancedQ50Signal]:
        """
        Analyze multiple signals in batch for efficiency
        
        Args:
            signals: List of (base_signal, mint_address) tuples
            
        Returns:
            List of EnhancedQ50Signal objects
        """
        logger.info(f"Analyzing batch of {len(signals)} signals")
        
        # Create analysis tasks
        tasks = [
            self.analyze_signal(signal, mint_address)
            for signal, mint_address in signals
        ]
        
        # Execute in parallel with concurrency limit
        semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        
        async def analyze_with_semaphore(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[analyze_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Filter out exceptions and log errors
        enhanced_signals = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch analysis failed for signal {i}: {result}")
                # Create fallback signal
                base_signal, mint_address = signals[i]
                fallback = self._create_fallback_signal(base_signal, mint_address, str(result))
                enhanced_signals.append(fallback)
            else:
                enhanced_signals.append(result)
        
        logger.info(f"Batch analysis completed: {len(enhanced_signals)} signals processed")
        return enhanced_signals
    
    async def _get_pumpswap_data(self, mint_address: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get PumpSwap pool data and pair address"""
        try:
            # Check cache first
            cache_key = f"pumpswap_{mint_address}"
            if cache_key in self.cache:
                cached_data = self.cache[cache_key]
                if time.time() - cached_data['timestamp'] < 60:  # 1-minute cache
                    return cached_data['pool_data'], cached_data['pair_address']
            
            # Get pair address
            pair_address = await self.pumpswap_sdk.get_pair_address(mint_address)
            if not pair_address:
                logger.debug(f"No pair found for {mint_address}")
                return None, None
            
            # Get pool data
            pool_data = await self.pumpswap_sdk.get_pool_data(mint_address)
            if not pool_data:
                logger.debug(f"No pool data for {mint_address}")
                return None, pair_address
            
            # Cache the result
            self.cache[cache_key] = {
                'pool_data': pool_data,
                'pair_address': pair_address,
                'timestamp': time.time()
            }
            
            return pool_data, pair_address
            
        except Exception as e:
            logger.error(f"Error getting PumpSwap data for {mint_address}: {e}")
            return None, None
    
    def _calculate_enhanced_metrics(self, base_signal: Dict[str, Any], 
                                  pool_data: Optional[Dict], 
                                  liquidity_validation: Optional[LiquidityValidationResult]) -> Dict[str, float]:
        """Calculate enhanced signal metrics"""
        metrics = {}
        
        try:
            # Extract base signal values
            q50 = base_signal.get('q50', 0)
            vol_risk = base_signal.get('vol_risk', 0.1)
            prob_up = base_signal.get('prob_up', 0.5)
            
            # Calculate expected value with PumpSwap-aware costs
            transaction_cost = self.realistic_transaction_cost
            if pool_data and liquidity_validation:
                # Add estimated slippage to transaction costs
                estimated_slippage = liquidity_validation.estimated_price_impact / 100
                total_cost = transaction_cost + estimated_slippage
            else:
                total_cost = transaction_cost * 2  # Higher cost for uncertain execution
            
            potential_gain = abs(q50) - total_cost
            potential_loss = abs(q50) + total_cost
            expected_value = (prob_up * potential_gain) - ((1 - prob_up) * potential_loss)
            metrics['expected_value'] = expected_value
            
            # Calculate enhanced info ratio with liquidity constraints
            market_variance = vol_risk
            if pool_data:
                # Add liquidity-based variance
                pool_liquidity = pool_data.get('reserve_sol', 0)
                if pool_liquidity > 0:
                    liquidity_variance = 1.0 / pool_liquidity  # Inverse relationship
                    market_variance += liquidity_variance * 0.1  # 10% weight
            
            prediction_variance = vol_risk * 0.5  # Assume prediction variance is 50% of market
            total_variance = market_variance + prediction_variance
            
            enhanced_info_ratio = abs(q50) / np.sqrt(total_variance) if total_variance > 0 else 0
            metrics['enhanced_info_ratio'] = enhanced_info_ratio
            
            # Calculate Kelly multiplier with liquidity constraints
            if vol_risk > 0:
                base_kelly = 0.1 / max(vol_risk * 1000, 0.1)
                
                # Adjust for liquidity
                if pool_data:
                    pool_liquidity = pool_data.get('reserve_sol', 0)
                    if pool_liquidity > 100:  # Good liquidity
                        liquidity_multiplier = 1.2
                    elif pool_liquidity > 50:  # Moderate liquidity
                        liquidity_multiplier = 1.0
                    else:  # Poor liquidity
                        liquidity_multiplier = 0.5
                else:
                    liquidity_multiplier = 0.3  # Conservative without data
                
                kelly_multiplier = base_kelly * liquidity_multiplier
            else:
                kelly_multiplier = 0.1
            
            metrics['kelly_multiplier'] = kelly_multiplier
            
            # Calculate signal strength with execution feasibility
            signal_strength = abs(q50)
            if enhanced_info_ratio > 0:
                effective_threshold = 1.0  # Base threshold
                signal_strength *= min(enhanced_info_ratio / effective_threshold, 2.0)
            
            metrics['signal_strength'] = signal_strength
            
        except Exception as e:
            logger.error(f"Error calculating enhanced metrics: {e}")
            # Provide fallback metrics
            metrics = {
                'expected_value': 0,
                'enhanced_info_ratio': 0,
                'kelly_multiplier': 0.1,
                'signal_strength': abs(base_signal.get('q50', 0))
            }
        
        return metrics
    
    def _determine_execution_feasibility(self, base_signal: Dict[str, Any], 
                                       pool_data: Optional[Dict],
                                       liquidity_validation: Optional[LiquidityValidationResult]) -> bool:
        """Determine if signal is executable via PumpSwap"""
        try:
            # Base tradeable check
            if not base_signal.get('tradeable', False):
                return False
            
            # Economic significance check
            if not base_signal.get('economically_significant', False):
                return False
            
            # PumpSwap data availability
            if not pool_data:
                return False
            
            # Liquidity validation
            if liquidity_validation and not liquidity_validation.is_valid:
                return False
            
            # Additional feasibility checks
            q50_value = abs(base_signal.get('q50', 0))
            if q50_value < 0.001:  # Minimum signal strength
                return False
            
            # Pool quality check
            if pool_data:
                pool_liquidity = pool_data.get('reserve_sol', 0)
                if pool_liquidity < self.config.pumpswap.min_liquidity_sol:
                    return False
                
                # Volume check
                volume_24h = pool_data.get('volume_24h', 0)
                if volume_24h < 1000:  # Minimum $1k daily volume
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error determining execution feasibility: {e}")
            return False
    
    def _calculate_liquidity_adjusted_strength(self, base_signal: Dict[str, Any],
                                             pool_data: Optional[Dict],
                                             enhanced_metrics: Dict[str, float]) -> float:
        """Calculate liquidity-adjusted signal strength"""
        try:
            base_strength = enhanced_metrics.get('signal_strength', abs(base_signal.get('q50', 0)))
            
            if not pool_data:
                return base_strength * 0.3  # Heavily penalize without liquidity data
            
            # Liquidity adjustment factors
            pool_liquidity = pool_data.get('reserve_sol', 0)
            volume_24h = pool_data.get('volume_24h', 0)
            
            # Liquidity factor (0.5 to 1.5)
            if pool_liquidity >= 100:
                liquidity_factor = 1.3
            elif pool_liquidity >= 50:
                liquidity_factor = 1.0
            elif pool_liquidity >= 10:
                liquidity_factor = 0.8
            else:
                liquidity_factor = 0.5
            
            # Volume factor (0.7 to 1.2)
            if volume_24h >= 10000:
                volume_factor = 1.2
            elif volume_24h >= 5000:
                volume_factor = 1.0
            elif volume_24h >= 1000:
                volume_factor = 0.9
            else:
                volume_factor = 0.7
            
            # Combined adjustment
            adjustment_factor = (liquidity_factor * 0.7) + (volume_factor * 0.3)
            adjusted_strength = base_strength * adjustment_factor
            
            return adjusted_strength
            
        except Exception as e:
            logger.error(f"Error calculating liquidity-adjusted strength: {e}")
            return abs(base_signal.get('q50', 0)) * 0.5  # Conservative fallback
    
    def _calculate_execution_adjusted_q50(self, base_signal: Dict[str, Any],
                                        pool_data: Optional[Dict],
                                        execution_feasible: bool) -> float:
        """Calculate execution-adjusted Q50 value"""
        try:
            base_q50 = base_signal.get('q50', 0)
            
            if not execution_feasible:
                return 0.0  # No execution means no signal
            
            if not pool_data:
                return base_q50 * 0.5  # Reduce confidence without pool data
            
            # Price impact adjustment
            estimated_position = self._estimate_position_size(base_signal, pool_data)
            pool_liquidity = pool_data.get('reserve_sol', 0)
            
            if pool_liquidity > 0:
                impact_ratio = estimated_position / pool_liquidity
                impact_adjustment = max(0.5, 1.0 - (impact_ratio * 2))  # Reduce for high impact
            else:
                impact_adjustment = 0.5
            
            # Slippage adjustment
            estimated_slippage = min(impact_ratio * 100, 20)  # Cap at 20%
            slippage_adjustment = max(0.7, 1.0 - (estimated_slippage / 100))
            
            # Combined adjustment
            total_adjustment = impact_adjustment * slippage_adjustment
            adjusted_q50 = base_q50 * total_adjustment
            
            return adjusted_q50
            
        except Exception as e:
            logger.error(f"Error calculating execution-adjusted Q50: {e}")
            return base_signal.get('q50', 0) * 0.7  # Conservative adjustment
    
    def _calculate_final_signal_score(self, base_signal: Dict[str, Any],
                                    enhanced_metrics: Dict[str, float],
                                    liquidity_adjusted_strength: float,
                                    execution_feasible: bool) -> float:
        """Calculate final composite signal score"""
        try:
            if not execution_feasible:
                return 0.0
            
            # Component scores (0-1 scale)
            signal_component = min(liquidity_adjusted_strength * 10, 1.0)  # Scale to 0-1
            economic_component = 1.0 if enhanced_metrics.get('expected_value', 0) > self.min_expected_value else 0.0
            quality_component = 1.0 if base_signal.get('high_quality', False) else 0.5
            regime_component = base_signal.get('regime_multiplier', 1.0) / 2.0  # Normalize to 0-1
            
            # Weighted combination
            weights = {
                'signal': 0.4,
                'economic': 0.3,
                'quality': 0.2,
                'regime': 0.1
            }
            
            final_score = (
                signal_component * weights['signal'] +
                economic_component * weights['economic'] +
                quality_component * weights['quality'] +
                regime_component * weights['regime']
            )
            
            return min(final_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating final signal score: {e}")
            return 0.0
    
    def _assess_signal_quality(self, base_signal: Dict[str, Any],
                             pool_data: Optional[Dict],
                             enhanced_metrics: Dict[str, float],
                             execution_feasible: bool) -> Tuple[SignalQuality, float, Dict[str, float]]:
        """Assess overall signal quality"""
        try:
            quality_factors = {}
            
            # Base signal quality
            quality_factors['base_quality'] = 1.0 if base_signal.get('high_quality', False) else 0.5
            quality_factors['economic_significance'] = 1.0 if base_signal.get('economically_significant', False) else 0.0
            quality_factors['tradeable'] = 1.0 if base_signal.get('tradeable', False) else 0.0
            
            # Signal strength
            signal_strength = abs(base_signal.get('q50', 0))
            quality_factors['signal_strength'] = min(signal_strength * 100, 1.0)
            
            # Execution feasibility
            quality_factors['execution_feasible'] = 1.0 if execution_feasible else 0.0
            
            # Liquidity quality
            if pool_data:
                pool_liquidity = pool_data.get('reserve_sol', 0)
                volume_24h = pool_data.get('volume_24h', 0)
                
                quality_factors['liquidity'] = min(pool_liquidity / 100, 1.0)  # Normalize to 100 SOL
                quality_factors['volume'] = min(volume_24h / 10000, 1.0)  # Normalize to $10k
            else:
                quality_factors['liquidity'] = 0.0
                quality_factors['volume'] = 0.0
            
            # Enhanced metrics
            quality_factors['expected_value'] = 1.0 if enhanced_metrics.get('expected_value', 0) > 0 else 0.0
            quality_factors['info_ratio'] = min(enhanced_metrics.get('enhanced_info_ratio', 0), 1.0)
            
            # Calculate overall quality score
            weights = {
                'base_quality': 0.15,
                'economic_significance': 0.15,
                'tradeable': 0.15,
                'signal_strength': 0.15,
                'execution_feasible': 0.15,
                'liquidity': 0.10,
                'volume': 0.05,
                'expected_value': 0.05,
                'info_ratio': 0.05
            }
            
            quality_score = sum(
                quality_factors[factor] * weight
                for factor, weight in weights.items()
                if factor in quality_factors
            )
            
            # Determine quality classification
            if quality_score >= 0.8:
                signal_quality = SignalQuality.EXCELLENT
            elif quality_score >= 0.6:
                signal_quality = SignalQuality.GOOD
            elif quality_score >= 0.4:
                signal_quality = SignalQuality.FAIR
            elif quality_score >= 0.2:
                signal_quality = SignalQuality.POOR
            else:
                signal_quality = SignalQuality.UNTRADEABLE
            
            return signal_quality, quality_score, quality_factors
            
        except Exception as e:
            logger.error(f"Error assessing signal quality: {e}")
            return SignalQuality.POOR, 0.0, {}
    
    def _calculate_position_recommendations(self, base_signal: Dict[str, Any],
                                          pool_data: Optional[Dict],
                                          enhanced_metrics: Dict[str, float]) -> Tuple[float, float]:
        """Calculate position size recommendations"""
        try:
            # Base Kelly calculation
            kelly_multiplier = enhanced_metrics.get('kelly_multiplier', 0.1)
            signal_strength = enhanced_metrics.get('signal_strength', 0)
            regime_multiplier = base_signal.get('regime_multiplier', 1.0)
            
            # Calculate recommended position
            recommended_position = kelly_multiplier * signal_strength * regime_multiplier
            
            # Apply configuration limits
            recommended_position = min(recommended_position, self.config.pumpswap.max_position_size)
            recommended_position = max(recommended_position, 0.01)  # Minimum position
            
            # Calculate maximum position by liquidity
            if pool_data:
                pool_liquidity = pool_data.get('reserve_sol', 0)
                max_by_liquidity = pool_liquidity * 0.25  # Max 25% of pool
            else:
                max_by_liquidity = self.config.pumpswap.base_position_size
            
            # Final recommended position respects liquidity constraints
            final_recommended = min(recommended_position, max_by_liquidity)
            
            return final_recommended, max_by_liquidity
            
        except Exception as e:
            logger.error(f"Error calculating position recommendations: {e}")
            return 0.01, 0.1  # Conservative fallback
    
    def _estimate_position_size(self, base_signal: Dict[str, Any], pool_data: Dict[str, Any]) -> float:
        """Estimate position size for impact calculations"""
        try:
            vol_risk = base_signal.get('vol_risk', 0.1)
            q50_value = abs(base_signal.get('q50', 0))
            
            base_size = 0.1 / max(vol_risk * 1000, 0.1)
            signal_multiplier = min(q50_value * 100, 2.0)
            
            estimated_size = base_size * signal_multiplier
            return min(estimated_size, self.config.pumpswap.max_position_size)
            
        except Exception as e:
            logger.error(f"Error estimating position size: {e}")
            return self.config.pumpswap.base_position_size
    
    def _create_fallback_signal(self, base_signal: Dict[str, Any], 
                              mint_address: str, error_reason: str) -> EnhancedQ50Signal:
        """Create fallback signal when PumpSwap data is unavailable"""
        return EnhancedQ50Signal(
            # Original Q50 fields
            timestamp=pd.Timestamp(base_signal.get('timestamp', pd.Timestamp.now())),
            q10=base_signal.get('q10', 0),
            q50=base_signal.get('q50', 0),
            q90=base_signal.get('q90', 0),
            vol_raw=base_signal.get('vol_raw', 0),
            vol_risk=base_signal.get('vol_risk', 0.1),
            prob_up=base_signal.get('prob_up', 0.5),
            economically_significant=False,  # Conservative fallback
            high_quality=False,  # Conservative fallback
            tradeable=False,  # Conservative fallback
            
            # Regime classification
            regime=base_signal.get('regime', 'unknown'),
            vol_risk_percentile=base_signal.get('vol_risk_percentile', 0.5),
            threshold_adjustment=base_signal.get('threshold_adjustment', 0.0),
            regime_multiplier=base_signal.get('regime_multiplier', 1.0),
            
            # PumpSwap integration (fallback values)
            mint_address=mint_address,
            pair_address=None,
            pool_liquidity_sol=0,
            pool_liquidity_usd=0,
            estimated_price_impact=100.0,
            execution_feasible=False,
            liquidity_validation=None,
            
            # Enhanced signal metrics (conservative)
            liquidity_adjusted_strength=0,
            execution_adjusted_q50=0,
            final_signal_score=0,
            recommended_position_size=0,
            max_position_by_liquidity=0,
            
            # Economic calculations (conservative)
            expected_value=0,
            enhanced_info_ratio=0,
            kelly_multiplier=0,
            
            # Signal quality assessment
            signal_quality=SignalQuality.UNTRADEABLE,
            quality_score=0,
            quality_factors={},
            
            # Fallback handling
            pumpswap_data_available=False,
            fallback_reason=error_reason
        )
    
    def _create_mock_sdk(self):
        """Create mock PumpSwap SDK for development"""
        class MockPumpSwapSDK:
            async def get_pair_address(self, mint_address: str) -> Optional[str]:
                return f"pair_{mint_address[:8]}"
            
            async def get_pool_data(self, mint_address: str) -> Dict:
                return {
                    'mint_address': mint_address,
                    'reserve_in_usd': 50000,
                    'reserve_sol': 500,
                    'reserve_token': 500000,
                    'price': 0.001,
                    'volume_24h': 10000
                }
        
        return MockPumpSwapSDK()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get analyzer performance metrics"""
        success_rate = (self.successful_analyses / max(self.analysis_count, 1)) * 100
        fallback_rate = (self.fallback_count / max(self.analysis_count, 1)) * 100
        
        return {
            'total_analyses': self.analysis_count,
            'successful_analyses': self.successful_analyses,
            'fallback_count': self.fallback_count,
            'success_rate_percent': success_rate,
            'fallback_rate_percent': fallback_rate,
            'cache_size': len(self.cache)
        }
    
    def clear_cache(self) -> None:
        """Clear the analysis cache"""
        self.cache.clear()
        logger.info("PumpSwapSignalAnalyzer cache cleared")