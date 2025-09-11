# Implementation Plan

- [x] 1. Enhance CLI collector registration system




  - Modify `_register_collectors` method in `SchedulerCLI` class to support network-specific NewPoolsCollector instances
  - Add support for additional constructor parameters in collector configuration tuples
  - Implement network-specific rate limiter assignment for new pools collectors
  - Create collector configuration entries for solana and ethereum networks with configurable intervals
  - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2, 6.3, 6.4_

- [x] 2. Implement collect-new-pools CLI command





  - Create new CLI command function with click decorators for network-specific new pools collection
  - Add command-line options for config file path, network selection, and mock mode
  - Implement async execution wrapper to initialize SchedulerCLI and run NewPoolsCollector
  - Add comprehensive result reporting including pools created, history records, and API metrics
  - Integrate rate limiting status display after collection execution
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.1, 7.2, 7.3_

- [x] 3. Implement new-pools-stats CLI command




  - Create new CLI command function for displaying new pools collection statistics
  - Add command-line options for config file, network filtering, and record limit
  - Implement database statistics collection (total pools, history records, network distribution)
  - Create recent records display with comprehensive pool information formatting
  - Add DEX distribution analysis and collection activity timeline
  - Implement network filtering capability for targeted statistics
  - _Requirements: 2.5, 2.6, 5.1, 5.2, 5.3_

- [ ] 4. Enhance existing CLI commands for new pools support





  - Modify `status` command to display new pools collectors in scheduler status output
  - Update `run-once` command to support new pools collector execution through job ID matching
  - Enhance `rate-limit-status` command to show new pools collector rate limiting information
  - Update `reset-rate-limiter` command to handle new pools collector rate limiter reset
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.4, 7.5_

- [ ] 5. Implement statistics and monitoring engine
  - Create database statistics collection functions for pools and history record counts
  - Implement network and DEX distribution analysis functions
  - Create recent records retrieval with proper formatting and filtering
  - Add collection activity timeline tracking for the last 24 hours
  - Implement comprehensive error reporting with rate limiting context
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.3, 8.4_

- [ ] 6. Add comprehensive error handling and logging
  - Implement specific error detection for rate limiting issues (429 status codes)
  - Add detailed error context logging for troubleshooting new pools collection
  - Create graceful error handling that continues processing valid records
  - Implement rate limiting error guidance and recovery suggestions
  - Add validation error reporting while maintaining collection continuity
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 7. Create integration tests for CLI new pools functionality
  - Write unit tests for new CLI commands (collect-new-pools, new-pools-stats)
  - Create integration tests for collector registration with network parameters
  - Implement tests for rate limiting integration with new pools collectors
  - Add tests for statistics engine functionality and filtering
  - Create end-to-end tests for complete CLI workflow with mock data
  - _Requirements: 1.4, 2.4, 3.4, 5.4, 7.6_

- [ ] 8. Update configuration and documentation
  - Add network configuration examples for new pools collection in config files
  - Update CLI help documentation to include new commands and options
  - Create operational documentation for new pools collection management
  - Add troubleshooting guide for common new pools collection issues
  - Document rate limiting configuration for network-specific collectors
  - _Requirements: 6.5, 9.1, 9.2, 9.3, 9.4_