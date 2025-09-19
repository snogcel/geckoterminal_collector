# Requirements Document

## Introduction

This specification defines the requirements for building a 2-week proof of concept (POC) that integrates our Q50-centric quantile trading system with NautilusTrader. The POC will validate the technical feasibility, performance characteristics, and implementation complexity of using NautilusTrader as our primary trading platform before committing to full production implementation.

The POC aims to demonstrate that our existing Q50 system (which achieves a 1.327 Sharpe ratio) can be successfully integrated with NautilusTrader while maintaining performance quality and providing a foundation for future scalability including RD-Agent integration and multi-asset expansion.

## Requirements

### Requirement 1: Q50 Signal Integration

**User Story:** As a quantitative trader, I want to integrate our existing Q50 quantile predictions with NautilusTrader, so that I can execute systematic trades based on our proven signal generation system.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL successfully load our existing Q50 signals from `data3/macro_features.pkl`
2. WHEN Q50 signals are loaded THEN the system SHALL validate that required columns (q10, q50, q90, vol_raw, vol_risk, prob_up, economically_significant, high_quality, tradeable) are present
3. WHEN a new market data tick arrives THEN the system SHALL retrieve the corresponding Q50 signal for that timestamp
4. IF no exact timestamp match exists THEN the system SHALL use the most recent available signal within a 5-minute window
5. WHEN Q50 signals are processed THEN the system SHALL convert quantile predictions to actionable trading decisions using our regime-aware probability conversion logic
6. WHEN signals are processed THEN the system SHALL apply our variance-based regime identification (vol_risk as variance measure) for enhanced risk assessment

### Requirement 2: NautilusTrader Strategy Implementation

**User Story:** As a systematic trader, I want a minimal viable NautilusTrader strategy that can execute Q50-based trades, so that I can validate the platform's suitability for our trading approach.

#### Acceptance Criteria

1. WHEN the strategy initializes THEN it SHALL inherit from NautilusTrader's Strategy base class
2. WHEN market data is received THEN the strategy SHALL process quote ticks and trade ticks appropriately
3. WHEN a Q50 signal indicates tradeable=True AND q50 > 0 THEN the system SHALL execute a market buy order (side=1)
4. WHEN a Q50 signal indicates tradeable=True AND q50 < 0 THEN the system SHALL execute a market sell order (side=0)
5. WHEN a Q50 signal indicates tradeable=False OR economically_significant=False THEN the system SHALL hold position (side=-1)
6. WHEN orders are executed THEN the system SHALL track position changes and log trade executions
7. WHEN processing signals THEN the system SHALL use our regime-aware signal classification with vol_raw deciles for volatility regime detection
8. WHEN determining tradeable status THEN the system SHALL use expected_value > 0.0005 (5 bps transaction cost) as the primary filter

### Requirement 3: Position Sizing and Risk Management

**User Story:** As a risk-conscious trader, I want the POC to implement our Kelly-based position sizing with variance-aware volatility adjustments, so that position sizes reflect signal strength and market conditions.

#### Acceptance Criteria

1. WHEN calculating position size THEN the system SHALL use inverse variance scaling: `base_size = 0.1 / max(vol_risk * 1000, 0.1)`
2. WHEN Q50 signal strength is available THEN the system SHALL use signal_strength = `abs_q50 * min(enhanced_info_ratio / effective_info_ratio_threshold, 2.0)`
3. WHEN vol_risk (variance measure) is available THEN the system SHALL apply variance regime adjustments using vol_risk.quantile(0.30), vol_risk.quantile(0.70), and vol_risk.quantile(0.90):
   - Low variance (≤30th percentile): -30% threshold adjustment
   - High variance (70th-90th percentile): +40% threshold adjustment  
   - Extreme variance (>90th percentile): +80% threshold adjustment
4. WHEN vol_raw deciles are available THEN the system SHALL apply Kelly-based risk adjustments (decile ≥9: 0.6x, decile ≥8: 0.7x, decile ≥6: 0.85x, decile ≤1: 1.1x)
5. WHEN final position size is calculated THEN the system SHALL clip position_size_suggestion to range [0.01, 0.5] (1%-50% of capital)
6. IF position size calculation fails THEN the system SHALL default to 10% base position size
7. WHEN risk limits are exceeded THEN the system SHALL reject the trade and log the rejection reason
8. WHEN using enhanced_info_ratio THEN the system SHALL incorporate both market variance (vol_risk) and prediction variance ((spread/2)²) for superior risk assessment

### Requirement 4: Paper Trading Validation

**User Story:** As a cautious trader, I want to validate the POC using paper trading before risking real capital, so that I can verify system behavior without financial exposure.

#### Acceptance Criteria

1. WHEN the system is configured THEN it SHALL connect to Binance testnet for paper trading using 60min timeframe data (matching training pipeline frequency)
2. WHEN paper trades are executed THEN the system SHALL simulate realistic order fills and slippage appropriate for 60min trading intervals
3. WHEN trades are completed THEN the system SHALL track simulated P&L and performance metrics with target 1.327+ Sharpe ratio
4. WHEN the POC runs for 24+ hours THEN it SHALL maintain stable operation without crashes while processing hourly signal updates
5. WHEN performance is measured THEN the system SHALL log trade execution latency (target < 30 seconds from hourly signal generation to order execution)
6. WHEN using QLib data framework THEN the system SHALL be compatible with potential qlib-server integration for live data feeds
7. WHEN validating signals THEN the system SHALL use the same data pipeline: crypto_loader (60min) + gdelt_loader (daily) via nested_data_loader

### Requirement 5: Performance Monitoring and Logging

**User Story:** As a system operator, I want comprehensive logging and performance monitoring, so that I can evaluate the POC's effectiveness and identify potential issues.

#### Acceptance Criteria

1. WHEN the system processes signals THEN it SHALL log signal strength (abs_q50), regime classification (variance_regime_low/high/extreme), action taken (side: -1/0/1), and execution details
2. WHEN orders are submitted THEN it SHALL log order details including size, price, timestamp, and regime context (vol_risk percentile, momentum_regime_trending/ranging)
3. WHEN orders are filled THEN it SHALL log fill details, update position tracking, and record regime-specific performance metrics
4. WHEN errors occur THEN the system SHALL log error details with sufficient context for debugging including signal validation failures
5. WHEN the POC completes THEN it SHALL generate a summary report including:
   - Total trades executed by regime (low/high/extreme variance)
   - Enhanced vs traditional info ratio comparison (actual implementation uses both)
   - Expected value vs traditional threshold performance comparison
   - System stability indicators and regime transition frequency
6. WHEN regime transitions occur THEN the system SHALL log regime changes using actual thresholds (30th/70th/90th percentiles) and their impact on signal generation and position sizing

### Requirement 6: Configuration Management

**User Story:** As a system administrator, I want flexible configuration management, so that I can easily adjust parameters without code changes during POC testing.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load configuration from a dedicated config file
2. WHEN configuration includes trading parameters THEN it SHALL support:
   - `realistic_transaction_cost`: 0.0005 (5 bps, actual implementation value)
   - `base_info_ratio`: 1.5 (actual implementation default)
   - `max_position_size`: 0.5 (50% of capital, actual implementation limit)
   - `timeframe`: "60min" (matching training pipeline frequency)
3. WHEN configuration includes instrument settings THEN it SHALL support configurable trading pairs (default: BTCUSDT.BINANCE)
4. WHEN configuration includes data settings THEN it SHALL support:
   - QLib data provider configuration with provider_uri path
   - Nested data loader configuration (crypto_loader + gdelt_loader)
   - Optional qlib-server integration parameters
5. WHEN configuration is invalid THEN the system SHALL fail gracefully with clear error messages
6. WHEN configuration changes are made THEN they SHALL take effect on next system restart
7. WHEN timeframe is configured THEN it SHALL support 60min intervals with regime analysis using:
   - 24-hour rolling windows for momentum calculation
   - 168-hour (7-day) rolling windows for longer-term regime detection

### Requirement 7: Variance-Based Signal Generation (Implementation-Aligned)

**User Story:** As a quantitative trader, I want the POC to implement our exact variance-based signal generation logic, so that the NautilusTrader integration maintains the same performance characteristics as our training pipeline.

#### Acceptance Criteria

1. WHEN calculating economic significance THEN the system SHALL use expected_value approach: `(prob_up * potential_gain) - ((1 - prob_up) * potential_loss) > 0.0005`
2. WHEN determining signal quality THEN the system SHALL use enhanced_info_ratio: `abs_q50 / sqrt(market_variance + prediction_variance)` where:
   - `market_variance = vol_risk` (6-day variance from crypto_loader)
   - `prediction_variance = (spread / 2)²` where `spread = q90 - q10`
3. WHEN applying regime adjustments THEN the system SHALL use variance percentile thresholds:
   - `variance_regime_low`: vol_risk ≤ 30th percentile → -30% threshold adjustment
   - `variance_regime_high`: vol_risk 70th-90th percentile → +40% threshold adjustment
   - `variance_regime_extreme`: vol_risk > 90th percentile → +80% threshold adjustment
4. WHEN calculating adaptive thresholds THEN the system SHALL use: `realistic_transaction_cost * regime_multipliers * variance_multiplier` where:
   - `realistic_transaction_cost = 0.0005` (5 bps)
   - `regime_multipliers` clipped to [0.3, 3.0] range
   - `variance_multiplier = 1.0 + vol_risk * 500`
5. WHEN determining tradeable status THEN the system SHALL use: `economically_significant = expected_value > realistic_transaction_cost`
6. WHEN generating trading signals THEN the system SHALL use pure Q50 logic:
   - `side = 1` (LONG) when `tradeable=True AND q50 > 0`
   - `side = 0` (SHORT) when `tradeable=True AND q50 < 0`  
   - `side = -1` (HOLD) when `tradeable=False`

### Requirement 8: Integration Architecture Validation

**User Story:** As a software architect, I want to validate that our Q50 system components integrate cleanly with NautilusTrader's architecture, so that I can assess long-term maintainability and scalability.

#### Acceptance Criteria

1. WHEN integrating Q50 components THEN the system SHALL maintain clear separation between our logic and NautilusTrader framework
2. WHEN processing market data THEN the system SHALL demonstrate efficient data flow from NautilusTrader to our Q50 components
3. WHEN executing trades THEN the system SHALL properly utilize NautilusTrader's order management and execution engines
4. WHEN handling errors THEN the system SHALL integrate with NautilusTrader's error handling and logging systems
5. WHEN the POC is complete THEN the architecture SHALL support future extensions for multi-asset trading and RD-Agent integration

### Requirement 8: Comparative Analysis Framework

**User Story:** As a decision maker, I want objective metrics to compare NautilusTrader against our Hummingbot alternative, so that I can make a data-driven platform selection.

#### Acceptance Criteria

1. WHEN the POC runs THEN it SHALL collect metrics on implementation complexity (lines of code, integration points, setup difficulty)
2. WHEN trades are executed THEN it SHALL measure performance metrics (signal latency, execution accuracy, system stability)
3. WHEN evaluating future potential THEN it SHALL assess scalability indicators (multi-asset support, advanced features, professional adoption)
4. WHEN the POC completes THEN it SHALL generate a comprehensive comparison framework for decision making
5. WHEN metrics are collected THEN they SHALL be formatted for easy comparison with equivalent Hummingbot POC metrics

### Requirement 9: Error Handling and Recovery

**User Story:** As a system operator, I want robust error handling and recovery mechanisms, so that the POC can handle unexpected conditions gracefully during testing.

#### Acceptance Criteria

1. WHEN Q50 signal loading fails THEN the system SHALL log the error and attempt to continue with cached signals
2. WHEN market data connection is lost THEN the system SHALL attempt reconnection with exponential backoff
3. WHEN order submission fails THEN the system SHALL log the failure and continue processing subsequent signals
4. WHEN invalid signals are encountered THEN the system SHALL skip the signal and log the validation failure
5. WHEN system resources are constrained THEN the system SHALL degrade gracefully rather than crash

### Requirement 10: Documentation and Knowledge Transfer

**User Story:** As a team member, I want clear documentation of the POC implementation and findings, so that the team can understand the integration approach and make informed decisions.

#### Acceptance Criteria

1. WHEN the POC is implemented THEN it SHALL include comprehensive code documentation with clear explanations
2. WHEN the POC testing is complete THEN it SHALL produce a detailed findings report with performance analysis
3. WHEN integration challenges are encountered THEN they SHALL be documented with proposed solutions
4. WHEN the POC concludes THEN it SHALL provide clear recommendations for full implementation approach
5. WHEN knowledge transfer occurs THEN the documentation SHALL enable other team members to understand and extend the implementation