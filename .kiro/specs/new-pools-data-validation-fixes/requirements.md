# Requirements Document

## Introduction

This feature addresses critical issues in the new pools collection system where data validation is failing due to missing 'attributes' fields in API responses, and rate limiting status retrieval is causing async/await errors. The system needs to be more resilient to API response variations and handle rate limiting status correctly.

## Requirements

### Requirement 1

**User Story:** As a data collector operator, I want the new pools collector to handle API response variations gracefully, so that data collection continues even when the API response structure differs from expectations.

#### Acceptance Criteria

1. WHEN the API returns pools without 'attributes' fields THEN the system SHALL log detailed information about the actual response structure
2. WHEN the API response structure varies from expected format THEN the system SHALL attempt to extract data using alternative field mappings
3. WHEN data validation fails for some pools THEN the system SHALL continue processing valid pools and provide detailed error reporting
4. WHEN the API response contains nested data structures THEN the system SHALL flatten or normalize the data appropriately

### Requirement 2

**User Story:** As a data collector operator, I want comprehensive logging of API response structures, so that I can diagnose and fix data parsing issues quickly.

#### Acceptance Criteria

1. WHEN an API response is received THEN the system SHALL log the response structure at debug level
2. WHEN validation fails THEN the system SHALL log sample failed records with their actual structure
3. WHEN 'attributes' field is missing THEN the system SHALL log the available fields in the pool data
4. WHEN data extraction fails THEN the system SHALL provide specific field-level error information

### Requirement 3

**User Story:** As a system administrator, I want rate limiting status retrieval to work correctly, so that I can monitor API usage without encountering async/await errors.

#### Acceptance Criteria

1. WHEN retrieving rate limiter status THEN the system SHALL NOT use await on non-coroutine methods
2. WHEN rate limiter status is requested THEN the system SHALL return current status without errors
3. WHEN rate limiting information is displayed THEN the system SHALL show accurate metrics and state
4. WHEN rate limiter methods are called THEN the system SHALL use proper async/sync calling conventions

### Requirement 4

**User Story:** As a data collector operator, I want the system to be resilient to API response format changes, so that data collection continues with minimal disruption.

#### Acceptance Criteria

1. WHEN the API response format changes THEN the system SHALL attempt multiple parsing strategies
2. WHEN primary data extraction fails THEN the system SHALL fall back to alternative field mappings
3. WHEN pool data is in unexpected format THEN the system SHALL extract available fields and log missing ones
4. WHEN validation errors occur THEN the system SHALL provide actionable error messages for debugging