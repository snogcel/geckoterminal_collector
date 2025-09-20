(c:\Projects\geckoterminal_collector\.conda) C:\Projects\geckoterminal_collector>python test_nautilus_poc_comprehensive.py
2025-09-20 07:00:23,825 - __main__ - INFO - 🚀 Starting Comprehensive NautilusTrader POC Test Suite
2025-09-20 07:00:23,826 - __main__ - INFO - ======================================================================
2025-09-20 07:00:23,826 - __main__ - INFO - 
📋 Running TestTask1EnvironmentSetup
2025-09-20 07:00:23,826 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,826 - __main__ - INFO - Testing configuration system...
2025-09-20 07:00:23,826 - __main__ - ERROR - ❌ test_configuration_system: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,826 - __main__ - INFO - Testing dependency imports...
2025-09-20 07:00:23,826 - __main__ - INFO - ✓ All dependencies imported successfully
2025-09-20 07:00:23,826 - __main__ - INFO - ✅ test_dependencies_import
2025-09-20 07:00:23,826 - __main__ - INFO -
📋 Running TestTask2Q50SignalIntegration
2025-09-20 07:00:23,826 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,830 - __main__ - INFO - Testing Q50SignalLoader initialization...
2025-09-20 07:00:23,832 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_features.pkl
2025-09-20 07:00:23,832 - __main__ - INFO - ✓ Q50SignalLoader initialization successful
2025-09-20 07:00:23,832 - __main__ - INFO - ✅ test_q50_signal_loader_initialization
2025-09-20 07:00:23,835 - __main__ - INFO - Testing regime adjustments...
2025-09-20 07:00:23,835 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,835 - __main__ - INFO - ✓ Regime adjustments applied successfully
2025-09-20 07:00:23,835 - __main__ - INFO - ✅ test_regime_adjustments
2025-09-20 07:00:23,837 - __main__ - INFO - Testing RegimeDetector...
2025-09-20 07:00:23,837 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,837 - __main__ - INFO - ✓ Regime classified as: medium_variance
2025-09-20 07:00:23,837 - __main__ - INFO - ✅ test_regime_detector_initialization
2025-09-20 07:00:23,838 - __main__ - INFO - Testing Q50 signal validation...
2025-09-20 07:00:23,838 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test.pkl
2025-09-20 07:00:23,838 - nautilus_poc.signal_loader - INFO - All required Q50 columns validated successfully
2025-09-20 07:00:23,848 - nautilus_poc.signal_loader - ERROR - Missing required Q50 columns: ['q50', 'tradeable']
2025-09-20 07:00:23,848 - __main__ - INFO - ✓ Q50 signal validation working correctly
2025-09-20 07:00:23,849 - __main__ - INFO - ✅ test_signal_validation
2025-09-20 07:00:23,849 - __main__ - INFO -
📋 Running TestTask3PumpSwapIntegration
2025-09-20 07:00:23,849 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,849 - __main__ - INFO - Testing buy signal execution...
2025-09-20 07:00:23,849 - __main__ - ERROR - ❌ test_buy_signal_execution: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,849 - __main__ - INFO - Testing LiquidityValidator...
2025-09-20 07:00:23,849 - __main__ - ERROR - ❌ test_liquidity_validator_initialization: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,849 - __main__ - INFO - Testing PumpSwapExecutor initialization...
2025-09-20 07:00:23,849 - __main__ - ERROR - ❌ test_pumpswap_executor_initialization: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,850 - __main__ - INFO - Testing TradeExecutionRecord...
2025-09-20 07:00:23,850 - __main__ - INFO - ✓ TradeExecutionRecord structure validated
2025-09-20 07:00:23,850 - __main__ - INFO - ✅ test_trade_execution_record
2025-09-20 07:00:23,850 - __main__ - INFO -
📋 Running TestTask4PositionSizingRiskManagement
2025-09-20 07:00:23,850 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,850 - __main__ - INFO - Testing circuit breaker...
2025-09-20 07:00:23,850 - __main__ - ERROR - ❌ test_circuit_breaker: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,850 - __main__ - INFO - Testing KellyPositionSizer initialization...
2025-09-20 07:00:23,850 - __main__ - ERROR - ❌ test_kelly_position_sizer_initialization: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,850 - __main__ - INFO - Testing liquidity constraints...
2025-09-20 07:00:23,851 - __main__ - ERROR - ❌ test_liquidity_constraints: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,851 - __main__ - INFO - Testing position size calculation...
2025-09-20 07:00:23,851 - __main__ - ERROR - ❌ test_position_size_calculation: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,851 - __main__ - INFO - Testing RiskManager initialization...
2025-09-20 07:00:23,851 - __main__ - ERROR - ❌ test_risk_manager_initialization: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,851 - __main__ - INFO - Testing trade validation...
2025-09-20 07:00:23,851 - __main__ - ERROR - ❌ test_trade_validation: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,851 - __main__ - INFO -
📋 Running TestTask5NautilusTraderStrategy
2025-09-20 07:00:23,851 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,852 - __main__ - INFO - Testing expected return calculation...
2025-09-20 07:00:23,871 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,871 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,871 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,871 - __main__ - ERROR - ❌ test_expected_return_calculation: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,872 - __main__ - INFO - Testing risk score calculation...
2025-09-20 07:00:23,873 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,873 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,873 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,873 - __main__ - ERROR - ❌ test_risk_score_calculation: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,874 - __main__ - INFO - Testing signal processing pipeline...
2025-09-20 07:00:23,875 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,875 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,875 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,875 - __main__ - ERROR - ❌ test_signal_processing_pipeline: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,876 - __main__ - INFO - Testing signal strength calculation...
2025-09-20 07:00:23,876 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,876 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,876 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,876 - __main__ - ERROR - ❌ test_signal_strength_calculation: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,878 - __main__ - INFO - Testing Q50NautilusStrategy initialization...
2025-09-20 07:00:23,879 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,879 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,879 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,879 - __main__ - ERROR - ❌ test_strategy_initialization: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,880 - __main__ - INFO - Testing strategy startup...
2025-09-20 07:00:23,881 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,881 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,881 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,881 - __main__ - ERROR - ❌ test_strategy_startup: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,883 - __main__ - INFO - Testing trading decision logic...
2025-09-20 07:00:23,884 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,884 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,884 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,884 - __main__ - ERROR - ❌ test_trading_decision_logic: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,884 - __main__ - INFO -
📋 Running TestIntegrationScenarios
2025-09-20 07:00:23,884 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,885 - __main__ - INFO - Testing component integration...
2025-09-20 07:00:23,885 - __main__ - ERROR - ❌ test_component_integration: 'NautilusPOCConfig' object has no attribute 'get'
2025-09-20 07:00:23,886 - __main__ - INFO - Testing end-to-end buy scenario...
2025-09-20 07:00:23,887 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:00:23,887 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:00:23,887 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,887 - __main__ - ERROR - ❌ test_end_to_end_buy_scenario: 'NautilusPOCConfig' object has no attribute 'pumpswap'
2025-09-20 07:00:23,887 - __main__ - INFO -
📋 Running TestPerformanceAndReliability
2025-09-20 07:00:23,887 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:00:23,888 - __main__ - INFO - Testing error handling robustness...
2025-09-20 07:00:23,888 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,888 - nautilus_poc.regime_detector - WARNING - Invalid vol_risk value, defaulting to medium variance regime
2025-09-20 07:00:23,888 - nautilus_poc.regime_detector - WARNING - Invalid vol_risk value, defaulting to medium variance regime
2025-09-20 07:00:23,888 - nautilus_poc.regime_detector - ERROR - Error in regime classification: '<=' not supported between instances of 'str' and 'float'       
2025-09-20 07:00:23,888 - __main__ - INFO - ✓ Error handling robustness validated
2025-09-20 07:00:23,888 - __main__ - INFO - ✅ test_error_handling_robustness
2025-09-20 07:00:23,888 - __main__ - INFO - Testing signal processing performance...
2025-09-20 07:00:23,888 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:00:23,918 - __main__ - INFO - ✓ Processed 100 signals in 0.029s
2025-09-20 07:00:23,918 - __main__ - INFO -   Average time per signal: 0.29ms
2025-09-20 07:00:23,920 - __main__ - INFO - ✅ test_signal_processing_performance
2025-09-20 07:00:23,920 - __main__ - INFO -
======================================================================
2025-09-20 07:00:23,920 - __main__ - INFO - 🎯 TEST SUITE SUMMARY
2025-09-20 07:00:23,920 - __main__ - INFO - ======================================================================
2025-09-20 07:00:23,920 - __main__ - INFO - Total Tests: 27
2025-09-20 07:00:23,920 - __main__ - INFO - Passed: 8
2025-09-20 07:00:23,920 - __main__ - INFO - Failed: 19
2025-09-20 07:00:23,920 - __main__ - INFO - Success Rate: 29.6%
2025-09-20 07:00:23,920 - __main__ - WARNING - ⚠️  19 tests failed. Please review the implementation.

(c:\Projects\geckoterminal_collector\.conda) C:\Projects\geckoterminal_collector>python test_nautilus_poc_comprehensive.py
2025-09-20 07:03:37,932 - __main__ - INFO - 🚀 Starting Comprehensive NautilusTrader POC Test Suite
2025-09-20 07:03:37,932 - __main__ - INFO - ======================================================================
2025-09-20 07:03:37,932 - __main__ - INFO -
📋 Running TestTask1EnvironmentSetup
2025-09-20 07:03:37,932 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:37,932 - __main__ - INFO - Testing configuration system...
2025-09-20 07:03:37,932 - nautilus_poc.config - INFO - No encryption key found - sensitive data will not be encrypted
2025-09-20 07:03:37,932 - nautilus_poc.config - INFO - Set NAUTILUS_ENCRYPTION_KEY environment variable for production use
2025-09-20 07:03:37,946 - nautilus_poc.config - INFO - Configuration loaded from config.yaml
2025-09-20 07:03:37,946 - nautilus_poc.config - WARNING - Configuration validation warnings:
2025-09-20 07:03:37,946 - nautilus_poc.config - WARNING -   WARNING: Q50 features file not found: test_macro_features.pkl
2025-09-20 07:03:37,946 - nautilus_poc.config - WARNING -   WARNING: Wallet public key should be set via environment variable for security
2025-09-20 07:03:37,946 - nautilus_poc.config - WARNING -   WARNING: Private key path should be set via environment variable for security
2025-09-20 07:03:37,946 - nautilus_poc.config - INFO - Configuration validation passed
2025-09-20 07:03:37,946 - nautilus_poc.config - INFO - Configuration loaded with 3 warnings
2025-09-20 07:03:37,946 - __main__ - INFO - ✓ Configuration system validated
2025-09-20 07:03:37,946 - __main__ - INFO - ✅ test_configuration_system
2025-09-20 07:03:37,948 - __main__ - INFO - Testing dependency imports...
2025-09-20 07:03:37,948 - __main__ - INFO - ✓ All dependencies imported successfully
2025-09-20 07:03:37,948 - __main__ - INFO - ✅ test_dependencies_import
2025-09-20 07:03:37,948 - __main__ - INFO -
📋 Running TestTask2Q50SignalIntegration
2025-09-20 07:03:37,948 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:37,950 - __main__ - INFO - Testing Q50SignalLoader initialization...
2025-09-20 07:03:37,951 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_features.pkl
2025-09-20 07:03:37,951 - __main__ - INFO - ✓ Q50SignalLoader initialization successful
2025-09-20 07:03:37,951 - __main__ - INFO - ✅ test_q50_signal_loader_initialization
2025-09-20 07:03:37,952 - __main__ - INFO - Testing regime adjustments...
2025-09-20 07:03:37,952 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:37,953 - __main__ - INFO - ✓ Regime adjustments applied successfully
2025-09-20 07:03:37,953 - __main__ - INFO - ✅ test_regime_adjustments
2025-09-20 07:03:37,954 - __main__ - INFO - Testing RegimeDetector...
2025-09-20 07:03:37,954 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:37,954 - __main__ - INFO - ✓ Regime classified as: medium_variance
2025-09-20 07:03:37,954 - __main__ - INFO - ✅ test_regime_detector_initialization
2025-09-20 07:03:37,956 - __main__ - INFO - Testing Q50 signal validation...
2025-09-20 07:03:37,957 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test.pkl
2025-09-20 07:03:37,957 - nautilus_poc.signal_loader - INFO - All required Q50 columns validated successfully
2025-09-20 07:03:37,958 - nautilus_poc.signal_loader - ERROR - Missing required Q50 columns: ['q50', 'tradeable']
2025-09-20 07:03:37,958 - __main__ - INFO - ✓ Q50 signal validation working correctly
2025-09-20 07:03:37,958 - __main__ - INFO - ✅ test_signal_validation
2025-09-20 07:03:37,958 - __main__ - INFO -
📋 Running TestTask3PumpSwapIntegration
2025-09-20 07:03:37,959 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:37,959 - __main__ - INFO - Testing buy signal execution...
2025-09-20 07:03:37,959 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:37,962 - nautilus_poc.pumpswap_executor - INFO - Executing buy signal buy_627044f1
2025-09-20 07:03:37,963 - nautilus_poc.pumpswap_executor - INFO - Executing buy order: 0.01 SOL for test_mint_address
2025-09-20 07:03:37,963 - nautilus_poc.pumpswap_executor - INFO - Buy order executed successfully: buy_627044f1
2025-09-20 07:03:37,965 - __main__ - INFO - ✓ Buy signal execution successful
2025-09-20 07:03:37,965 - __main__ - INFO - ✅ test_buy_signal_execution
2025-09-20 07:03:37,965 - __main__ - INFO - Testing LiquidityValidator...
2025-09-20 07:03:37,965 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:37,965 - __main__ - INFO - ✓ LiquidityValidator working correctly
2025-09-20 07:03:37,965 - __main__ - INFO - ✅ test_liquidity_validator_initialization
2025-09-20 07:03:37,965 - __main__ - INFO - Testing PumpSwapExecutor initialization...
2025-09-20 07:03:37,966 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:37,966 - __main__ - INFO - ✓ PumpSwapExecutor initialized successfully
2025-09-20 07:03:37,966 - __main__ - INFO - ✅ test_pumpswap_executor_initialization
2025-09-20 07:03:37,966 - __main__ - INFO - Testing TradeExecutionRecord...
2025-09-20 07:03:37,966 - __main__ - INFO - ✓ TradeExecutionRecord structure validated
2025-09-20 07:03:37,966 - __main__ - INFO - ✅ test_trade_execution_record
2025-09-20 07:03:37,966 - __main__ - INFO -
📋 Running TestTask4PositionSizingRiskManagement
2025-09-20 07:03:37,966 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:37,966 - __main__ - INFO - Testing circuit breaker...
2025-09-20 07:03:37,966 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,966 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=1, circuit_breaker=closed
2025-09-20 07:03:37,966 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=2, circuit_breaker=closed
2025-09-20 07:03:37,968 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=3, circuit_breaker=closed
2025-09-20 07:03:37,968 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=4, circuit_breaker=closed
2025-09-20 07:03:37,968 - nautilus_poc.risk_manager - WARNING - Circuit breaker OPENED after 5 failures
2025-09-20 07:03:37,968 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=5, circuit_breaker=open
2025-09-20 07:03:37,968 - nautilus_poc.risk_manager - ERROR - Trade failure recorded: count=6, circuit_breaker=open
2025-09-20 07:03:37,968 - __main__ - INFO - ✓ Circuit breaker functioning correctly
2025-09-20 07:03:37,968 - __main__ - INFO - ✅ test_circuit_breaker
2025-09-20 07:03:37,968 - __main__ - INFO - Testing KellyPositionSizer initialization...
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,969 - __main__ - INFO - ✓ KellyPositionSizer initialized successfully
2025-09-20 07:03:37,969 - __main__ - INFO - ✅ test_kelly_position_sizer_initialization
2025-09-20 07:03:37,969 - __main__ - INFO - Testing liquidity constraints...
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - Position size constrained by liquidity: 0.4000 -> 0.2500 SOL
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - Position size calculated: 0.2500 SOL (base: 0.1000, signal: 2.00x, regime: 2.00x)
2025-09-20 07:03:37,969 - __main__ - INFO - ✓ Liquidity constraints working correctly
2025-09-20 07:03:37,969 - __main__ - INFO - ✅ test_liquidity_constraints
2025-09-20 07:03:37,969 - __main__ - INFO - Testing position size calculation...
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,969 - nautilus_poc.position_sizer - INFO - Position size calculated: 0.0100 SOL (base: 0.0100, signal: 0.50x, regime: 1.20x)
2025-09-20 07:03:37,969 - __main__ - INFO - ✓ Position size calculated: 0.0060 SOL
2025-09-20 07:03:37,970 - __main__ - INFO - ✅ test_position_size_calculation
2025-09-20 07:03:37,970 - __main__ - INFO - Testing RiskManager initialization...
2025-09-20 07:03:37,970 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,970 - __main__ - INFO - ✓ RiskManager initialized successfully
2025-09-20 07:03:37,970 - __main__ - INFO - ✅ test_risk_manager_initialization
2025-09-20 07:03:37,970 - __main__ - INFO - Testing trade validation...
2025-09-20 07:03:37,970 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,970 - __main__ - INFO - ✓ Trade validation working correctly
2025-09-20 07:03:37,970 - __main__ - INFO - ✅ test_trade_validation
2025-09-20 07:03:37,970 - __main__ - INFO -
📋 Running TestTask5NautilusTraderStrategy
2025-09-20 07:03:37,970 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:37,973 - __main__ - INFO - Testing expected return calculation...
2025-09-20 07:03:37,985 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:37,985 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:37,985 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:37,987 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:37,987 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:37,987 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,987 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,987 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:37,987 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:37,987 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:37,987 - __main__ - INFO - ✓ Expected return calculated: 0.3850
2025-09-20 07:03:37,987 - __main__ - INFO - ✅ test_expected_return_calculation
2025-09-20 07:03:37,988 - __main__ - INFO - Testing risk score calculation...
2025-09-20 07:03:37,989 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:37,989 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:37,989 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:37,990 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:37,990 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:37,990 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,990 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,990 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:37,990 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:37,990 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:37,991 - __main__ - INFO - ✓ Risk score calculated: 0.620
2025-09-20 07:03:37,991 - __main__ - INFO - ✅ test_risk_score_calculation
2025-09-20 07:03:37,992 - __main__ - INFO - Testing signal processing pipeline...
2025-09-20 07:03:37,993 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:37,993 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:37,993 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:37,994 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:37,994 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:37,994 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:37,994 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:37,994 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:37,994 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:37,994 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:37,997 - nautilus_poc.q50_nautilus_strategy - INFO - Executing buy signal for SOL/USDC
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO - Buy order executed successfully: test_buy_123
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO - SOL amount: 0.1, Token amount: None
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO - Trade decision: buy for SOL/USDC
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO -   Q50: 0.6000, Signal strength: 0.725
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO -   Expected return: 0.2940, Risk score: 0.565
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO -   Regime: low_variance (confidence: 0.50)
2025-09-20 07:03:37,998 - nautilus_poc.q50_nautilus_strategy - INFO -   Reason: strong_buy_signal_strength_0.725_return_0.2940
2025-09-20 07:03:37,999 - __main__ - INFO - ✓ Signal processing pipeline completed successfully
2025-09-20 07:03:37,999 - __main__ - INFO - ✅ test_signal_processing_pipeline
2025-09-20 07:03:38,000 - __main__ - INFO - Testing signal strength calculation...
2025-09-20 07:03:38,001 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:38,001 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:38,001 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,001 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:38,001 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,001 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,001 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,001 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:38,002 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:38,002 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:38,002 - __main__ - INFO - ✓ Signal strength calculated: 0.806
2025-09-20 07:03:38,002 - __main__ - INFO - ✅ test_signal_strength_calculation
2025-09-20 07:03:38,004 - __main__ - INFO - Testing Q50NautilusStrategy initialization...
2025-09-20 07:03:38,005 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:38,005 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:38,005 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,005 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:38,005 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,005 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,005 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,005 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:38,005 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:38,006 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:38,006 - __main__ - INFO - ✓ Q50NautilusStrategy initialized successfully
2025-09-20 07:03:38,006 - __main__ - INFO - ✅ test_strategy_initialization
2025-09-20 07:03:38,007 - __main__ - INFO - Testing strategy startup...
2025-09-20 07:03:38,008 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:38,008 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:38,008 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,008 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:38,008 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,009 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,009 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,009 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:38,009 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:38,009 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:38,010 - nautilus_poc.q50_nautilus_strategy - INFO - Starting Q50 NautilusTrader Strategy
2025-09-20 07:03:38,010 - nautilus_poc.q50_nautilus_strategy - INFO - Loaded 1000 Q50 signals
2025-09-20 07:03:38,011 - nautilus_poc.q50_nautilus_strategy - INFO - Tradeable signals: 250
2025-09-20 07:03:38,011 - nautilus_poc.q50_nautilus_strategy - INFO - Date range: 2024-01-01T00:00:00 to 2024-12-31T23:59:59
2025-09-20 07:03:38,011 - nautilus_poc.q50_nautilus_strategy - INFO - Q50 NautilusTrader Strategy started successfully
2025-09-20 07:03:38,011 - nautilus_poc.q50_nautilus_strategy - INFO - Stopping Q50 NautilusTrader Strategy
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - === Q50 NautilusTrader Strategy Final Performance ===
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Processed signals: 0
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Errors encountered: 0
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Total trades executed: 0
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Success rate: 0.0%
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Total volume: 0.0000 SOL
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - === End Performance Summary ===
2025-09-20 07:03:38,012 - nautilus_poc.q50_nautilus_strategy - INFO - Q50 NautilusTrader Strategy stopped successfully
2025-09-20 07:03:38,012 - __main__ - INFO - ✓ Strategy startup/shutdown successful
2025-09-20 07:03:38,012 - __main__ - INFO - ✅ test_strategy_startup
2025-09-20 07:03:38,014 - __main__ - INFO - Testing trading decision logic...
2025-09-20 07:03:38,015 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:38,015 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:38,015 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,015 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:38,015 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,015 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,015 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,015 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:38,015 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:38,015 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:38,017 - __main__ - INFO - ✓ Trading decision: buy - strong_buy_signal_strength_0.830_return_0.6400
2025-09-20 07:03:38,017 - __main__ - INFO - ✅ test_trading_decision_logic
2025-09-20 07:03:38,017 - __main__ - INFO -
📋 Running TestIntegrationScenarios
2025-09-20 07:03:38,017 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:38,018 - __main__ - INFO - Testing component integration...
2025-09-20 07:03:38,018 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,018 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,018 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,019 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,019 - nautilus_poc.position_sizer - INFO - Position size calculated: 0.0100 SOL (base: 0.0100, signal: 0.50x, regime: 1.00x)
2025-09-20 07:03:38,019 - __main__ - INFO - ✓ Component integration successful
2025-09-20 07:03:38,019 - __main__ - INFO -   Regime: low_variance
2025-09-20 07:03:38,019 - __main__ - INFO -   Position size: 0.0050 SOL
2025-09-20 07:03:38,019 - __main__ - INFO -   Risk valid: True
2025-09-20 07:03:38,019 - __main__ - INFO -   Liquidity valid: True
2025-09-20 07:03:38,019 - __main__ - INFO - ✅ test_component_integration
2025-09-20 07:03:38,020 - __main__ - INFO - Testing end-to-end buy scenario...
2025-09-20 07:03:38,020 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-20 07:03:38,021 - nautilus_poc.signal_loader - INFO - Q50SignalLoader initialized with features path: test_macro_features.pkl
2025-09-20 07:03:38,021 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,021 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor initialized
2025-09-20 07:03:38,021 - nautilus_poc.liquidity_validator - INFO - LiquidityValidator initialized with min_liquidity=10.0 SOL, max_impact=10.0%
2025-09-20 07:03:38,021 - nautilus_poc.position_sizer - INFO - KellyPositionSizer initialized with config
2025-09-20 07:03:38,021 - nautilus_poc.risk_manager - INFO - RiskManager initialized with circuit breaker functionality
2025-09-20 07:03:38,021 - nautilus_poc.pumpswap_executor - INFO - PumpSwapExecutor dependencies set
2025-09-20 07:03:38,021 - nautilus_poc.q50_nautilus_strategy - INFO - Strategy configuration validated successfully
2025-09-20 07:03:38,021 - nautilus_poc.q50_nautilus_strategy - INFO - Q50NautilusStrategy initialized with instance_id: TEST-COMPREHENSIVE-001
2025-09-20 07:03:38,023 - nautilus_poc.q50_nautilus_strategy - INFO - Starting Q50 NautilusTrader Strategy
2025-09-20 07:03:38,023 - nautilus_poc.q50_nautilus_strategy - INFO - Loaded 100 Q50 signals
2025-09-20 07:03:38,023 - nautilus_poc.q50_nautilus_strategy - INFO - Tradeable signals: 0
2025-09-20 07:03:38,023 - nautilus_poc.q50_nautilus_strategy - INFO - Date range: None to None
2025-09-20 07:03:38,023 - nautilus_poc.q50_nautilus_strategy - INFO - Q50 NautilusTrader Strategy started successfully
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO - Executing buy signal for SOL/USDC
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO - Buy order executed successfully: integration_test_buy
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO - SOL amount: 0.15, Token amount: 150.0
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO - Trade decision: buy for SOL/USDC
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO -   Q50: 0.7000, Signal strength: 0.765
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO -   Expected return: 0.3920, Risk score: 0.565
2025-09-20 07:03:38,025 - nautilus_poc.q50_nautilus_strategy - INFO -   Regime: low_variance (confidence: 0.50)
2025-09-20 07:03:38,026 - nautilus_poc.q50_nautilus_strategy - INFO -   Reason: strong_buy_signal_strength_0.765_return_0.3920
2025-09-20 07:03:38,026 - nautilus_poc.q50_nautilus_strategy - INFO - Stopping Q50 NautilusTrader Strategy
2025-09-20 07:03:38,026 - nautilus_poc.q50_nautilus_strategy - INFO - === Q50 NautilusTrader Strategy Final Performance ===
2025-09-20 07:03:38,026 - nautilus_poc.q50_nautilus_strategy - INFO - Processed signals: 1
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Errors encountered: 0
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Average signal processing time: 2.01ms
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Total trade decisions: 1
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Buy signals: 1
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Sell signals: 0
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Hold signals: 0
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Total trades executed: 0
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Success rate: 0.0%
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Total volume: 0.0000 SOL
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - === End Performance Summary ===
2025-09-20 07:03:38,027 - nautilus_poc.q50_nautilus_strategy - INFO - Q50 NautilusTrader Strategy stopped successfully
2025-09-20 07:03:38,027 - __main__ - INFO - ✓ End-to-end buy scenario completed successfully
2025-09-20 07:03:38,027 - __main__ - INFO - ✅ test_end_to_end_buy_scenario
2025-09-20 07:03:38,029 - __main__ - INFO -
📋 Running TestPerformanceAndReliability
2025-09-20 07:03:38,029 - __main__ - INFO - --------------------------------------------------
2025-09-20 07:03:38,029 - __main__ - INFO - Testing error handling robustness...
2025-09-20 07:03:38,029 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,029 - nautilus_poc.regime_detector - WARNING - Invalid vol_risk value, defaulting to medium variance regime
2025-09-20 07:03:38,029 - nautilus_poc.regime_detector - WARNING - Invalid vol_risk value, defaulting to medium variance regime
2025-09-20 07:03:38,029 - nautilus_poc.regime_detector - ERROR - Error in regime classification: '<=' not supported between instances of 'str' and 'float'       
2025-09-20 07:03:38,029 - __main__ - INFO - ✓ Error handling robustness validated
2025-09-20 07:03:38,029 - __main__ - INFO - ✅ test_error_handling_robustness
2025-09-20 07:03:38,029 - __main__ - INFO - Testing signal processing performance...
2025-09-20 07:03:38,029 - nautilus_poc.regime_detector - INFO - RegimeDetector initialized with percentiles: {'low': 0.3, 'high': 0.7, 'extreme': 0.9}
2025-09-20 07:03:38,059 - __main__ - INFO - ✓ Processed 100 signals in 0.029s
2025-09-20 07:03:38,059 - __main__ - INFO -   Average time per signal: 0.29ms
2025-09-20 07:03:38,059 - __main__ - INFO - ✅ test_signal_processing_performance
2025-09-20 07:03:38,059 - __main__ - INFO -
======================================================================
2025-09-20 07:03:38,059 - __main__ - INFO - 🎯 TEST SUITE SUMMARY
2025-09-20 07:03:38,060 - __main__ - INFO - ======================================================================
2025-09-20 07:03:38,060 - __main__ - INFO - Total Tests: 27
2025-09-20 07:03:38,060 - __main__ - INFO - Passed: 27
2025-09-20 07:03:38,060 - __main__ - INFO - Failed: 0
2025-09-20 07:03:38,060 - __main__ - INFO - Success Rate: 100.0%
2025-09-20 07:03:38,060 - __main__ - INFO - 🎉 ALL TESTS PASSED! NautilusTrader POC implementation is working correctly.