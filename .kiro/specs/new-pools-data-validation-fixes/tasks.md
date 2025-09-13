# Implementation Plan

- [ ] 1. Create Response Analyzer utility class
  - Create `ResponseAnalyzer` class in `gecko_terminal_collector/utils/response_analyzer.py`
  - Implement structure detection methods for analyzing API response formats
  - Add logging utilities for detailed response structure debugging
  - Write unit tests for response analysis functionality
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 2. Enhance New Pools Collector validation
- [ ] 2.1 Create enhanced validation class
  - Create `EnhancedNewPoolsValidator` class in `gecko_terminal_collector/collectors/enhanced_validation.py`
  - Implement fallback validation strategies for missing 'attributes' fields
  - Add alternative field mapping attempts for different response formats
  - Write unit tests for enhanced validation methods
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2_

- [ ] 2.2 Update NewPoolsCollector to use enhanced validation
  - Modify `_validate_specific_data()` method in `NewPoolsCollector` to use enhanced validator
  - Update `_extract_pool_info()` method to use resilient extraction with fallbacks
  - Add detailed logging of response structure when validation fails
  - Ensure collection continues even when some pools fail validation
  - _Requirements: 1.1, 1.3, 2.1, 2.3, 4.3_

- [ ] 2.3 Improve error reporting and logging
  - Enhance error messages to include specific field-level information
  - Add sample failed record logging for debugging purposes
  - Implement structure analysis logging when 'attributes' field is missing
  - Update validation result to include processed vs failed counts
  - _Requirements: 2.1, 2.2, 2.3, 4.4_

- [ ] 3. Fix rate limiting async/await issues
- [ ] 3.1 Create rate limiting status handler
  - Create `RateLimitingStatusHandler` class in `gecko_terminal_collector/utils/rate_limiting_status.py`
  - Implement safe status retrieval without async/await on synchronous methods
  - Add error handling for status retrieval failures
  - Write unit tests for status handler functionality
  - _Requirements: 3.1, 3.2, 3.4_

- [ ] 3.2 Fix CLI rate limiting status calls
  - Remove `await` from `rate_limiter.get_status()` calls in `examples/cli_with_scheduler.py`
  - Add proper error handling for rate limiter status retrieval failures
  - Update status display formatting to handle missing status gracefully
  - Test rate limiting status display functionality
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 4. Add comprehensive testing
- [ ] 4.1 Create unit tests for response analysis
  - Write tests for `ResponseAnalyzer` with various response formats
  - Test structure detection with missing 'attributes' fields
  - Test logging output for debugging scenarios
  - Verify field mapping detection accuracy
  - _Requirements: 2.1, 2.2, 4.1_

- [ ] 4.2 Create unit tests for enhanced validation
  - Write tests for `EnhancedNewPoolsValidator` with malformed data
  - Test fallback extraction strategies with alternative field mappings
  - Test validation continuation with partial failures
  - Verify detailed error reporting functionality
  - _Requirements: 1.1, 1.2, 1.3, 4.2, 4.3, 4.4_

- [ ] 4.3 Create integration tests for new pools collection
  - Write end-to-end tests with various API response formats
  - Test collection resilience with missing 'attributes' fields
  - Test error recovery and continuation scenarios
  - Verify rate limiting status display without errors
  - _Requirements: 1.1, 1.3, 3.2, 4.1, 4.3_

- [ ] 5. Update existing tests and documentation
- [ ] 5.1 Update existing new pools collector tests
  - Modify existing tests in `tests/test_new_pools_collector.py` to use enhanced validation
  - Add test cases for missing 'attributes' field scenarios
  - Update integration tests in `tests/test_new_pools_integration.py`
  - Ensure all tests pass with enhanced validation logic
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 5.2 Update CLI and rate limiting tests
  - Modify rate limiting tests to verify fixed async/await usage
  - Update CLI tests to ensure status retrieval works correctly
  - Add tests for error handling in status retrieval
  - Verify rate limiting status display functionality
  - _Requirements: 3.1, 3.2, 3.3, 3.4_