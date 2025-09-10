# Requirements Document

## Introduction

The GeckoTerminal data collection system has several critical issues affecting data reliability, API rate limit handling, database population, and test coverage. This feature addresses these systemic issues to ensure robust data collection, proper error handling, and comprehensive monitoring capabilities. The fixes will resolve API rate limiting problems, data validation failures, missing database records, and integrate the existing QLib symbol case-sensitivity improvements.

## Requirements

### Requirement 1

**User Story:** As a system operator, I want the data collection system to handle GeckoTerminal API rate limits gracefully, so that data collection continues reliably without service interruption.

#### Acceptance Criteria

1. WHEN the system encounters a 429 (Too Many Requests) response THEN it SHALL implement exponential backoff with jitter
2. WHEN API rate limits are reached THEN the system SHALL log appropriate warnings and create system alerts
3. WHEN rate limiting occurs THEN the system SHALL track rate limit events in the performance_metrics table
4. WHEN the CLI script runs collectors THEN the rate limiter backoff logic SHALL function correctly
5. WHEN multiple collectors are running THEN the system SHALL coordinate API usage to stay within rate limits

### Requirement 2

**User Story:** As a data analyst, I want all database tables to be properly populated with collection metadata and performance data, so that I can monitor system health and data quality.

#### Acceptance Criteria

1. WHEN any collector runs THEN collection metadata SHALL be stored in the collection_metadata table
2. WHEN collectors execute THEN execution history SHALL be recorded in the execution_history table
3. WHEN performance metrics are generated THEN they SHALL be stored in the performance_metrics table
4. WHEN system errors occur THEN alerts SHALL be created in the system_alerts table
5. WHEN OHLCV data is collected THEN it SHALL be properly parsed and stored in the database

### Requirement 3

**User Story:** As a developer, I want data validation to work consistently across all collectors, so that the system handles both DataFrame and List data types correctly.

#### Acceptance Criteria

1. WHEN DEX monitoring collector receives API responses THEN it SHALL handle both DataFrame and List data types
2. WHEN data validation occurs THEN the system SHALL provide clear error messages for validation failures
3. WHEN CSV fixtures are used in tests THEN they SHALL be converted to appropriate JSON format for consistency
4. WHEN collectors process API responses THEN the response_to_dict method SHALL work consistently
5. WHEN validation fails THEN the system SHALL log detailed information about the data type mismatch

### Requirement 4

**User Story:** As a system administrator, I want comprehensive test coverage that validates end-to-end workflows, so that I can ensure system reliability before deployment.

#### Acceptance Criteria

1. WHEN running the CLI with scheduler THEN all collectors SHALL execute successfully without type errors
2. WHEN API limits are simulated THEN the rate limiting logic SHALL be properly tested
3. WHEN integration tests run THEN they SHALL validate the complete data flow from API to database
4. WHEN test fixtures are used THEN they SHALL accurately represent real API responses
5. WHEN performance tests run THEN they SHALL validate system behavior under load

### Requirement 5

**User Story:** As a QLib user, I want symbol case-sensitivity to be handled correctly throughout the system, so that I can reliably export and import data with proper address mapping.

#### Acceptance Criteria

1. WHEN symbols are generated THEN they SHALL preserve original cryptocurrency address case
2. WHEN symbol lookups occur THEN the system SHALL support both case-sensitive and case-insensitive matching
3. WHEN QLib export happens THEN symbol mappings SHALL maintain bidirectional compatibility
4. WHEN external systems provide lowercase symbols THEN the system SHALL correctly map them to original pools
5. WHEN the SymbolMapper is integrated THEN it SHALL work seamlessly with all existing collectors