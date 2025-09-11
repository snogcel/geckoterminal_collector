# Requirements Document

## Introduction

This specification defines the integration of the NewPoolsCollector functionality into the existing CLI scheduler infrastructure. The integration will provide comprehensive command-line access to new pools collection with full rate limiting, monitoring, and operational capabilities while maintaining consistency with the existing CLI architecture.

## Requirements

### Requirement 1

**User Story:** As a system operator, I want to run new pools collection through the existing CLI scheduler, so that I can leverage the existing rate limiting and monitoring infrastructure.

#### Acceptance Criteria

1. WHEN the CLI scheduler starts THEN the system SHALL register NewPoolsCollector instances for each configured network
2. WHEN a network is configured for new pools collection THEN the system SHALL create a dedicated rate limiter instance for that network
3. WHEN the scheduler runs new pools collection THEN the system SHALL use `client.get_new_pools_by_network()` SDK method to fetch network-wide pools data
4. WHEN the scheduler runs new pools collection THEN the system SHALL apply rate limiting and circuit breaker protection
5. WHEN new pools collection completes THEN the system SHALL update metadata tracking and monitoring metrics

### Requirement 2

**User Story:** As a system operator, I want dedicated CLI commands for new pools collection, so that I can run on-demand collection and view statistics independently of the scheduler.

#### Acceptance Criteria

1. WHEN I run `collect-new-pools` command THEN the system SHALL execute new pools collection for the specified network
2. WHEN I specify `--network` parameter THEN the system SHALL collect pools only for that network
3. WHEN I use `--mock` flag THEN the system SHALL use mock clients for testing
4. WHEN collection completes THEN the system SHALL display comprehensive results including pools created and history records
5. WHEN I run `new-pools-stats` command THEN the system SHALL display database statistics and recent collection data
6. WHEN I specify `--limit` parameter THEN the system SHALL show the specified number of recent records

### Requirement 3

**User Story:** As a system operator, I want new pools collectors to integrate with existing CLI commands, so that I can manage them through the unified interface.

#### Acceptance Criteria

1. WHEN I run `status` command THEN the system SHALL display new pools collectors in the scheduler status
2. WHEN I run `run-once` command with new pools collector THEN the system SHALL execute the collector through the scheduler
3. WHEN I run `rate-limit-status` command THEN the system SHALL show rate limiting status for new pools collectors
4. WHEN I run `reset-rate-limiter` command THEN the system SHALL reset rate limiters for new pools collectors

### Requirement 4

**User Story:** As a data analyst, I want dual-table data storage for new pools collection, so that I can maintain referential integrity and create comprehensive historical records for predictive modeling.

#### Acceptance Criteria

1. WHEN new pools are collected THEN the system SHALL populate the Pools table with essential pool information (id, address, name, dex_id, base_token_id, quote_token_id, reserve_usd, created_at, last_updated)
2. WHEN new pools are collected THEN the system SHALL create historical records in the new_pools_history table with comprehensive market data
3. WHEN storing pool data THEN the system SHALL use pool IDs like "solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU" to maintain network-specific identification
4. WHEN storing historical data THEN the system SHALL capture all available market metrics (prices, volumes, transactions, price changes, FDV, market cap)
5. WHEN pools already exist THEN the system SHALL skip pool creation but always create new historical records

### Requirement 5

**User Story:** As a system operator, I want comprehensive statistics and monitoring for new pools collection, so that I can track collection performance and data quality.

#### Acceptance Criteria

1. WHEN new pools collection runs THEN the system SHALL track pools created, history records, and API response metrics
2. WHEN I request statistics THEN the system SHALL show total database counts, recent records, and collection activity
3. WHEN I filter by network THEN the system SHALL show network-specific statistics and distribution
4. WHEN collection fails THEN the system SHALL provide detailed error information and rate limiting status

### Requirement 6

**User Story:** As a data analyst, I want network-wide new pools collection, so that I can capture all new pools across the entire network rather than being limited to specific DEXes.

#### Acceptance Criteria

1. WHEN collecting new pools for Solana THEN the system SHALL fetch pools from all DEXes on the network (pump-fun, pumpswap, etc.)
2. WHEN using `client.get_new_pools_by_network("solana")` THEN the system SHALL receive pools from multiple DEXes in a single API call
3. WHEN processing pool data THEN the system SHALL correctly identify the source DEX from the dex_id field
4. WHEN storing pool data THEN the system SHALL maintain network-specific pool IDs with proper network prefixes
5. WHEN displaying statistics THEN the system SHALL show DEX distribution across the collected pools

### Requirement 7

**User Story:** As a system operator, I want flexible network configuration for new pools collection, so that I can enable/disable collection per network and configure intervals independently.

#### Acceptance Criteria

1. WHEN the system starts THEN the system SHALL support configurable networks (solana, ethereum, etc.)
2. WHEN a network is configured THEN the system SHALL allow independent enable/disable control
3. WHEN a network is configured THEN the system SHALL allow independent interval configuration
4. WHEN a network is disabled THEN the system SHALL not run collection for that network
5. WHEN network configuration changes THEN the system SHALL apply changes without requiring restart

### Requirement 7

**User Story:** As a system operator, I want full rate limiting integration for new pools collection, so that I can stay within API limits and avoid service disruption.

#### Acceptance Criteria

1. WHEN new pools collection starts THEN the system SHALL check rate limiter status before making API calls
2. WHEN rate limits are exceeded THEN the system SHALL apply backoff and circuit breaker protection
3. WHEN collection completes THEN the system SHALL update rate limiting metrics and usage statistics
4. WHEN rate limiting issues occur THEN the system SHALL provide clear error messages and recovery guidance
5. WHEN I reset rate limiters THEN the system SHALL reset new pools collector rate limiters

### Requirement 8

**User Story:** As a system operator, I want consistent error handling and logging for new pools collection, so that I can troubleshoot issues and monitor system health.

#### Acceptance Criteria

1. WHEN errors occur during collection THEN the system SHALL log detailed error information with context
2. WHEN API calls fail THEN the system SHALL distinguish between rate limiting and other errors
3. WHEN data validation fails THEN the system SHALL continue processing valid records and report validation errors
4. WHEN database operations fail THEN the system SHALL provide clear error messages and rollback guidance
5. WHEN collection completes with errors THEN the system SHALL report both successful and failed operations

### Requirement 9

**User Story:** As a system operator, I want backward compatibility with existing CLI functionality, so that current operations continue to work without modification.

#### Acceptance Criteria

1. WHEN existing CLI commands run THEN the system SHALL maintain current functionality and behavior
2. WHEN existing collectors run THEN the system SHALL not be affected by new pools collector integration
3. WHEN configuration is updated THEN the system SHALL maintain compatibility with existing configuration formats
4. WHEN new functionality is added THEN the system SHALL not break existing command interfaces