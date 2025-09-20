"""
Q50 NautilusTrader Strategy Implementation

This module provides the Q50NautilusStrategy class that integrates our proven
Q50 quantile trading system with NautilusTrader framework for professional
trading execution with PumpSwap DEX integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

import pandas as pd

# NautilusTrader imports with fallback for development/testing
try:
    from nautilus_trader.trading.strategy import Strategy
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model.data import QuoteTick
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.instruments import Instrument
    from nautilus_trader.core.message import Event
    NAUTILUS_AVAILABLE = True
except ImportError:
    # Mock NautilusTrader classes for development/testing
    class StrategyConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class Strategy:
        def __init__(self, config: StrategyConfig):
            self.config = config
            # Mock NautilusTrader strategy attributes
            self.log = logging.getLogger(self.__class__.__name__)
        
        async def on_start(self):
            pass
        
        async def on_stop(self):
            pass
        
        def on_event(self, event):
            pass
    
    class QuoteTick:
        def __init__(self):
            self.instrument_id = "TEST/INSTRUMENT"
            self.bid_price = 100.0
            self.ask_price = 100.1
            self.bid_size = 1000.0
            self.ask_size = 1000.0
            self.ts_event = pd.Timestamp.now().value
    
    class InstrumentId:
        pass
    
    class Instrument:
        pass
    
    class Event:
        pass
    
    NAUTILUS_AVAILABLE = False

from .config import NautilusPOCConfig
from .signal_loader import Q50SignalLoader
from .regime_detector import RegimeDetector
from .pumpswap_executor import PumpSwapExecutor
from .liquidity_validator import LiquidityValidator
from .position_sizer import KellyPositionSizer
from .risk_manager import RiskManager

logger = logging.getLogger(__name__)


if NAUTILUS_AVAILABLE:
    # Use proper NautilusTrader StrategyConfig (msgspec Struct)
    class Q50StrategyConfig(StrategyConfig):
        """Configuration for Q50 NautilusTrader Strategy."""
        strategy_id: str
        instrument_id: str = "SOL/USDC"
        # Add other required fields as needed
else:
    # Mock configuration for testing
    class Q50StrategyConfig(StrategyConfig):
        def __init__(
            self,
            poc_config: NautilusPOCConfig,
            instrument_id: str = "SOL/USDC",
            **kwargs
        ):
            super().__init__(**kwargs)
            self.poc_config = poc_config
            self.instrument_id = instrument_id
            self.strategy_id = poc_config.nautilus.instance_id


class Q50NautilusStrategy(Strategy):
    """
    NautilusTrader strategy implementing Q50 quantile trading logic.
    
    This strategy inherits from NautilusTrader's Strategy base class and implements
    our proven Q50 signal processing with regime-aware enhancements, integrated
    with PumpSwap DEX execution for real Solana trading.
    
    Key Features:
    - Q50 signal loading and processing
    - Variance-based regime detection
    - Kelly position sizing with liquidity constraints
    - PumpSwap DEX execution
    - Comprehensive error handling and monitoring
    """
    
    def __init__(self, poc_config: NautilusPOCConfig):
        """
        Initialize Q50 NautilusTrader Strategy.
        
        Args:
            poc_config: Complete NautilusTrader POC configuration
        """
        # Create appropriate strategy config based on availability
        if NAUTILUS_AVAILABLE:
            # Create proper StrategyConfig for production NautilusTrader
            strategy_config = Q50StrategyConfig(
                strategy_id=poc_config.nautilus.instance_id,
                instrument_id="SOL/USDC"
            )
            super().__init__(config=strategy_config)
        else:
            # Mock initialization for testing
            mock_config = Q50StrategyConfig(poc_config=poc_config)
            super().__init__(config=mock_config)
        
        # Store POC configuration
        self.poc_config = poc_config
        
        # Initialize core components
        try:
            self.signal_loader = Q50SignalLoader(self._convert_config_for_components())
        except Exception as e:
            logger.warning(f"Failed to initialize signal loader with database: {e}")
            # Create a mock signal loader for testing
            self.signal_loader = Mock()
            self.signal_loader.load_signals = AsyncMock(return_value=False)
            self.signal_loader.get_signal_for_timestamp = AsyncMock(return_value=None)
            self.signal_loader.get_signal_statistics = Mock(return_value={})
            self.signal_loader.health_check = Mock(return_value={'signals_loaded': False})
            self.signal_loader.close_async = AsyncMock()
        
        self.regime_detector = RegimeDetector(self._convert_config_for_components())
        
        # Initialize trading components
        self.pumpswap_executor = PumpSwapExecutor(self.poc_config)
        self.liquidity_validator = LiquidityValidator(self.poc_config)
        
        # Convert config for components that expect dictionary format
        dict_config = self._convert_poc_config_to_dict()
        self.position_sizer = KellyPositionSizer(dict_config)
        self.risk_manager = RiskManager(dict_config)
        
        # Set up component dependencies
        self.pumpswap_executor.set_dependencies(
            self.liquidity_validator,
            None,  # Position manager will be set up later
            self.risk_manager
        )
        
        # Strategy state
        self._is_strategy_initialized = False
        self.last_signal_timestamp = None
        self.processed_signals_count = 0
        self.trading_enabled = True
        
        # Performance tracking
        self.signal_processing_times = []
        self.trade_decisions = []
        self.error_count = 0
        
        # Configuration validation
        self._validate_configuration()
        
        logger.info(f"Q50NautilusStrategy initialized with instance_id: {poc_config.nautilus.instance_id}")
    
    def _convert_config_for_components(self) -> Dict[str, Any]:
        """Convert NautilusPOCConfig to dictionary format for components"""
        return {
            'q50': {
                'features_path': self.poc_config.q50.features_path,
                'signal_tolerance_minutes': self.poc_config.q50.signal_tolerance_minutes,
                'required_columns': self.poc_config.q50.required_columns
            },
            'regime_detection': self.poc_config.regime_detection,
            'database': {
                # Mock database configuration for testing
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_password'
            }
        }
    
    def _convert_poc_config_to_dict(self) -> Dict[str, Any]:
        """Convert NautilusPOCConfig to full dictionary format"""
        return {
            'pumpswap': {
                'payer_public_key': self.poc_config.pumpswap.payer_public_key,
                'private_key_path': self.poc_config.pumpswap.private_key_path,
                'max_slippage_percent': self.poc_config.pumpswap.max_slippage_percent,
                'base_position_size': self.poc_config.pumpswap.base_position_size,
                'max_position_size': self.poc_config.pumpswap.max_position_size,
                'min_liquidity_sol': self.poc_config.pumpswap.min_liquidity_sol,
                'max_price_impact_percent': self.poc_config.pumpswap.max_price_impact_percent,
                'stop_loss_percent': self.poc_config.pumpswap.stop_loss_percent,
                'position_timeout_hours': self.poc_config.pumpswap.position_timeout_hours
            },
            'regime_detection': self.poc_config.regime_detection,
            'solana': {
                'network': self.poc_config.solana.network,
                'rpc_endpoint': self.poc_config.solana.rpc_endpoint,
                'commitment': self.poc_config.solana.commitment
            },
            'error_handling': self.poc_config.error_handling,
            'monitoring': self.poc_config.monitoring
        }
    
    def _validate_configuration(self) -> None:
        """Validate strategy configuration"""
        errors = []
        
        # Validate Q50 configuration
        if not self.poc_config.q50.features_path:
            errors.append("Q50 features_path is required")
        
        # Validate PumpSwap configuration
        if not self.poc_config.pumpswap.payer_public_key:
            errors.append("PumpSwap payer_public_key is required")
        
        # Validate Solana configuration
        if not self.poc_config.solana.rpc_endpoint:
            errors.append("Solana RPC endpoint is required")
        
        if errors:
            error_msg = "Configuration validation failed: " + "; ".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Strategy configuration validated successfully")
    
    async def on_start(self) -> None:
        """
        Initialize strategy and load Q50 signals.
        
        This method is called by NautilusTrader when the strategy starts.
        It handles loading Q50 signals and initializing all components.
        """
        try:
            logger.info("Starting Q50 NautilusTrader Strategy")
            
            # Load Q50 signals
            signals_loaded = await self.signal_loader.load_signals()
            if not signals_loaded:
                raise RuntimeError("Failed to load Q50 signals")
            
            # Get signal statistics for logging
            signal_stats = self.signal_loader.get_signal_statistics()
            logger.info(f"Loaded {signal_stats.get('total_signals', 0)} Q50 signals")
            logger.info(f"Tradeable signals: {signal_stats.get('tradeable_signals', 0)}")
            logger.info(f"Date range: {signal_stats.get('date_range', {}).get('start')} to {signal_stats.get('date_range', {}).get('end')}")
            
            # Initialize regime detector with historical data if available
            try:
                if hasattr(self.signal_loader, 'signals_df') and self.signal_loader.signals_df is not None:
                    vol_risk_history = self.signal_loader.signals_df['vol_risk'].dropna().tolist()
                    self.regime_detector.load_historical_data(vol_risk_history)
                    logger.info(f"Loaded {len(vol_risk_history)} historical vol_risk observations for regime detection")
            except Exception as e:
                logger.debug(f"Could not load historical data for regime detector: {e}")
                # Continue without historical data
            
            # Validate components
            health_check = self.signal_loader.health_check()
            if not health_check.get('signals_loaded', False):
                raise RuntimeError("Signal loader health check failed")
            
            self._is_strategy_initialized = True
            logger.info("Q50 NautilusTrader Strategy started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Q50 strategy: {e}")
            self.error_count += 1
            raise
    
    async def on_stop(self) -> None:
        """
        Clean up strategy resources.
        
        This method is called by NautilusTrader when the strategy stops.
        """
        try:
            logger.info("Stopping Q50 NautilusTrader Strategy")
            
            # Close signal loader
            await self.signal_loader.close_async()
            
            # Log final performance metrics
            self._log_final_performance()
            
            logger.info("Q50 NautilusTrader Strategy stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping Q50 strategy: {e}")
    
    async def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        Process market data tick and execute Q50 signals.
        
        This is the main entry point for market data processing.
        It retrieves Q50 signals, applies regime detection, and makes trading decisions.
        
        Args:
            tick: Market data quote tick from NautilusTrader
        """
        if not self._is_strategy_initialized:
            logger.warning("Strategy not initialized, skipping tick processing")
            return
        
        if not self.trading_enabled:
            logger.debug("Trading disabled, skipping tick processing")
            return
        
        start_time = datetime.now()
        
        try:
            # Convert tick timestamp to pandas Timestamp
            tick_timestamp = pd.Timestamp(tick.ts_event, unit='ns')
            
            logger.debug(f"Processing tick for {tick.instrument_id} at {tick_timestamp}")
            
            # Get Q50 signal for current timestamp
            current_signal = await self.signal_loader.get_signal_for_timestamp(tick_timestamp)
            
            if not current_signal:
                logger.debug(f"No Q50 signal found for timestamp {tick_timestamp}")
                return
            
            # Check if we've already processed this signal
            signal_timestamp = current_signal.get('timestamp')
            if signal_timestamp == self.last_signal_timestamp:
                logger.debug("Signal already processed, skipping")
                return
            
            # Enhance signal with regime analysis
            regime_data = self.regime_detector.classify_regime(current_signal)
            enhanced_signal = self.regime_detector.apply_regime_adjustments(current_signal, regime_data)
            
            # Apply additional signal enhancements
            enhanced_signal = self._apply_signal_enhancements(enhanced_signal, tick)
            
            # Add tick information to signal
            enhanced_signal['tick_data'] = {
                'instrument_id': str(tick.instrument_id),
                'bid_price': float(tick.bid_price),
                'ask_price': float(tick.ask_price),
                'bid_size': float(tick.bid_size),
                'ask_size': float(tick.ask_size),
                'timestamp': tick_timestamp
            }
            
            # Make trading decision
            await self._process_trading_signal(enhanced_signal, tick)
            
            # Update tracking
            self.last_signal_timestamp = signal_timestamp
            self.processed_signals_count += 1
            
            # Record processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.signal_processing_times.append(processing_time)
            
            logger.debug(f"Processed signal in {processing_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"Error processing quote tick: {e}")
            self.error_count += 1
    
    async def _process_trading_signal(self, enhanced_signal: Dict[str, Any], tick: QuoteTick) -> None:
        """
        Process enhanced Q50 signal and make trading decisions.
        
        This method implements the core trading decision logic based on Q50 values,
        regime analysis, and comprehensive signal validation.
        
        Args:
            enhanced_signal: Q50 signal enhanced with regime analysis
            tick: Market data tick
        """
        try:
            # Extract key signal values
            q50_value = enhanced_signal.get('q50', 0.0)
            q10_value = enhanced_signal.get('q10', 0.0)
            q90_value = enhanced_signal.get('q90', 0.0)
            prob_up = enhanced_signal.get('prob_up', 0.5)
            vol_risk = enhanced_signal.get('vol_risk', 0.1)
            
            # Get regime-adjusted values
            tradeable = enhanced_signal.get('regime_adjusted_tradeable', False)
            economically_significant = enhanced_signal.get('regime_adjusted_economically_significant', False)
            regime_info = enhanced_signal.get('regime_info', {})
            regime = regime_info.get('regime', 'unknown')
            regime_confidence = regime_info.get('regime_confidence', 0.5)
            
            # Create comprehensive trade decision record
            trade_decision = {
                'timestamp': pd.Timestamp.now(),
                'instrument_id': str(tick.instrument_id),
                'q50_value': q50_value,
                'q10_value': q10_value,
                'q90_value': q90_value,
                'prob_up': prob_up,
                'vol_risk': vol_risk,
                'tradeable': tradeable,
                'economically_significant': economically_significant,
                'regime': regime,
                'regime_confidence': regime_confidence,
                'action': 'hold',  # Default action
                'reason': '',
                'signal_strength': 0.0,
                'expected_return': 0.0,
                'risk_score': 0.0,
                'signal_data': enhanced_signal
            }
            
            # Calculate signal strength and expected return
            signal_strength = self._calculate_signal_strength(enhanced_signal)
            expected_return = self._calculate_expected_return(enhanced_signal)
            risk_score = self._calculate_risk_score(enhanced_signal)
            
            trade_decision['signal_strength'] = signal_strength
            trade_decision['expected_return'] = expected_return
            trade_decision['risk_score'] = risk_score
            
            # Apply comprehensive trading decision logic
            decision_result = await self._make_trading_decision(enhanced_signal, trade_decision)
            
            # Update trade decision with result
            trade_decision.update(decision_result)
            
            # Execute the trading action
            if trade_decision['action'] == 'buy':
                await self._execute_buy_signal(enhanced_signal, tick)
            elif trade_decision['action'] == 'sell':
                await self._execute_sell_signal(enhanced_signal, tick)
            # 'hold' action requires no execution
            
            # Store trade decision
            self.trade_decisions.append(trade_decision)
            
            # Log comprehensive trade decision
            logger.info(f"Trade decision: {trade_decision['action']} for {tick.instrument_id}")
            logger.info(f"  Q50: {q50_value:.4f}, Signal strength: {signal_strength:.3f}")
            logger.info(f"  Expected return: {expected_return:.4f}, Risk score: {risk_score:.3f}")
            logger.info(f"  Regime: {regime} (confidence: {regime_confidence:.2f})")
            logger.info(f"  Reason: {trade_decision['reason']}")
            
        except Exception as e:
            logger.error(f"Error processing trading signal: {e}")
            self.error_count += 1
    
    def _calculate_signal_strength(self, enhanced_signal: Dict[str, Any]) -> float:
        """
        Calculate comprehensive signal strength based on Q50 and regime data.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime information
            
        Returns:
            Signal strength score (0-1)
        """
        try:
            q50_value = abs(enhanced_signal.get('q50', 0.0))
            prob_up = enhanced_signal.get('prob_up', 0.5)
            vol_risk = enhanced_signal.get('vol_risk', 0.1)
            
            # Get regime adjustments
            regime_info = enhanced_signal.get('regime_info', {})
            regime_multiplier = regime_info.get('regime_multiplier', 1.0)
            enhanced_info_ratio = regime_info.get('enhanced_info_ratio', 0.0)
            regime_confidence = regime_info.get('regime_confidence', 0.5)
            
            # Base signal strength from Q50 value
            base_strength = min(q50_value * 10, 1.0)  # Scale Q50 to 0-1 range
            
            # Probability adjustment (higher confidence for extreme probabilities)
            prob_adjustment = abs(prob_up - 0.5) * 2  # 0-1 range
            
            # Volatility adjustment (lower strength in high volatility)
            vol_adjustment = max(0.1, 1.0 - vol_risk)
            
            # Regime-based enhancement
            regime_enhancement = regime_multiplier * regime_confidence
            
            # Information ratio contribution
            info_ratio_contribution = min(enhanced_info_ratio / 2.0, 0.5)
            
            # Combined signal strength
            signal_strength = (
                base_strength * 0.4 +
                prob_adjustment * 0.2 +
                vol_adjustment * 0.2 +
                regime_enhancement * 0.1 +
                info_ratio_contribution * 0.1
            )
            
            return min(max(signal_strength, 0.0), 1.0)  # Clamp to 0-1
            
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
            return 0.0
    
    def _calculate_expected_return(self, enhanced_signal: Dict[str, Any]) -> float:
        """
        Calculate expected return based on Q50 signal and probability.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime information
            
        Returns:
            Expected return (can be negative)
        """
        try:
            q50_value = enhanced_signal.get('q50', 0.0)
            prob_up = enhanced_signal.get('prob_up', 0.5)
            
            # Get regime adjustments
            regime_info = enhanced_signal.get('regime_info', {})
            threshold_adjustment = regime_info.get('threshold_adjustment', 0.0)
            
            # Calculate potential gain/loss based on Q50 quantile
            potential_gain = abs(q50_value) if q50_value > 0 else 0
            potential_loss = abs(q50_value) if q50_value < 0 else 0
            
            # Expected value calculation with regime adjustment
            expected_return = (prob_up * potential_gain) - ((1 - prob_up) * potential_loss)
            
            # Apply regime threshold adjustment
            adjusted_return = expected_return * (1 + threshold_adjustment)
            
            return adjusted_return
            
        except Exception as e:
            logger.error(f"Error calculating expected return: {e}")
            return 0.0
    
    def _calculate_risk_score(self, enhanced_signal: Dict[str, Any]) -> float:
        """
        Calculate risk score based on volatility and regime analysis.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime information
            
        Returns:
            Risk score (0-1, higher is riskier)
        """
        try:
            vol_risk = enhanced_signal.get('vol_risk', 0.1)
            vol_raw = enhanced_signal.get('vol_raw', 0.1)
            
            # Get regime information
            regime_info = enhanced_signal.get('regime_info', {})
            regime = regime_info.get('regime', 'medium_variance')
            regime_confidence = regime_info.get('regime_confidence', 0.5)
            
            # Base risk from volatility measures
            vol_risk_score = min(vol_risk * 10, 1.0)  # Scale to 0-1
            vol_raw_score = min(vol_raw * 5, 1.0)
            
            # Regime-based risk adjustment
            regime_risk_multipliers = {
                'low_variance': 0.7,
                'medium_variance': 1.0,
                'high_variance': 1.3,
                'extreme_variance': 1.8
            }
            regime_multiplier = regime_risk_multipliers.get(regime, 1.0)
            
            # Confidence adjustment (lower confidence = higher risk)
            confidence_adjustment = 1.0 - (regime_confidence * 0.3)
            
            # Combined risk score
            risk_score = (
                vol_risk_score * 0.5 +
                vol_raw_score * 0.3 +
                (regime_multiplier - 1.0) * 0.2
            ) * confidence_adjustment
            
            return min(max(risk_score, 0.0), 1.0)  # Clamp to 0-1
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 0.5  # Default medium risk
    
    async def _make_trading_decision(self, enhanced_signal: Dict[str, Any], trade_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make comprehensive trading decision based on signal analysis.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime information
            trade_decision: Current trade decision data
            
        Returns:
            Dictionary with updated action and reason
        """
        try:
            q50_value = enhanced_signal.get('q50', 0.0)
            tradeable = enhanced_signal.get('regime_adjusted_tradeable', False)
            economically_significant = enhanced_signal.get('regime_adjusted_economically_significant', False)
            high_quality = enhanced_signal.get('high_quality', False)
            
            signal_strength = trade_decision['signal_strength']
            expected_return = trade_decision['expected_return']
            risk_score = trade_decision['risk_score']
            
            # Get regime information
            regime_info = enhanced_signal.get('regime_info', {})
            regime = regime_info.get('regime', 'unknown')
            regime_confidence = regime_info.get('regime_confidence', 0.5)
            
            # Decision thresholds (configurable)
            min_signal_strength = 0.3
            min_expected_return = 0.0005  # 5 bps
            max_risk_score = 0.8
            min_regime_confidence = 0.4
            
            # Adjust thresholds based on regime
            if regime == 'extreme_variance':
                min_signal_strength = 0.5
                min_expected_return = 0.001  # 10 bps
                min_regime_confidence = 0.6
            elif regime == 'low_variance':
                min_signal_strength = 0.2
                min_expected_return = 0.0003  # 3 bps
            
            # Primary decision logic
            decision_result = {'action': 'hold', 'reason': 'default_hold'}
            
            # Check basic signal validity
            if not tradeable:
                decision_result = {
                    'action': 'hold',
                    'reason': 'signal_not_tradeable'
                }
            elif not economically_significant:
                decision_result = {
                    'action': 'hold',
                    'reason': 'not_economically_significant'
                }
            elif not high_quality:
                decision_result = {
                    'action': 'hold',
                    'reason': 'low_quality_signal'
                }
            elif signal_strength < min_signal_strength:
                decision_result = {
                    'action': 'hold',
                    'reason': f'weak_signal_strength_{signal_strength:.3f}'
                }
            elif expected_return < min_expected_return:
                decision_result = {
                    'action': 'hold',
                    'reason': f'insufficient_expected_return_{expected_return:.4f}'
                }
            elif risk_score > max_risk_score:
                decision_result = {
                    'action': 'hold',
                    'reason': f'excessive_risk_{risk_score:.3f}'
                }
            elif regime_confidence < min_regime_confidence:
                decision_result = {
                    'action': 'hold',
                    'reason': f'low_regime_confidence_{regime_confidence:.3f}'
                }
            else:
                # Signal passes all checks - determine buy/sell/hold
                if q50_value > 0:
                    # Positive signal - consider buy
                    decision_result = await self._evaluate_buy_decision(enhanced_signal, trade_decision)
                elif q50_value < 0:
                    # Negative signal - consider sell
                    decision_result = await self._evaluate_sell_decision(enhanced_signal, trade_decision)
                else:
                    # Neutral signal
                    decision_result = {
                        'action': 'hold',
                        'reason': 'neutral_q50_signal'
                    }
            
            return decision_result
            
        except Exception as e:
            logger.error(f"Error making trading decision: {e}")
            return {'action': 'hold', 'reason': f'decision_error_{str(e)}'}
    
    async def _evaluate_buy_decision(self, enhanced_signal: Dict[str, Any], trade_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether to execute a buy decision.
        
        Args:
            enhanced_signal: Enhanced Q50 signal
            trade_decision: Current trade decision data
            
        Returns:
            Dictionary with buy decision and reason
        """
        try:
            q50_value = enhanced_signal.get('q50', 0.0)
            signal_strength = trade_decision['signal_strength']
            expected_return = trade_decision['expected_return']
            
            # Check if we already have a position (simplified check)
            # In a full implementation, this would check actual position manager
            mint_address = enhanced_signal.get('mint_address', 'unknown')
            
            # For now, assume we can always buy (position manager integration needed)
            can_buy = True
            
            if not can_buy:
                return {
                    'action': 'hold',
                    'reason': 'already_have_position'
                }
            
            # Additional buy-specific checks
            if q50_value < 0.01:  # Minimum positive signal threshold
                return {
                    'action': 'hold',
                    'reason': f'q50_too_small_{q50_value:.4f}'
                }
            
            # Strong buy signal criteria
            if signal_strength > 0.7 and expected_return > 0.001:
                return {
                    'action': 'buy',
                    'reason': f'strong_buy_signal_strength_{signal_strength:.3f}_return_{expected_return:.4f}'
                }
            
            # Regular buy signal
            return {
                'action': 'buy',
                'reason': f'buy_signal_q50_{q50_value:.4f}_strength_{signal_strength:.3f}'
            }
            
        except Exception as e:
            logger.error(f"Error evaluating buy decision: {e}")
            return {'action': 'hold', 'reason': f'buy_evaluation_error_{str(e)}'}
    
    async def _evaluate_sell_decision(self, enhanced_signal: Dict[str, Any], trade_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether to execute a sell decision.
        
        Args:
            enhanced_signal: Enhanced Q50 signal
            trade_decision: Current trade decision data
            
        Returns:
            Dictionary with sell decision and reason
        """
        try:
            q50_value = enhanced_signal.get('q50', 0.0)
            signal_strength = trade_decision['signal_strength']
            expected_return = trade_decision['expected_return']
            
            # Check if we have a position to sell (simplified check)
            # In a full implementation, this would check actual position manager
            mint_address = enhanced_signal.get('mint_address', 'unknown')
            
            # For now, assume we might have a position (position manager integration needed)
            has_position = True  # This should be checked via position manager
            
            if not has_position:
                return {
                    'action': 'hold',
                    'reason': 'no_position_to_sell'
                }
            
            # Additional sell-specific checks
            if q50_value > -0.01:  # Minimum negative signal threshold
                return {
                    'action': 'hold',
                    'reason': f'q50_not_negative_enough_{q50_value:.4f}'
                }
            
            # Strong sell signal criteria
            if signal_strength > 0.7 and abs(expected_return) > 0.001:
                return {
                    'action': 'sell',
                    'reason': f'strong_sell_signal_strength_{signal_strength:.3f}_return_{expected_return:.4f}'
                }
            
            # Regular sell signal
            return {
                'action': 'sell',
                'reason': f'sell_signal_q50_{q50_value:.4f}_strength_{signal_strength:.3f}'
            }
            
        except Exception as e:
            logger.error(f"Error evaluating sell decision: {e}")
            return {'action': 'hold', 'reason': f'sell_evaluation_error_{str(e)}'}
    
    def _apply_signal_enhancements(self, enhanced_signal: Dict[str, Any], tick: QuoteTick) -> Dict[str, Any]:
        """
        Apply additional signal enhancements beyond regime analysis.
        
        Args:
            enhanced_signal: Signal already enhanced with regime data
            tick: Market data tick
            
        Returns:
            Further enhanced signal with additional analysis
        """
        try:
            # Add market data context
            enhanced_signal['market_context'] = {
                'bid_ask_spread': float(tick.ask_price - tick.bid_price),
                'mid_price': float((tick.bid_price + tick.ask_price) / 2),
                'bid_ask_ratio': float(tick.bid_size / max(tick.ask_size, 0.001)),
                'tick_timestamp': pd.Timestamp(tick.ts_event, unit='ns')
            }
            
            # Calculate spread-based liquidity indicator
            spread_pct = enhanced_signal['market_context']['bid_ask_spread'] / enhanced_signal['market_context']['mid_price']
            enhanced_signal['market_context']['spread_percent'] = spread_pct * 100
            
            # Adjust tradeable status based on spread
            if spread_pct > 0.05:  # 5% spread threshold
                enhanced_signal['regime_adjusted_tradeable'] = False
                enhanced_signal['spread_adjustment_reason'] = f'excessive_spread_{spread_pct:.3f}'
            
            # Add signal timing analysis
            signal_timestamp = enhanced_signal.get('timestamp')
            if signal_timestamp:
                time_diff = (pd.Timestamp.now() - signal_timestamp).total_seconds()
                enhanced_signal['signal_age_seconds'] = time_diff
                
                # Reduce signal strength for old signals
                if time_diff > 300:  # 5 minutes
                    age_penalty = min(time_diff / 3600, 0.5)  # Max 50% penalty after 1 hour
                    if 'regime_adjusted_signal_strength' in enhanced_signal:
                        enhanced_signal['regime_adjusted_signal_strength'] *= (1 - age_penalty)
                    enhanced_signal['age_penalty_applied'] = age_penalty
            
            # Add confidence scoring
            confidence_factors = []
            
            # High quality signal factor
            if enhanced_signal.get('high_quality', False):
                confidence_factors.append(0.2)
            
            # Economic significance factor
            if enhanced_signal.get('regime_adjusted_economically_significant', False):
                confidence_factors.append(0.2)
            
            # Regime confidence factor
            regime_confidence = enhanced_signal.get('regime_info', {}).get('regime_confidence', 0.5)
            confidence_factors.append(regime_confidence * 0.3)
            
            # Signal strength factor
            signal_strength = enhanced_signal.get('regime_adjusted_signal_strength', 0)
            confidence_factors.append(min(signal_strength, 0.3))
            
            # Combined confidence score
            enhanced_signal['overall_confidence'] = sum(confidence_factors)
            
            return enhanced_signal
            
        except Exception as e:
            logger.error(f"Error applying signal enhancements: {e}")
            return enhanced_signal
    
    def get_current_positions(self) -> Dict[str, Any]:
        """
        Get current trading positions (placeholder for position manager integration).
        
        Returns:
            Dictionary of current positions
        """
        # This is a placeholder - in full implementation, this would
        # integrate with the position manager component
        return {}
    
    def get_trading_performance(self) -> Dict[str, Any]:
        """
        Get comprehensive trading performance metrics.
        
        Returns:
            Dictionary containing performance analysis
        """
        try:
            if not self.trade_decisions:
                return {'status': 'no_trades'}
            
            # Analyze trade decisions
            actions = [d['action'] for d in self.trade_decisions]
            buy_count = actions.count('buy')
            sell_count = actions.count('sell')
            hold_count = actions.count('hold')
            
            # Calculate signal strength statistics
            signal_strengths = [d.get('signal_strength', 0) for d in self.trade_decisions]
            avg_signal_strength = sum(signal_strengths) / len(signal_strengths) if signal_strengths else 0
            
            # Calculate expected return statistics
            expected_returns = [d.get('expected_return', 0) for d in self.trade_decisions]
            avg_expected_return = sum(expected_returns) / len(expected_returns) if expected_returns else 0
            
            # Regime analysis
            regimes = [d.get('regime', 'unknown') for d in self.trade_decisions]
            regime_counts = {}
            for regime in regimes:
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            # Recent performance (last 100 decisions)
            recent_decisions = self.trade_decisions[-100:] if len(self.trade_decisions) > 100 else self.trade_decisions
            recent_actions = [d['action'] for d in recent_decisions]
            
            return {
                'total_decisions': len(self.trade_decisions),
                'buy_signals': buy_count,
                'sell_signals': sell_count,
                'hold_signals': hold_count,
                'buy_percentage': (buy_count / len(self.trade_decisions)) * 100,
                'sell_percentage': (sell_count / len(self.trade_decisions)) * 100,
                'hold_percentage': (hold_count / len(self.trade_decisions)) * 100,
                'average_signal_strength': avg_signal_strength,
                'average_expected_return': avg_expected_return,
                'regime_distribution': regime_counts,
                'recent_performance': {
                    'decisions': len(recent_decisions),
                    'buy_signals': recent_actions.count('buy'),
                    'sell_signals': recent_actions.count('sell'),
                    'hold_signals': recent_actions.count('hold')
                },
                'first_decision': self.trade_decisions[0]['timestamp'].isoformat(),
                'last_decision': self.trade_decisions[-1]['timestamp'].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating trading performance: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def _execute_buy_signal(self, enhanced_signal: Dict[str, Any], tick: QuoteTick) -> None:
        """
        Execute buy signal via PumpSwap.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime data
            tick: Market data tick
        """
        try:
            logger.info(f"Executing buy signal for {tick.instrument_id}")
            
            # Execute buy via PumpSwap executor
            execution_result = await self.pumpswap_executor.execute_buy_signal(
                enhanced_signal, 
                enhanced_signal.get('tick_data')
            )
            
            # Log execution result
            if execution_result.get('status') == 'executed':
                logger.info(f"Buy order executed successfully: {execution_result.get('trade_id')}")
                logger.info(f"SOL amount: {execution_result.get('sol_amount')}, "
                           f"Token amount: {execution_result.get('token_amount')}")
                
                # Monitor transaction if hash is available
                tx_hash = execution_result.get('transaction_hash')
                if tx_hash:
                    asyncio.create_task(self._monitor_transaction(tx_hash))
                    
            elif execution_result.get('status') == 'skipped':
                logger.info(f"Buy order skipped: {execution_result.get('reason')}")
                
            elif execution_result.get('status') == 'rejected':
                logger.warning(f"Buy order rejected: {execution_result.get('reason')}")
                
            else:
                logger.error(f"Buy order failed: {execution_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error executing buy signal: {e}")
            self.error_count += 1
    
    async def _execute_sell_signal(self, enhanced_signal: Dict[str, Any], tick: QuoteTick) -> None:
        """
        Execute sell signal via PumpSwap.
        
        Args:
            enhanced_signal: Enhanced Q50 signal with regime data
            tick: Market data tick
        """
        try:
            logger.info(f"Executing sell signal for {tick.instrument_id}")
            
            # Execute sell via PumpSwap executor
            execution_result = await self.pumpswap_executor.execute_sell_signal(
                enhanced_signal,
                enhanced_signal.get('tick_data')
            )
            
            # Log execution result
            if execution_result.get('status') == 'executed':
                logger.info(f"Sell order executed successfully: {execution_result.get('trade_id')}")
                logger.info(f"Token amount: {execution_result.get('token_amount')}, "
                           f"SOL amount: {execution_result.get('sol_amount')}")
                logger.info(f"P&L: {execution_result.get('pnl_sol', 0):.4f} SOL")
                
                # Monitor transaction if hash is available
                tx_hash = execution_result.get('transaction_hash')
                if tx_hash:
                    asyncio.create_task(self._monitor_transaction(tx_hash))
                    
            elif execution_result.get('status') == 'skipped':
                logger.info(f"Sell order skipped: {execution_result.get('reason')}")
                
            else:
                logger.error(f"Sell order failed: {execution_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error executing sell signal: {e}")
            self.error_count += 1
    
    async def _monitor_transaction(self, transaction_hash: str) -> None:
        """
        Monitor transaction confirmation in background.
        
        Args:
            transaction_hash: Transaction hash to monitor
        """
        try:
            logger.debug(f"Monitoring transaction: {transaction_hash}")
            
            result = await self.pumpswap_executor.monitor_transaction(transaction_hash)
            
            if result.get('status') == 'confirmed':
                logger.info(f"Transaction confirmed: {transaction_hash} "
                           f"(confirmation time: {result.get('confirmation_time', 0):.2f}s)")
            elif result.get('status') == 'timeout':
                logger.warning(f"Transaction monitoring timeout: {transaction_hash}")
            else:
                logger.error(f"Transaction monitoring failed: {transaction_hash}")
                
        except Exception as e:
            logger.error(f"Error monitoring transaction {transaction_hash}: {e}")
    
    def on_event(self, event: Event) -> None:
        """
        Handle NautilusTrader events.
        
        Args:
            event: NautilusTrader event
        """
        try:
            logger.debug(f"Received event: {type(event).__name__}")
            
            # Handle specific event types if needed
            # For now, we'll just log the event
            
        except Exception as e:
            logger.error(f"Error handling event: {e}")
            self.error_count += 1
    
    def enable_trading(self) -> None:
        """Enable trading signal processing"""
        self.trading_enabled = True
        logger.info("Trading enabled")
    
    def disable_trading(self) -> None:
        """Disable trading signal processing"""
        self.trading_enabled = False
        logger.info("Trading disabled")
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive strategy statistics.
        
        Returns:
            Dictionary containing strategy performance metrics
        """
        try:
            # Basic statistics
            stats = {
                'is_initialized': self._is_strategy_initialized,
                'trading_enabled': self.trading_enabled,
                'processed_signals_count': self.processed_signals_count,
                'error_count': self.error_count,
                'last_signal_timestamp': self.last_signal_timestamp.isoformat() if self.last_signal_timestamp else None
            }
            
            # Signal processing performance
            if self.signal_processing_times:
                stats['signal_processing'] = {
                    'average_time_ms': sum(self.signal_processing_times) / len(self.signal_processing_times),
                    'min_time_ms': min(self.signal_processing_times),
                    'max_time_ms': max(self.signal_processing_times),
                    'total_processed': len(self.signal_processing_times)
                }
            
            # Trade decision statistics
            if self.trade_decisions:
                actions = [d['action'] for d in self.trade_decisions]
                stats['trade_decisions'] = {
                    'total_decisions': len(self.trade_decisions),
                    'buy_signals': actions.count('buy'),
                    'sell_signals': actions.count('sell'),
                    'hold_signals': actions.count('hold'),
                    'last_decision_time': self.trade_decisions[-1]['timestamp'].isoformat()
                }
            
            # Component statistics
            stats['signal_loader'] = self.signal_loader.get_signal_statistics()
            stats['regime_detector'] = self.regime_detector.get_regime_statistics()
            stats['pumpswap_executor'] = self.pumpswap_executor.get_performance_metrics()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting strategy statistics: {e}")
            return {'error': str(e)}
    
    def _log_final_performance(self) -> None:
        """Log final performance metrics when strategy stops"""
        try:
            stats = self.get_strategy_statistics()
            
            logger.info("=== Q50 NautilusTrader Strategy Final Performance ===")
            logger.info(f"Processed signals: {stats.get('processed_signals_count', 0)}")
            logger.info(f"Errors encountered: {stats.get('error_count', 0)}")
            
            # Signal processing performance
            signal_perf = stats.get('signal_processing', {})
            if signal_perf:
                logger.info(f"Average signal processing time: {signal_perf.get('average_time_ms', 0):.2f}ms")
            
            # Trade decisions
            trade_stats = stats.get('trade_decisions', {})
            if trade_stats:
                logger.info(f"Total trade decisions: {trade_stats.get('total_decisions', 0)}")
                logger.info(f"Buy signals: {trade_stats.get('buy_signals', 0)}")
                logger.info(f"Sell signals: {trade_stats.get('sell_signals', 0)}")
                logger.info(f"Hold signals: {trade_stats.get('hold_signals', 0)}")
            
            # Execution performance
            exec_stats = stats.get('pumpswap_executor', {})
            if exec_stats:
                logger.info(f"Total trades executed: {exec_stats.get('total_trades', 0)}")
                logger.info(f"Success rate: {exec_stats.get('success_rate_percent', 0):.1f}%")
                logger.info(f"Total volume: {exec_stats.get('total_volume_sol', 0):.4f} SOL")
            
            logger.info("=== End Performance Summary ===")
            
        except Exception as e:
            logger.error(f"Error logging final performance: {e}")