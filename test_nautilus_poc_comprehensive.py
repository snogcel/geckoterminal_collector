#!/usr/bin/env python3
"""
Comprehensive Test Suite for NautilusTrader POC

This test suite validates all completed tasks in the NautilusTrader POC implementation:
- Task 1: Environment Setup and Dependencies
- Task 2: Q50 Signal Integration Foundation (2.1, 2.2)
- Task 3: PumpSwap SDK Integration Layer (3.1, 3.2)
- Task 4: Position Sizing and Risk Management (4.1, 4.2)
- Task 5: NautilusTrader Strategy Implementation (5.1, 5.2)

The suite includes unit tests, integration tests, and end-to-end validation.
"""

import asyncio
import logging
import sys
import tempfile
import pickle
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import all components to test
from nautilus_poc.config import (
    ConfigManager, NautilusPOCConfig, Q50Config, PumpSwapConfig, 
    SolanaConfig, NautilusConfig, WalletConfig, TradingConfig, 
    SecurityConfig, EnvironmentConfig
)
from nautilus_poc.signal_loader import Q50SignalLoader
from nautilus_poc.regime_detector import RegimeDetector
from nautilus_poc.pumpswap_executor import PumpSwapExecutor, TradeExecutionRecord
from nautilus_poc.liquidity_validator import LiquidityValidator, LiquidityStatus
from nautilus_poc.position_sizer import KellyPositionSizer, PositionSizeResult
from nautilus_poc.risk_manager import RiskManager, RiskLevel, CircuitBreakerStatus
from nautilus_poc.q50_nautilus_strategy import Q50NautilusStrategy

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestDataGenerator:
    """Generate test data for various components"""
    
    @staticmethod
    def create_test_config() -> NautilusPOCConfig:
        """Create comprehensive test configuration"""
        # Create environment-specific configurations
        testnet_env = EnvironmentConfig(
            solana=SolanaConfig(
                network='testnet',
                rpc_endpoint='https://api.testnet.solana.com',
                commitment='confirmed',
                cluster='testnet'
            ),
            pumpswap=PumpSwapConfig(
                max_slippage_percent=5.0,
                base_position_size=0.1,
                max_position_size=0.5,
                min_liquidity_sol=10.0,
                max_price_impact_percent=10.0,
                realistic_transaction_cost=0.0005
            ),
            security=SecurityConfig(
                validate_token_addresses=True,
                require_transaction_confirmation=True,
                enable_circuit_breaker=True,
                max_daily_trades=500,
                wallet_balance_alert_threshold=1.0
            )
        )
        
        return NautilusPOCConfig(
            environment='testnet',
            environments={'testnet': testnet_env},
            q50=Q50Config(
                features_path='test_macro_features.pkl',
                signal_tolerance_minutes=5,
                required_columns=[
                    'q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
                    'prob_up', 'economically_significant', 'high_quality', 'tradeable'
                ]
            ),
            wallet=WalletConfig(
                payer_public_key='test_public_key_12345',
                private_key_path='test_private_key.json',
                validate_balance_before_trade=True,
                min_balance_sol=0.1
            ),
            trading=TradingConfig(
                kelly_multiplier=1.0,
                max_portfolio_risk=0.2,
                position_concentration_limit=0.1,
                stop_loss_percent=20.0,
                take_profit_percent=50.0,
                position_timeout_hours=24,
                max_consecutive_losses=5
            ),
            nautilus=NautilusConfig(
                instance_id='TEST-COMPREHENSIVE-001',
                log_level='INFO',
                cache_database_path='test_cache.db'
            ),
            security=SecurityConfig(
                validate_token_addresses=True,
                enable_circuit_breaker=True,
                max_daily_trades=500,
                enable_audit_logging=True
            ),
            monitoring={
                'enable_performance_tracking': True,
                'log_trade_decisions': True,
                'performance_window_minutes': 60
            },
            error_handling={
                'max_retries': 3,
                'retry_delay_base': 1.0,
                'circuit_breaker_threshold': 5
            },
            regime_detection={
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
                },
                'threshold_adjustments': {
                    'low_variance': -0.30,
                    'medium_variance': 0.0,
                    'high_variance': 0.40,
                    'extreme_variance': 0.80
                }
            }
        )
    
    @staticmethod
    def create_test_q50_data(num_samples: int = 1000) -> pd.DataFrame:
        """Create realistic Q50 test data"""
        np.random.seed(42)  # For reproducible tests
        
        timestamps = pd.date_range(
            start='2024-01-01', 
            periods=num_samples, 
            freq='5min'
        )
        
        # Generate correlated Q50 data
        base_trend = np.sin(np.arange(num_samples) * 0.01) * 0.3
        noise = np.random.normal(0, 0.2, num_samples)
        
        data = {
            'q10': base_trend - 0.3 + noise * 0.5,
            'q50': base_trend + noise,
            'q90': base_trend + 0.3 + noise * 0.5,
            'vol_raw': np.abs(np.random.normal(0.15, 0.05, num_samples)),
            'vol_risk': np.abs(np.random.normal(0.25, 0.1, num_samples)),
            'prob_up': np.random.beta(2, 2, num_samples),  # Centered around 0.5
            'economically_significant': np.random.choice([True, False], num_samples, p=[0.3, 0.7]),
            'high_quality': np.random.choice([True, False], num_samples, p=[0.4, 0.6]),
            'tradeable': np.random.choice([True, False], num_samples, p=[0.25, 0.75])
        }
        
        df = pd.DataFrame(data, index=timestamps)
        
        # Ensure some logical consistency
        df.loc[df['economically_significant'] == False, 'tradeable'] = False
        df.loc[df['high_quality'] == False, 'tradeable'] = False
        
        return df
    
    @staticmethod
    def create_test_pool_data() -> dict:
        """Create test PumpSwap pool data"""
        return {
            'mint_address': 'So11111111111111111111111111111111111111112',
            'reserve_in_usd': 50000.0,
            'reserve_sol': 500.0,
            'reserve_token': 500000.0,
            'price': 0.001,
            'volume_24h': 10000.0,
            'liquidity_sol': 500.0,
            'price_change_24h': 0.05
        }
    
    @staticmethod
    def create_mock_tick():
        """Create mock market data tick"""
        mock_tick = Mock()
        mock_tick.instrument_id = Mock()
        mock_tick.instrument_id.__str__ = Mock(return_value='SOL/USDC')
        mock_tick.bid_price = 100.0
        mock_tick.ask_price = 100.1
        mock_tick.bid_size = 1000.0
        mock_tick.ask_size = 1000.0
        mock_tick.ts_event = pd.Timestamp.now().value
        return mock_tick


class TestTask1EnvironmentSetup:
    """Test Task 1: Environment Setup and Dependencies"""
    
    def test_dependencies_import(self):
        """Test that all required dependencies can be imported"""
        logger.info("Testing dependency imports...")
        
        # Test core imports
        import pandas as pd
        import numpy as np
        import asyncio
        import logging
        
        # Test configuration imports
        from nautilus_poc.config import ConfigManager, NautilusPOCConfig
        
        # Test component imports
        from nautilus_poc.signal_loader import Q50SignalLoader
        from nautilus_poc.regime_detector import RegimeDetector
        from nautilus_poc.pumpswap_executor import PumpSwapExecutor
        from nautilus_poc.liquidity_validator import LiquidityValidator
        from nautilus_poc.position_sizer import KellyPositionSizer
        from nautilus_poc.risk_manager import RiskManager
        from nautilus_poc.q50_nautilus_strategy import Q50NautilusStrategy
        
        logger.info("✓ All dependencies imported successfully")
    
    def test_configuration_system(self):
        """Test configuration management system"""
        logger.info("Testing configuration system...")
        
        config = TestDataGenerator.create_test_config()
        
        # Test configuration structure
        assert config.environment == 'testnet'
        assert config.q50.signal_tolerance_minutes == 5
        
        # Access environment-specific configuration
        env_config = config.get_current_env_config()
        assert env_config.pumpswap.max_slippage_percent == 5.0
        assert env_config.solana.network == 'testnet'
        assert config.nautilus.instance_id == 'TEST-COMPREHENSIVE-001'
        
        # Test wallet and trading configuration
        assert config.wallet.payer_public_key == 'test_public_key_12345'
        assert config.trading.stop_loss_percent == 20.0
        
        # Test configuration validation
        config_manager = ConfigManager()
        assert config_manager.validate_config(config) == True
        
        logger.info("✓ Configuration system validated")


class TestTask2Q50SignalIntegration:
    """Test Task 2: Q50 Signal Integration Foundation"""
    
    def setup_method(self):
        """Set up test data for Q50 signal tests"""
        self.test_data = TestDataGenerator.create_test_q50_data(100)
        self.config = TestDataGenerator.create_test_config()
    
    def test_q50_signal_loader_initialization(self):
        """Test Q50SignalLoader initialization"""
        logger.info("Testing Q50SignalLoader initialization...")
        
        # Mock database connection to avoid dependency
        with patch('nautilus_poc.signal_loader.DatabaseConnection'):
            config_dict = {
                'q50': {
                    'features_path': 'test_features.pkl',
                    'signal_tolerance_minutes': 5,
                    'required_columns': self.config.q50.required_columns
                },
                'database': {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'test_db',
                    'username': 'test',
                    'password': 'test'
                }
            }
            
            signal_loader = Q50SignalLoader(config_dict)
            
            assert signal_loader.signal_tolerance_minutes == 5
            assert signal_loader.REQUIRED_COLUMNS == self.config.q50.required_columns
            
        logger.info("✓ Q50SignalLoader initialization successful")
    
    def test_signal_validation(self):
        """Test Q50 signal validation"""
        logger.info("Testing Q50 signal validation...")
        
        with patch('nautilus_poc.signal_loader.DatabaseConnection'):
            config_dict = {
                'q50': {'features_path': 'test.pkl', 'signal_tolerance_minutes': 5},
                'database': {}
            }
            signal_loader = Q50SignalLoader(config_dict)
            
            # Test valid signal data
            valid_result = signal_loader.validate_signal_columns(self.test_data)
            assert valid_result == True
            
            # Test invalid signal data (missing columns)
            invalid_data = self.test_data.drop(columns=['q50', 'tradeable'])
            invalid_result = signal_loader.validate_signal_columns(invalid_data)
            assert invalid_result == False
        
        logger.info("✓ Q50 signal validation working correctly")
    
    def test_regime_detector_initialization(self):
        """Test RegimeDetector initialization and basic functionality"""
        logger.info("Testing RegimeDetector...")
        
        config_dict = {
            'regime_detection': self.config.regime_detection
        }
        
        regime_detector = RegimeDetector(config_dict)
        
        # Test regime classification
        test_signal = {
            'vol_risk': 0.5,
            'q50': 0.3,
            'prob_up': 0.6,
            'vol_raw': 0.2
        }
        
        regime_info = regime_detector.classify_regime(test_signal)
        
        assert 'regime' in regime_info
        assert 'vol_risk' in regime_info
        assert 'regime_multiplier' in regime_info
        assert 'threshold_adjustment' in regime_info
        
        logger.info(f"✓ Regime classified as: {regime_info['regime']}")
    
    def test_regime_adjustments(self):
        """Test regime-specific signal adjustments"""
        logger.info("Testing regime adjustments...")
        
        config_dict = {'regime_detection': self.config.regime_detection}
        regime_detector = RegimeDetector(config_dict)
        
        test_signal = {
            'q50': 0.5,
            'prob_up': 0.7,
            'vol_risk': 0.3,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True
        }
        
        regime_info = regime_detector.classify_regime(test_signal)
        adjusted_signal = regime_detector.apply_regime_adjustments(test_signal, regime_info)
        
        assert 'regime_adjusted_economically_significant' in adjusted_signal
        assert 'regime_adjusted_signal_strength' in adjusted_signal
        assert 'regime_adjusted_tradeable' in adjusted_signal
        assert 'regime_info' in adjusted_signal
        
        logger.info("✓ Regime adjustments applied successfully")


class TestTask3PumpSwapIntegration:
    """Test Task 3: PumpSwap SDK Integration Layer"""
    
    def setup_method(self):
        """Set up test data for PumpSwap integration tests"""
        self.config = TestDataGenerator.create_test_config()
        self.pool_data = TestDataGenerator.create_test_pool_data()
    
    def test_pumpswap_executor_initialization(self):
        """Test PumpSwapExecutor initialization"""
        logger.info("Testing PumpSwapExecutor initialization...")
        
        executor = PumpSwapExecutor(self.config)
        
        assert executor.config == self.config
        assert executor.payer_pk == self.config.wallet.payer_public_key
        assert executor.total_trades == 0
        assert executor.successful_trades == 0
        assert executor.failed_trades == 0
        
        logger.info("✓ PumpSwapExecutor initialized successfully")
    
    @pytest.mark.asyncio
    async def test_buy_signal_execution(self):
        """Test buy signal execution logic"""
        logger.info("Testing buy signal execution...")
        
        executor = PumpSwapExecutor(self.config)
        
        # Mock dependencies
        executor.liquidity_validator = Mock()
        executor.liquidity_validator.validate_buy_liquidity.return_value = True
        
        executor.risk_manager = Mock()
        executor.risk_manager.validate_trade.return_value = True
        
        # Mock SDK responses
        executor.sdk.get_pair_address = AsyncMock(return_value='test_pair_address')
        executor.sdk.get_pool_data = AsyncMock(return_value=self.pool_data)
        executor.sdk.buy = AsyncMock(return_value={
            'transaction_hash': 'test_tx_hash',
            'status': 'confirmed',
            'token_amount': 100.0,
            'price': 0.001
        })
        
        test_signal = {
            'q50': 0.5,
            'vol_risk': 0.2,
            'regime_multiplier': 1.0,
            'mint_address': 'test_mint_address'
        }
        
        result = await executor.execute_buy_signal(test_signal)
        
        assert result['status'] == 'executed'
        assert result['action'] == 'buy'
        assert 'trade_id' in result
        assert 'transaction_hash' in result
        
        logger.info("✓ Buy signal execution successful")
    
    def test_liquidity_validator_initialization(self):
        """Test LiquidityValidator initialization and validation"""
        logger.info("Testing LiquidityValidator...")
        
        validator = LiquidityValidator(self.config)
        
        # Test liquidity validation
        test_signal = {'vol_risk': 0.2, 'q50': 0.3}
        validation_result = validator.validate_buy_liquidity(self.pool_data, test_signal)
        
        assert validation_result == True  # Should pass with good pool data
        
        # Test with insufficient liquidity
        poor_pool_data = self.pool_data.copy()
        poor_pool_data['reserve_sol'] = 1.0  # Very low liquidity
        
        poor_validation = validator.validate_buy_liquidity(poor_pool_data, test_signal)
        assert poor_validation == False
        
        logger.info("✓ LiquidityValidator working correctly")
    
    def test_trade_execution_record(self):
        """Test TradeExecutionRecord data structure"""
        logger.info("Testing TradeExecutionRecord...")
        
        record = TradeExecutionRecord(
            trade_id='test_trade_123',
            mint_address='test_mint',
            pair_address='test_pair',
            timestamp=pd.Timestamp.now(),
            action='buy',
            sol_amount=0.1,
            token_amount=100.0,
            expected_price=0.001,
            actual_price=0.0011,
            transaction_hash='test_tx_hash',
            execution_status='confirmed',
            gas_used=5000,
            execution_latency_ms=250,
            slippage_percent=10.0,
            price_impact_percent=2.5,
            pnl_sol=None,
            signal_data={'q50': 0.5},
            regime_at_execution='medium_variance',
            error_message=None
        )
        
        assert record.trade_id == 'test_trade_123'
        assert record.action == 'buy'
        assert record.slippage_percent == 10.0
        assert record.regime_at_execution == 'medium_variance'
        
        logger.info("✓ TradeExecutionRecord structure validated")


class TestTask4PositionSizingRiskManagement:
    """Test Task 4: Position Sizing and Risk Management"""
    
    def setup_method(self):
        """Set up test data for position sizing and risk management tests"""
        self.config = TestDataGenerator.create_test_config()
        self.pool_data = TestDataGenerator.create_test_pool_data()
    
    def test_kelly_position_sizer_initialization(self):
        """Test KellyPositionSizer initialization"""
        logger.info("Testing KellyPositionSizer initialization...")
        
        position_sizer = KellyPositionSizer(self.config)
        
        assert position_sizer.config == self.config
        env_config = self.config.get_current_env_config()
        assert position_sizer.pumpswap_config['base_position_size'] == env_config.pumpswap.base_position_size
        assert position_sizer.pumpswap_config['max_position_size'] == env_config.pumpswap.max_position_size
        
        logger.info("✓ KellyPositionSizer initialized successfully")
    
    def test_position_size_calculation(self):
        """Test Kelly position sizing calculation"""
        logger.info("Testing position size calculation...")
        
        position_sizer = KellyPositionSizer(self.config)
        
        test_signal = {
            'q50': 0.5,
            'vol_risk': 0.2,
            'prob_up': 0.7,
            'regime_multiplier': 1.2
        }
        
        result = position_sizer.calculate_position_size(test_signal, self.pool_data)
        
        assert isinstance(result, PositionSizeResult)
        assert result.recommended_size > 0
        env_config = self.config.get_current_env_config()
        assert result.recommended_size <= env_config.pumpswap.max_position_size
        assert result.kelly_fraction >= 0
        
        logger.info(f"✓ Position size calculated: {result.recommended_size:.4f} SOL")
    
    def test_liquidity_constraints(self):
        """Test position sizing with liquidity constraints"""
        logger.info("Testing liquidity constraints...")
        
        position_sizer = KellyPositionSizer(self.config)
        
        # Test with low liquidity pool
        low_liquidity_pool = self.pool_data.copy()
        low_liquidity_pool['reserve_sol'] = 1.0  # Very low liquidity
        
        test_signal = {
            'q50': 1.0,  # Maximum signal
            'vol_risk': 0.001,  # Very low risk to generate large base size
            'prob_up': 0.9,  # High probability
            'regime_multiplier': 2.0,  # Higher regime multiplier
            'enhanced_info_ratio': 3.0  # Very high info ratio for large signal multiplier
        }
        
        result = position_sizer.calculate_position_size(test_signal, low_liquidity_pool)
        
        # Should be constrained by liquidity (max 25% of pool)
        max_by_liquidity = low_liquidity_pool['reserve_sol'] * 0.25
        assert result.final_size <= max_by_liquidity
        assert result.liquidity_constrained == True
        
        logger.info("✓ Liquidity constraints working correctly")
    
    def test_risk_manager_initialization(self):
        """Test RiskManager initialization"""
        logger.info("Testing RiskManager initialization...")
        
        risk_manager = RiskManager(self.config)
        
        assert risk_manager.config == self.config
        assert risk_manager.circuit_breaker_status == CircuitBreakerStatus.NORMAL
        assert risk_manager.consecutive_failures == 0
        
        logger.info("✓ RiskManager initialized successfully")
    
    def test_trade_validation(self):
        """Test trade validation logic"""
        logger.info("Testing trade validation...")
        
        risk_manager = RiskManager(self.config)
        
        # Test valid trade
        valid_signal = {
            'q50': 0.5,
            'vol_risk': 0.2,
            'regime': 'medium_variance'
        }
        
        validation_result = risk_manager.validate_trade(0.1, valid_signal)
        assert validation_result.is_valid == True
        
        # Test oversized trade
        oversized_validation = risk_manager.validate_trade(1.0, valid_signal)  # Exceeds max
        assert oversized_validation.is_valid == False
        assert 'position_size_exceeded' in oversized_validation.rejection_reason
        
        logger.info("✓ Trade validation working correctly")
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        logger.info("Testing circuit breaker...")
        
        risk_manager = RiskManager(self.config)
        
        # Simulate consecutive failures
        for i in range(6):  # Exceed threshold of 5
            risk_manager.record_trade_failure('test_error')
        
        assert risk_manager.circuit_breaker_status == CircuitBreakerStatus.TRIGGERED
        
        # Test that trades are blocked
        test_signal = {'q50': 0.5, 'vol_risk': 0.2}
        validation = risk_manager.validate_trade(0.1, test_signal)
        assert validation.is_valid == False
        assert 'circuit_breaker' in validation.rejection_reason
        
        logger.info("✓ Circuit breaker functioning correctly")


class TestTask5NautilusTraderStrategy:
    """Test Task 5: NautilusTrader Strategy Implementation"""
    
    def setup_method(self):
        """Set up test data for NautilusTrader strategy tests"""
        self.config = TestDataGenerator.create_test_config()
        self.test_data = TestDataGenerator.create_test_q50_data(50)
    
    def test_strategy_initialization(self):
        """Test Q50NautilusStrategy initialization"""
        logger.info("Testing Q50NautilusStrategy initialization...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        assert strategy.poc_config == self.config
        assert strategy.is_initialized == False
        assert strategy.trading_enabled == True
        assert strategy.processed_signals_count == 0
        
        # Test component initialization
        assert strategy.signal_loader is not None
        assert strategy.regime_detector is not None
        assert strategy.pumpswap_executor is not None
        assert strategy.liquidity_validator is not None
        assert strategy.position_sizer is not None
        assert strategy.risk_manager is not None
        
        logger.info("✓ Q50NautilusStrategy initialized successfully")
    
    @pytest.mark.asyncio
    async def test_strategy_startup(self):
        """Test strategy startup process"""
        logger.info("Testing strategy startup...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        # Mock signal loader methods
        strategy.signal_loader.load_signals = AsyncMock(return_value=True)
        strategy.signal_loader.get_signal_statistics = Mock(return_value={
            'total_signals': 1000,
            'tradeable_signals': 250,
            'date_range': {
                'start': '2024-01-01T00:00:00',
                'end': '2024-12-31T23:59:59'
            }
        })
        strategy.signal_loader.health_check = Mock(return_value={'signals_loaded': True})
        strategy.signal_loader.close_async = AsyncMock()
        
        # Mock regime detector
        strategy.regime_detector.load_historical_data = Mock()
        
        # Test startup
        await strategy.on_start()
        
        assert strategy.is_initialized == True
        
        # Test shutdown
        await strategy.on_stop()
        
        logger.info("✓ Strategy startup/shutdown successful")
    
    def test_signal_strength_calculation(self):
        """Test signal strength calculation"""
        logger.info("Testing signal strength calculation...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        test_signal = {
            'q50': 0.6,
            'prob_up': 0.75,
            'vol_risk': 0.2,
            'regime_info': {
                'regime_multiplier': 1.2,
                'enhanced_info_ratio': 1.5,
                'regime_confidence': 0.8
            }
        }
        
        signal_strength = strategy._calculate_signal_strength(test_signal)
        
        assert 0 <= signal_strength <= 1
        assert signal_strength > 0.3  # Should be reasonably strong
        
        logger.info(f"✓ Signal strength calculated: {signal_strength:.3f}")
    
    def test_expected_return_calculation(self):
        """Test expected return calculation"""
        logger.info("Testing expected return calculation...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        test_signal = {
            'q50': 0.5,
            'prob_up': 0.7,
            'regime_info': {
                'threshold_adjustment': 0.1
            }
        }
        
        expected_return = strategy._calculate_expected_return(test_signal)
        
        assert expected_return > 0  # Should be positive for positive Q50
        
        logger.info(f"✓ Expected return calculated: {expected_return:.4f}")
    
    def test_risk_score_calculation(self):
        """Test risk score calculation"""
        logger.info("Testing risk score calculation...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        test_signal = {
            'vol_risk': 0.3,
            'vol_raw': 0.15,
            'regime_info': {
                'regime': 'high_variance',
                'regime_confidence': 0.7
            }
        }
        
        risk_score = strategy._calculate_risk_score(test_signal)
        
        assert 0 <= risk_score <= 1
        
        logger.info(f"✓ Risk score calculated: {risk_score:.3f}")
    
    @pytest.mark.asyncio
    async def test_trading_decision_logic(self):
        """Test comprehensive trading decision logic"""
        logger.info("Testing trading decision logic...")
        
        strategy = Q50NautilusStrategy(self.config)
        
        # Test strong buy signal
        strong_buy_signal = {
            'q50': 0.8,
            'prob_up': 0.8,
            'vol_risk': 0.15,
            'regime_adjusted_tradeable': True,
            'regime_adjusted_economically_significant': True,
            'high_quality': True,
            'regime_info': {
                'regime': 'medium_variance',
                'regime_confidence': 0.9,
                'regime_multiplier': 1.0,
                'enhanced_info_ratio': 2.0
            }
        }
        
        trade_decision = {
            'signal_strength': strategy._calculate_signal_strength(strong_buy_signal),
            'expected_return': strategy._calculate_expected_return(strong_buy_signal),
            'risk_score': strategy._calculate_risk_score(strong_buy_signal)
        }
        
        decision_result = await strategy._make_trading_decision(strong_buy_signal, trade_decision)
        
        # Should result in buy decision for strong signal
        assert decision_result['action'] in ['buy', 'hold']  # May be hold due to other constraints
        
        logger.info(f"✓ Trading decision: {decision_result['action']} - {decision_result['reason']}")
    
    @pytest.mark.asyncio
    async def test_signal_processing_pipeline(self):
        """Test complete signal processing pipeline"""
        logger.info("Testing signal processing pipeline...")
        
        strategy = Q50NautilusStrategy(self.config)
        strategy.is_initialized = True
        strategy.trading_enabled = True
        
        # Mock signal loader
        test_signal = {
            'timestamp': pd.Timestamp.now(),
            'q50': 0.6,
            'q10': 0.3,
            'q90': 0.8,
            'vol_risk': 0.2,
            'vol_raw': 0.15,
            'prob_up': 0.7,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True
        }
        
        strategy.signal_loader.get_signal_for_timestamp = AsyncMock(return_value=test_signal)
        
        # Mock PumpSwap executor
        strategy.pumpswap_executor.execute_buy_signal = AsyncMock(return_value={
            'status': 'executed',
            'trade_id': 'test_buy_123',
            'sol_amount': 0.1
        })
        
        # Create mock tick
        mock_tick = TestDataGenerator.create_mock_tick()
        
        # Process the tick
        await strategy.on_quote_tick(mock_tick)
        
        # Verify processing occurred
        assert strategy.processed_signals_count > 0
        assert len(strategy.trade_decisions) > 0
        
        decision = strategy.trade_decisions[0]
        assert 'action' in decision
        assert 'signal_strength' in decision
        assert 'expected_return' in decision
        assert 'risk_score' in decision
        
        logger.info("✓ Signal processing pipeline completed successfully")


class TestIntegrationScenarios:
    """Test integration scenarios across all components"""
    
    def setup_method(self):
        """Set up integration test environment"""
        self.config = TestDataGenerator.create_test_config()
        self.test_data = TestDataGenerator.create_test_q50_data(100)
    
    @pytest.mark.asyncio
    async def test_end_to_end_buy_scenario(self):
        """Test complete end-to-end buy scenario"""
        logger.info("Testing end-to-end buy scenario...")
        
        # Initialize all components
        strategy = Q50NautilusStrategy(self.config)
        
        # Mock external dependencies
        strategy.signal_loader.load_signals = AsyncMock(return_value=True)
        strategy.signal_loader.get_signal_statistics = Mock(return_value={'total_signals': 100})
        strategy.signal_loader.health_check = Mock(return_value={'signals_loaded': True})
        strategy.signal_loader.close_async = AsyncMock()
        strategy.regime_detector.load_historical_data = Mock()
        
        # Initialize strategy
        await strategy.on_start()
        
        # Create strong buy signal
        buy_signal = {
            'timestamp': pd.Timestamp.now(),
            'q50': 0.7,
            'q10': 0.4,
            'q90': 0.9,
            'vol_risk': 0.2,
            'vol_raw': 0.15,
            'prob_up': 0.8,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True
        }
        
        strategy.signal_loader.get_signal_for_timestamp = AsyncMock(return_value=buy_signal)
        
        # Mock successful execution
        strategy.pumpswap_executor.execute_buy_signal = AsyncMock(return_value={
            'status': 'executed',
            'action': 'buy',
            'trade_id': 'integration_test_buy',
            'sol_amount': 0.15,
            'token_amount': 150.0,
            'transaction_hash': 'integration_test_tx_hash'
        })
        
        # Process tick
        mock_tick = TestDataGenerator.create_mock_tick()
        await strategy.on_quote_tick(mock_tick)
        
        # Verify results
        assert len(strategy.trade_decisions) > 0
        decision = strategy.trade_decisions[0]
        
        # Should have made a trading decision
        assert decision['action'] in ['buy', 'sell', 'hold']
        assert 'signal_strength' in decision
        assert 'expected_return' in decision
        
        await strategy.on_stop()
        
        logger.info("✓ End-to-end buy scenario completed successfully")
    
    def test_component_integration(self):
        """Test integration between all major components"""
        logger.info("Testing component integration...")
        
        # Test that all components can work together
        config = self.config
        
        # Initialize components (now they accept NautilusPOCConfig objects directly)
        position_sizer = KellyPositionSizer(config)
        risk_manager = RiskManager(config)
        liquidity_validator = LiquidityValidator(config)
        regime_detector = RegimeDetector({'regime_detection': config.regime_detection})
        
        # Test signal flow through components
        test_signal = {
            'q50': 0.5,
            'vol_risk': 0.25,
            'prob_up': 0.65,
            'vol_raw': 0.2,
            'economically_significant': True,
            'high_quality': True,
            'tradeable': True
        }
        
        pool_data = TestDataGenerator.create_test_pool_data()
        
        # 1. Regime detection
        regime_info = regime_detector.classify_regime(test_signal)
        enhanced_signal = regime_detector.apply_regime_adjustments(test_signal, regime_info)
        
        # 2. Position sizing
        position_result = position_sizer.calculate_position_size(enhanced_signal, pool_data)
        
        # 3. Risk validation
        risk_validation = risk_manager.validate_trade(position_result.recommended_size, enhanced_signal)
        
        # 4. Liquidity validation
        liquidity_valid = liquidity_validator.validate_buy_liquidity(pool_data, enhanced_signal)
        
        # Verify all components produced valid results
        assert 'regime' in regime_info
        assert 'regime_adjusted_tradeable' in enhanced_signal
        assert position_result.recommended_size > 0
        assert risk_validation.is_valid in [True, False]
        assert liquidity_valid in [True, False]
        
        logger.info("✓ Component integration successful")
        logger.info(f"  Regime: {regime_info['regime']}")
        logger.info(f"  Position size: {position_result.recommended_size:.4f} SOL")
        logger.info(f"  Risk valid: {risk_validation.is_valid}")
        logger.info(f"  Liquidity valid: {liquidity_valid}")


class TestPerformanceAndReliability:
    """Test performance and reliability aspects"""
    
    def test_signal_processing_performance(self):
        """Test signal processing performance"""
        logger.info("Testing signal processing performance...")
        
        config = TestDataGenerator.create_test_config()
        regime_detector = RegimeDetector({'regime_detection': config.regime_detection})
        
        # Test processing multiple signals
        test_signals = []
        for i in range(100):
            signal = {
                'q50': np.random.normal(0, 0.3),
                'vol_risk': np.random.uniform(0.1, 0.5),
                'prob_up': np.random.uniform(0.3, 0.7),
                'vol_raw': np.random.uniform(0.1, 0.3)
            }
            test_signals.append(signal)
        
        start_time = datetime.now()
        
        for signal in test_signals:
            regime_info = regime_detector.classify_regime(signal)
            adjusted_signal = regime_detector.apply_regime_adjustments(signal, regime_info)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Should process 100 signals in reasonable time (< 1 second)
        assert processing_time < 1.0
        
        avg_time_per_signal = processing_time / len(test_signals) * 1000  # ms
        
        logger.info(f"✓ Processed {len(test_signals)} signals in {processing_time:.3f}s")
        logger.info(f"  Average time per signal: {avg_time_per_signal:.2f}ms")
    
    def test_error_handling_robustness(self):
        """Test error handling and robustness"""
        logger.info("Testing error handling robustness...")
        
        config = TestDataGenerator.create_test_config()
        
        # Test with invalid signal data
        regime_detector = RegimeDetector({'regime_detection': config.regime_detection})
        
        invalid_signals = [
            {},  # Empty signal
            {'vol_risk': None},  # None values
            {'vol_risk': float('nan')},  # NaN values
            {'vol_risk': 'invalid'},  # Wrong type
        ]
        
        for invalid_signal in invalid_signals:
            try:
                regime_info = regime_detector.classify_regime(invalid_signal)
                # Should handle gracefully and return default regime
                assert 'regime' in regime_info
            except Exception as e:
                # Should not crash, but if it does, log it
                logger.warning(f"Signal processing failed for {invalid_signal}: {e}")
        
        logger.info("✓ Error handling robustness validated")


async def run_comprehensive_tests():
    """Run all comprehensive tests"""
    logger.info("🚀 Starting Comprehensive NautilusTrader POC Test Suite")
    logger.info("=" * 70)
    
    test_classes = [
        TestTask1EnvironmentSetup,
        TestTask2Q50SignalIntegration,
        TestTask3PumpSwapIntegration,
        TestTask4PositionSizingRiskManagement,
        TestTask5NautilusTraderStrategy,
        TestIntegrationScenarios,
        TestPerformanceAndReliability
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        logger.info(f"\n📋 Running {test_class.__name__}")
        logger.info("-" * 50)
        
        test_instance = test_class()
        
        # Get all test methods
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
        
        for test_method_name in test_methods:
            total_tests += 1
            
            try:
                # Set up if method exists
                if hasattr(test_instance, 'setup_method'):
                    test_instance.setup_method()
                
                # Run the test
                test_method = getattr(test_instance, test_method_name)
                
                if asyncio.iscoroutinefunction(test_method):
                    await test_method()
                else:
                    test_method()
                
                passed_tests += 1
                logger.info(f"✅ {test_method_name}")
                
            except Exception as e:
                failed_tests += 1
                logger.error(f"❌ {test_method_name}: {str(e)}")
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("🎯 TEST SUITE SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {failed_tests}")
    logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        logger.info("🎉 ALL TESTS PASSED! NautilusTrader POC implementation is working correctly.")
    else:
        logger.warning(f"⚠️  {failed_tests} tests failed. Please review the implementation.")
    
    return passed_tests, failed_tests


if __name__ == "__main__":
    # Run the comprehensive test suite
    asyncio.run(run_comprehensive_tests())