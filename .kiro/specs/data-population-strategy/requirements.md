# Requirements Document

## Introduction

The current system uses a watchlist-driven approach that creates an inverted dependency chain, requiring manual population of a watchlist CSV before any data collection can begin. This creates several problems:

1. **Dependency Inversion**: The system requires pools to exist before collecting pool data
2. **Manual Bootstrapping**: Users must manually populate watchlist.csv with pool addresses
3. **Discovery Limitation**: The system cannot discover new pools organically
4. **Maintenance Overhead**: Watchlist requires manual curation and updates

The natural data flow should be: DEXes → Pools → Tokens → OHLCV/Trades, with the system automatically discovering and populating pools rather than requiring pre-defined watchlists.

## Requirements

### Requirement 1: Automated Pool Discovery

**User Story:** As a system operator, I want the system to automatically discover and populate pools from DEXes, so that I don't need to manually maintain a watchlist.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL automatically discover pools from configured DEXes
2. WHEN new pools are created on monitored DEXes THEN the system SHALL automatically detect and add them
3. WHEN pools meet volume/activity thresholds THEN they SHALL be automatically included in data collection
4. IF a pool becomes inactive THEN the system SHALL automatically reduce collection frequency or pause collection

### Requirement 2: Natural Data Flow Architecture

**User Story:** As a developer, I want the data collection to follow the natural dependency chain (DEXes → Pools → Tokens → Data), so that the system is more maintainable and logical.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL first collect DEX information
2. WHEN DEXes are populated THEN the system SHALL discover and populate pools from those DEXes
3. WHEN pools are populated THEN the system SHALL extract and populate token information
4. WHEN pools and tokens exist THEN OHLCV and trade collection SHALL proceed automatically
5. IF foreign key constraints exist THEN they SHALL be satisfied by the natural collection order

### Requirement 3: Intelligent Pool Filtering

**User Story:** As a system operator, I want the system to intelligently filter pools based on activity and volume, so that resources are focused on meaningful data.

#### Acceptance Criteria

1. WHEN discovering pools THEN the system SHALL apply volume thresholds to filter active pools
2. WHEN pools have insufficient activity THEN they SHALL be excluded from regular collection
3. WHEN pools meet activity criteria THEN they SHALL be automatically included in collection schedules
4. IF pool activity changes THEN collection frequency SHALL be adjusted accordingly

### Requirement 4: Backward Compatibility

**User Story:** As an existing user, I want to optionally use watchlists for specific monitoring, so that I can still manually curate specific pools of interest.

#### Acceptance Criteria

1. WHEN a watchlist file exists THEN the system SHALL include those pools in addition to discovered pools
2. WHEN watchlist pools are specified THEN they SHALL have priority in collection scheduling
3. WHEN watchlist pools become inactive THEN they SHALL still be monitored (unlike auto-discovered pools)
4. IF no watchlist exists THEN the system SHALL operate entirely on auto-discovery

### Requirement 5: Bootstrap and Initialization Strategy

**User Story:** As a new user, I want the system to work immediately after configuration, so that I don't need to manually populate any data files.

#### Acceptance Criteria

1. WHEN the system starts with an empty database THEN it SHALL automatically bootstrap with DEX and pool data
2. WHEN configuration specifies target DEXes THEN those SHALL be the source for initial pool discovery
3. WHEN initial bootstrap completes THEN regular collection schedules SHALL begin automatically
4. IF bootstrap fails THEN the system SHALL provide clear error messages and recovery options

### Requirement 6: Performance and Scalability

**User Story:** As a system operator, I want the auto-discovery to be efficient and scalable, so that it doesn't impact regular data collection performance.

#### Acceptance Criteria

1. WHEN discovering pools THEN the system SHALL use batch API calls for efficiency
2. WHEN many pools exist THEN discovery SHALL be paginated and rate-limited
3. WHEN discovery runs THEN it SHALL not interfere with regular OHLCV/trade collection
4. IF API limits are reached THEN discovery SHALL back off gracefully

### Requirement 7: Configuration and Control

**User Story:** As a system administrator, I want to configure discovery parameters and thresholds, so that I can control what pools are automatically included.

#### Acceptance Criteria

1. WHEN configuring the system THEN I SHALL be able to set minimum volume thresholds for auto-discovery
2. WHEN configuring the system THEN I SHALL be able to set maximum number of pools to monitor
3. WHEN configuring the system THEN I SHALL be able to enable/disable auto-discovery per DEX
4. IF thresholds change THEN existing pools SHALL be re-evaluated against new criteria