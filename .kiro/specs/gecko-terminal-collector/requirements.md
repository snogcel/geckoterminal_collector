# Requirements Document

## Introduction

This document outlines the requirements for a Python-based GeckoTerminal data collection system that monitors decentralized exchange (DEX) trading data on the Solana network. The system will collect real-time and historical data for tokens, pools, and trades from specific DEXes (Heaven and PumpSwap) using the GeckoTerminal API and geckoterminal-py SDK. The collected data will be stored with integrity controls and made available for analysis and predictive modeling using QLib.

## Requirements

### Requirement 1: DEX Monitoring Infrastructure

**User Story:** As a Solana DEX trader, I want the system to monitor specific DEXes (Heaven and PumpSwap) with extensible architecture, so that I can track trading opportunities and expand to new DEXes in the future.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL connect to GeckoTerminal API using the geckoterminal-py SDK
2. WHEN querying available DEXes THEN the system SHALL retrieve and validate that "heaven" and "pumpswap" are available on Solana network
3. WHEN adding new DEX targets THEN the system SHALL support configuration-based extensibility without code changes
4. IF a DEX becomes unavailable THEN the system SHALL log the error and continue monitoring other configured DEXes

### Requirement 2: Top Pools Monitoring

**User Story:** As a trader, I want to monitor the top pools by network and DEX on a configurable schedule, so that I can identify high-volume trading opportunities.

#### Acceptance Criteria

1. WHEN the monitoring interval triggers THEN the system SHALL fetch top pools for each configured DEX using get_top_pools_by_network_dex
2. WHEN configuring monitoring intervals THEN the system SHALL support hourly intervals as default with configurable alternatives
3. WHEN pool data is retrieved THEN the system SHALL store pool information including volume, liquidity, and token pair details
4. IF API rate limits are encountered THEN the system SHALL implement exponential backoff and retry logic

### Requirement 3: Watchlist-Based Token Monitoring

**User Story:** As an analyst, I want to monitor specific tokens from a watchlist CSV file, so that I can collect detailed information about tokens of interest.

#### Acceptance Criteria

1. WHEN a watchlist CSV file is updated THEN the system SHALL detect changes and process new tokens within the configured interval
2. WHEN processing watchlist tokens THEN the system SHALL retrieve pool data using get_multiple_pools_by_network for efficiency
3. WHEN individual token details are needed THEN the system SHALL use get_pool_by_network_address and get_specific_token_on_network
4. WHEN handling address types THEN the system SHALL correctly distinguish between pool addresses ("id") and network addresses ("base_token_id")
5. IF a token is removed from the watchlist THEN the system SHALL stop monitoring but retain historical data

### Requirement 4: OHLCV Data Collection

**User Story:** As a data analyst, I want to collect OHLCV (Open, High, Low, Close, Volume) data for watchlist tokens with configurable intervals, so that I can perform technical analysis and build predictive models.

#### Acceptance Criteria

1. WHEN collecting OHLCV data THEN the system SHALL support all SDK timeframes: ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
2. WHEN storing OHLCV data THEN the system SHALL prevent duplicate entries using composite keys of pool_address, timeframe, and timestamp
3. WHEN data collection runs THEN the system SHALL verify data continuity and flag gaps between intervals
4. IF missing data is detected THEN the system SHALL attempt to backfill gaps using historical data endpoints
5. WHEN timeframe configuration changes THEN the system SHALL validate the new timeframe against supported options

### Requirement 5: Trade Data Collection

**User Story:** As a trader, I want to collect trade data for watchlist tokens with volume filtering, so that I can analyze significant trading activity and market movements.

#### Acceptance Criteria

1. WHEN collecting trade data THEN the system SHALL retrieve up to 300 trades from the last 24 hours per pool
2. WHEN filtering trades THEN the system SHALL support configurable minimum USD volume thresholds (default: $100)
3. WHEN storing trade data THEN the system SHALL prevent duplicate entries using trade ID or composite timestamp/pool/amount keys
4. WHEN trade collection runs THEN the system SHALL verify data continuity within the 24-hour window
5. IF API limits are reached THEN the system SHALL prioritize high-volume pools and implement fair rotation

### Requirement 6: Historical OHLCV Data Collection

**User Story:** As a quantitative analyst, I want to collect historical OHLCV data up to 6 months back using direct API calls, so that I can build comprehensive datasets for predictive modeling.

#### Acceptance Criteria

1. WHEN collecting historical data THEN the system SHALL use direct HTTP requests to GeckoTerminal API with proper query parameters
2. WHEN specifying timeframes THEN the system SHALL support day, hour, and minute with appropriate aggregate values
3. WHEN requesting historical data THEN the system SHALL support pagination using before_timestamp and limit parameters
4. WHEN processing responses THEN the system SHALL handle empty intervals based on include_empty_intervals configuration
5. IF historical data is unavailable THEN the system SHALL log the gap and continue with available data
6. WHEN backfilling data THEN the system SHALL respect API rate limits and implement appropriate delays

### Requirement 7: QLib Integration Support

**User Story:** As a quantitative researcher, I want the collected data to be compatible with QLib framework, so that I can leverage existing crypto data collection patterns for predictive modeling.

#### Acceptance Criteria

1. WHEN designing data storage THEN the system SHALL structure data in formats compatible with QLib crypto data collectors
2. WHEN exporting data THEN the system SHALL provide interfaces similar to existing QLib crypto data collection patterns
3. WHEN integrating with QLib THEN the system SHALL support the data formats and schemas expected by QLib models
4. IF QLib requirements change THEN the system SHALL provide configurable export formats to maintain compatibility

### Requirement 8: Configuration Management

**User Story:** As a system administrator, I want all intervals, thresholds, and targets to be configurable, so that I can adjust the system behavior without code changes.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load configuration from a structured configuration file (JSON/YAML)
2. WHEN configuration includes intervals THEN the system SHALL validate and apply monitoring, collection, and processing intervals
3. WHEN configuration includes thresholds THEN the system SHALL apply volume filters, rate limits, and retry parameters
4. WHEN configuration changes THEN the system SHALL support hot-reloading without requiring system restart
5. IF configuration is invalid THEN the system SHALL use safe defaults and log configuration errors

### Requirement 9: Data Integrity and Error Handling

**User Story:** As a data engineer, I want robust data integrity controls and error handling, so that the collected data is reliable and the system is resilient to failures.

#### Acceptance Criteria

1. WHEN storing any data THEN the system SHALL implement duplicate prevention using appropriate unique constraints
2. WHEN data collection fails THEN the system SHALL log detailed error information and continue with other operations
3. WHEN API errors occur THEN the system SHALL implement exponential backoff with maximum retry limits
4. WHEN data gaps are detected THEN the system SHALL flag inconsistencies and attempt automated recovery
5. IF critical errors occur THEN the system SHALL maintain system stability and provide clear error reporting