"""
Signal analysis engine for new pools data.
Detects trading signals and patterns from new pools history.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """Result of signal analysis."""
    signal_score: float
    volume_trend: str
    liquidity_trend: str
    momentum_indicator: float
    activity_score: float
    volatility_score: float
    signals: Dict[str, Any]


class NewPoolsSignalAnalyzer:
    """
    Analyze new pools data for trading signals and patterns.
    
    This analyzer processes new pools history data to identify:
    - Volume spikes and trends
    - Liquidity growth patterns
    - Price momentum indicators
    - Trading activity surges
    - Overall signal strength
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the signal analyzer.
        
        Args:
            config: Configuration dictionary with thresholds and parameters
        """
        self.config = config or {}
        
        # Default thresholds
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 2.0)
        self.liquidity_growth_threshold = self.config.get('liquidity_growth_threshold', 1.5)
        self.momentum_lookback_hours = self.config.get('momentum_lookback_hours', 6)
        self.min_signal_score = self.config.get('min_signal_score', 60.0)
        
        logger.info(f"Signal analyzer initialized with thresholds: "
                   f"volume_spike={self.volume_spike_threshold}, "
                   f"liquidity_growth={self.liquidity_growth_threshold}")
    
    def analyze_pool_signals(self, current_data: Dict, historical_data: List[Dict] = None) -> SignalResult:
        """
        Analyze a pool's current data against historical patterns to generate signals.
        
        Args:
            current_data: Current pool data from API
            historical_data: List of historical data points for the pool
            
        Returns:
            SignalResult with comprehensive signal analysis
        """
        try:
            # Initialize signal components
            signals = {}
            
            # Extract current metrics
            current_volume = self._safe_decimal(current_data.get('volume_usd_h24', 0))
            current_liquidity = self._safe_decimal(current_data.get('reserve_in_usd', 0))
            current_price_change_1h = self._safe_decimal(current_data.get('price_change_percentage_h1', 0))
            current_price_change_24h = self._safe_decimal(current_data.get('price_change_percentage_h24', 0))
            
            # Calculate individual signal components
            volume_analysis = self._analyze_volume_trend(current_data, historical_data)
            liquidity_analysis = self._analyze_liquidity_trend(current_data, historical_data)
            momentum_analysis = self._analyze_price_momentum(current_data, historical_data)
            activity_analysis = self._analyze_trading_activity(current_data, historical_data)
            volatility_analysis = self._analyze_volatility(current_data, historical_data)
            
            # Store individual signals
            signals.update({
                'volume_spike': volume_analysis.get('spike_detected', False),
                'volume_growth_rate': volume_analysis.get('growth_rate', 0),
                'liquidity_growth': liquidity_analysis.get('growth_detected', False),
                'liquidity_growth_rate': liquidity_analysis.get('growth_rate', 0),
                'price_momentum_strong': momentum_analysis.get('strong_momentum', False),
                'momentum_direction': momentum_analysis.get('direction', 'neutral'),
                'high_activity': activity_analysis.get('high_activity', False),
                'activity_increase': activity_analysis.get('activity_increase', 0),
                'high_volatility': volatility_analysis.get('high_volatility', False),
                'volatility_trend': volatility_analysis.get('trend', 'stable')
            })
            
            # Calculate overall signal score (0-100)
            signal_score = self._calculate_overall_signal_score(
                volume_analysis, liquidity_analysis, momentum_analysis, 
                activity_analysis, volatility_analysis
            )
            
            return SignalResult(
                signal_score=signal_score,
                volume_trend=volume_analysis.get('trend', 'stable'),
                liquidity_trend=liquidity_analysis.get('trend', 'stable'),
                momentum_indicator=momentum_analysis.get('indicator', 0.0),
                activity_score=activity_analysis.get('score', 0.0),
                volatility_score=volatility_analysis.get('score', 0.0),
                signals=signals
            )
            
        except Exception as e:
            logger.error(f"Error analyzing pool signals: {e}")
            return self._create_default_signal_result()
    
    def _analyze_volume_trend(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analyze volume trends and detect spikes."""
        try:
            current_volume = self._safe_decimal(current_data.get('volume_usd_h24', 0))
            
            if not historical_data or len(historical_data) < 2:
                # No historical data - use basic heuristics
                return {
                    'trend': 'unknown',
                    'spike_detected': current_volume > 10000,  # Basic threshold
                    'growth_rate': 0,
                    'score': min(float(current_volume) / 1000, 50)  # Basic scoring
                }
            
            # Calculate historical average
            historical_volumes = [self._safe_decimal(d.get('volume_usd_h24', 0)) for d in historical_data]
            avg_volume = sum(historical_volumes) / len(historical_volumes) if historical_volumes else Decimal('0')
            
            # Calculate growth rate
            growth_rate = float((current_volume / avg_volume) - 1) if avg_volume > 0 else 0
            
            # Detect volume spike
            spike_detected = growth_rate >= (self.volume_spike_threshold - 1)
            
            # Determine trend
            if growth_rate > 0.5:
                trend = 'spike' if spike_detected else 'increasing'
            elif growth_rate > 0.1:
                trend = 'increasing'
            elif growth_rate < -0.3:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            # Calculate volume score (0-100)
            volume_score = min(100, max(0, (
                (float(current_volume) / 1000) * 10 +  # Base volume component
                (growth_rate * 50) +  # Growth component
                (50 if spike_detected else 0)  # Spike bonus
            )))
            
            return {
                'trend': trend,
                'spike_detected': spike_detected,
                'growth_rate': growth_rate,
                'score': volume_score,
                'current_volume': float(current_volume),
                'avg_historical_volume': float(avg_volume)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume trend: {e}")
            return {'trend': 'stable', 'spike_detected': False, 'growth_rate': 0, 'score': 0}
    
    def _analyze_liquidity_trend(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analyze liquidity trends and growth patterns."""
        try:
            current_liquidity = self._safe_decimal(current_data.get('reserve_in_usd', 0))
            
            if not historical_data or len(historical_data) < 2:
                return {
                    'trend': 'unknown',
                    'growth_detected': current_liquidity > 50000,  # Basic threshold
                    'growth_rate': 0,
                    'score': min(float(current_liquidity) / 10000, 30)
                }
            
            # Calculate historical average
            historical_liquidity = [self._safe_decimal(d.get('reserve_in_usd', 0)) for d in historical_data]
            avg_liquidity = sum(historical_liquidity) / len(historical_liquidity) if historical_liquidity else Decimal('0')
            
            # Calculate growth rate
            growth_rate = float((current_liquidity / avg_liquidity) - 1) if avg_liquidity > 0 else 0
            
            # Detect significant growth
            growth_detected = growth_rate >= (self.liquidity_growth_threshold - 1)
            
            # Determine trend
            if growth_rate > 0.3:
                trend = 'growing'
            elif growth_rate < -0.2:
                trend = 'shrinking'
            else:
                trend = 'stable'
            
            # Calculate liquidity score
            liquidity_score = min(100, max(0, (
                (float(current_liquidity) / 10000) * 20 +  # Base liquidity component
                (growth_rate * 30) +  # Growth component
                (30 if growth_detected else 0)  # Growth bonus
            )))
            
            return {
                'trend': trend,
                'growth_detected': growth_detected,
                'growth_rate': growth_rate,
                'score': liquidity_score,
                'current_liquidity': float(current_liquidity),
                'avg_historical_liquidity': float(avg_liquidity)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity trend: {e}")
            return {'trend': 'stable', 'growth_detected': False, 'growth_rate': 0, 'score': 0}
    
    def _analyze_price_momentum(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analyze price momentum and direction."""
        try:
            price_change_1h = self._safe_decimal(current_data.get('price_change_percentage_h1', 0))
            price_change_24h = self._safe_decimal(current_data.get('price_change_percentage_h24', 0))
            
            # Calculate momentum indicator
            momentum_indicator = float((price_change_1h * 2 + price_change_24h) / 3)
            
            # Determine momentum strength and direction
            strong_momentum = abs(momentum_indicator) > 10  # >10% momentum
            
            if momentum_indicator > 5:
                direction = 'bullish'
            elif momentum_indicator < -5:
                direction = 'bearish'
            else:
                direction = 'neutral'
            
            # Calculate momentum score
            momentum_score = min(100, max(0, (
                abs(momentum_indicator) * 5 +  # Base momentum
                (20 if strong_momentum else 0) +  # Strong momentum bonus
                (10 if direction == 'bullish' else 0)  # Bullish bias
            )))
            
            return {
                'indicator': momentum_indicator,
                'strong_momentum': strong_momentum,
                'direction': direction,
                'score': momentum_score,
                'price_change_1h': float(price_change_1h),
                'price_change_24h': float(price_change_24h)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing price momentum: {e}")
            return {'indicator': 0.0, 'strong_momentum': False, 'direction': 'neutral', 'score': 0}
    
    def _analyze_trading_activity(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analyze trading activity patterns."""
        try:
            # Extract transaction data
            buys_1h = self._safe_int(current_data.get('transactions_h1_buys', 0))
            sells_1h = self._safe_int(current_data.get('transactions_h1_sells', 0))
            buys_24h = self._safe_int(current_data.get('transactions_h24_buys', 0))
            sells_24h = self._safe_int(current_data.get('transactions_h24_sells', 0))
            
            # Calculate activity metrics
            total_1h = buys_1h + sells_1h
            total_24h = buys_24h + sells_24h
            
            # Calculate buy/sell ratio
            buy_ratio_1h = buys_1h / total_1h if total_1h > 0 else 0.5
            buy_ratio_24h = buys_24h / total_24h if total_24h > 0 else 0.5
            
            # Detect high activity
            high_activity = total_1h > 50 or total_24h > 500
            
            # Calculate activity increase (if historical data available)
            activity_increase = 0
            if historical_data and len(historical_data) > 0:
                avg_historical_24h = sum(
                    self._safe_int(d.get('transactions_h24_buys', 0)) + 
                    self._safe_int(d.get('transactions_h24_sells', 0))
                    for d in historical_data
                ) / len(historical_data)
                
                if avg_historical_24h > 0:
                    activity_increase = (total_24h / avg_historical_24h) - 1
            
            # Calculate activity score
            activity_score = min(100, max(0, (
                (total_1h * 0.5) +  # 1h activity component
                (total_24h * 0.1) +  # 24h activity component
                (activity_increase * 30) +  # Activity increase bonus
                (20 if high_activity else 0) +  # High activity bonus
                (abs(buy_ratio_1h - 0.5) * 40)  # Imbalance component
            )))
            
            return {
                'score': activity_score,
                'high_activity': high_activity,
                'activity_increase': activity_increase,
                'total_transactions_1h': total_1h,
                'total_transactions_24h': total_24h,
                'buy_ratio_1h': buy_ratio_1h,
                'buy_ratio_24h': buy_ratio_24h
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trading activity: {e}")
            return {'score': 0, 'high_activity': False, 'activity_increase': 0}
    
    def _analyze_volatility(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analyze price volatility patterns."""
        try:
            price_change_1h = abs(self._safe_decimal(current_data.get('price_change_percentage_h1', 0)))
            price_change_24h = abs(self._safe_decimal(current_data.get('price_change_percentage_h24', 0)))
            
            # Calculate volatility score
            volatility_score = float((price_change_1h * 2 + price_change_24h) / 3)
            
            # Determine volatility level
            high_volatility = volatility_score > 15  # >15% volatility
            
            # Determine trend
            if volatility_score > 20:
                trend = 'extreme'
            elif volatility_score > 10:
                trend = 'high'
            elif volatility_score > 5:
                trend = 'moderate'
            else:
                trend = 'low'
            
            return {
                'score': min(100, volatility_score * 3),
                'high_volatility': high_volatility,
                'trend': trend,
                'volatility_1h': float(price_change_1h),
                'volatility_24h': float(price_change_24h)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volatility: {e}")
            return {'score': 0, 'high_volatility': False, 'trend': 'low'}
    
    def _calculate_overall_signal_score(self, volume_analysis: Dict, liquidity_analysis: Dict, 
                                      momentum_analysis: Dict, activity_analysis: Dict, 
                                      volatility_analysis: Dict) -> float:
        """Calculate overall signal score from individual components."""
        try:
            # Weight the different components
            weights = {
                'volume': 0.3,
                'liquidity': 0.2,
                'momentum': 0.2,
                'activity': 0.2,
                'volatility': 0.1
            }
            
            # Get scores from each analysis
            volume_score = volume_analysis.get('score', 0)
            liquidity_score = liquidity_analysis.get('score', 0)
            momentum_score = momentum_analysis.get('score', 0)
            activity_score = activity_analysis.get('score', 0)
            volatility_score = volatility_analysis.get('score', 0)
            
            # Calculate weighted average
            overall_score = (
                volume_score * weights['volume'] +
                liquidity_score * weights['liquidity'] +
                momentum_score * weights['momentum'] +
                activity_score * weights['activity'] +
                volatility_score * weights['volatility']
            )
            
            # Apply bonuses for strong signals
            if volume_analysis.get('spike_detected', False):
                overall_score += 10
            if liquidity_analysis.get('growth_detected', False):
                overall_score += 8
            if momentum_analysis.get('strong_momentum', False):
                overall_score += 5
            if activity_analysis.get('high_activity', False):
                overall_score += 5
            
            return min(100, max(0, overall_score))
            
        except Exception as e:
            logger.error(f"Error calculating overall signal score: {e}")
            return 0.0
    
    def _create_default_signal_result(self) -> SignalResult:
        """Create a default signal result for error cases."""
        return SignalResult(
            signal_score=0.0,
            volume_trend='stable',
            liquidity_trend='stable',
            momentum_indicator=0.0,
            activity_score=0.0,
            volatility_score=0.0,
            signals={}
        )
    
    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None or value == '':
            return Decimal('0')
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal('0')
    
    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int."""
        if value is None or value == '':
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def should_add_to_watchlist(self, signal_result: SignalResult, threshold: float = None) -> bool:
        """
        Determine if a pool should be added to watchlist based on signal analysis.
        
        Args:
            signal_result: Signal analysis result
            threshold: Signal score threshold (uses config default if None)
            
        Returns:
            True if pool should be added to watchlist
        """
        if threshold is None:
            threshold = self.config.get('auto_watchlist_threshold', 75.0)
        
        return signal_result.signal_score >= threshold
    
    def generate_alert_message(self, pool_id: str, signal_result: SignalResult) -> str:
        """Generate human-readable alert message for strong signals."""
        signals = signal_result.signals
        messages = []
        
        if signals.get('volume_spike', False):
            messages.append(f"Volume spike detected ({signals.get('volume_growth_rate', 0):.1%} increase)")
        
        if signals.get('liquidity_growth', False):
            messages.append(f"Liquidity growth ({signals.get('liquidity_growth_rate', 0):.1%} increase)")
        
        if signals.get('price_momentum_strong', False):
            direction = signals.get('momentum_direction', 'neutral')
            messages.append(f"Strong {direction} momentum")
        
        if signals.get('high_activity', False):
            messages.append("High trading activity")
        
        if not messages:
            messages.append("Multiple positive signals detected")
        
        return f"Pool {pool_id} - Signal Score: {signal_result.signal_score:.1f} - {', '.join(messages)}"