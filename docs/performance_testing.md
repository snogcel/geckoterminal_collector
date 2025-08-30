# Performance and Load Testing Suite

This document describes the comprehensive performance and load testing suite for the GeckoTerminal collector system, covering SQLite performance baselines, concurrent collection scenarios, database scalability limits, and PostgreSQL migration decision points.

## Overview

The performance testing suite validates system performance under various load conditions and provides benchmarks for making informed decisions about database migration from SQLite to PostgreSQL.

## Test Categories

### 1. SQLite Performance Baseline Tests

**Purpose**: Establish baseline performance metrics for OHLCV and trade data operations.

**Tests Included**:
- `test_ohlcv_write_throughput_baseline`: Measures OHLCV data write throughput
- `test_trade_write_throughput_baseline`: Measures trade data write throughput  
- `test_batch_size_optimization`: Determines optimal batch sizes for different data types

**Performance Thresholds**:
- OHLCV write throughput: > 100 records/sec
- Trade write throughput: > 200 records/sec
- Memory usage: < 100 MB during baseline tests
- Operation duration: < 30 seconds for 1000 records

### 2. Concurrent Collection Scenarios

**Purpose**: Test system behavior under concurrent load from multiple collectors.

**Tests Included**:
- `test_concurrent_ohlcv_collectors`: Multiple OHLCV collectors running simultaneously
- `test_mixed_data_type_concurrency`: Concurrent OHLCV and trade data collection
- `test_database_contention_measurement`: Measure database lock contention

**Performance Thresholds**:
- Concurrent throughput: > 300 records/sec
- Lock wait time: < 1.0 second average
- Success rate: 100% (no failed operations due to contention)

### 3. Database Scalability Limits

**Purpose**: Identify SQLite performance limits and scalability boundaries.

**Tests Included**:
- `test_data_volume_limits`: Performance with increasing data volumes (5K to 500K records)
- `test_query_performance_scaling`: Query performance as data volume increases
- `test_file_size_growth_patterns`: Database file size growth analysis

**Performance Thresholds**:
- Performance degradation: < 50% from baseline to high volume
- Database size efficiency: < 1000 bytes per record
- Query response time: < 10 seconds for complex queries

### 4. Memory and Resource Monitoring

**Purpose**: Monitor memory usage and resource consumption during high-volume operations.

**Tests Included**:
- `test_memory_usage_during_high_volume_collection`: Memory usage patterns
- `test_resource_cleanup_verification`: Proper resource cleanup validation

**Performance Thresholds**:
- Peak memory usage: < 500 MB
- Memory growth: < 300 MB during operations
- Resource cleanup: Memory increase < 100 MB after operations

### 5. API Rate Limit Compliance

**Purpose**: Validate rate limiting and backoff behavior under load, specifically designed for GeckoTerminal Free API constraints.

**GeckoTerminal Free API Limits**:
- **Rate Limit**: 30 calls per minute
- **Monthly Cap**: 10,000 calls per month
- **Access**: Default for public API without subscription

**Tests Included**:
- `test_rate_limit_backoff_behavior`: Exponential backoff implementation with realistic API limits
- `test_concurrent_rate_limit_compliance`: Rate limiting with multiple collectors respecting free tier limits

**Performance Thresholds**:
- Success rate with rate limiting: > 80%
- Backoff delay: > 1.0 second average
- API compliance: Respects 30 calls/minute limit
- Monthly usage: Tracks against 10,000 call cap

**Note**: Tests use mock API clients with reduced limits for faster execution while maintaining realistic rate limiting behavior patterns.

### 6. PostgreSQL Migration Benchmarks

**Purpose**: Establish decision points for migrating from SQLite to PostgreSQL.

**Tests Included**:
- `test_sqlite_performance_thresholds`: Performance threshold analysis
- `test_sqlalchemy_abstraction_validation`: Database abstraction layer validation

**Migration Indicators**:
- Write throughput: < 50 records/sec
- Query response time: > 10 seconds
- Concurrent users: < 2 simultaneous users
- Database size: > 500 MB
- Memory usage: > 1 GB

## Running Performance Tests

### Command Line Interface

Use the performance test runner script:

```bash
# Run all performance tests
python scripts/run_performance_tests.py

# Run specific test categories
python scripts/run_performance_tests.py --categories baseline concurrency

# Generate detailed report
python scripts/run_performance_tests.py --output performance_report.txt --json-output results.json

# Enable verbose logging
python scripts/run_performance_tests.py --verbose
```

### Programmatic Usage

```python
from tests.test_performance_load import *
from tests.performance_config import get_performance_config

# Run individual test classes
baseline_tester = TestSQLitePerformanceBaseline()
await baseline_tester.test_ohlcv_write_throughput_baseline(db_manager)

# Run comprehensive suite
results = await test_comprehensive_performance_suite(db_manager)
```

### Pytest Integration

```bash
# Run all performance tests with pytest
pytest tests/test_performance_load.py -v

# Run specific test categories
pytest tests/test_performance_load.py::TestSQLitePerformanceBaseline -v

# Run with performance markers
pytest -m "performance" -v
```

## Configuration

### Performance Thresholds

Customize performance thresholds in `tests/performance_config.py`:

```python
from tests.performance_config import create_custom_config

config = create_custom_config(
    ohlcv_write_min_throughput=150.0,  # Increase threshold
    max_memory_usage=400.0,            # Decrease memory limit
    max_query_response_time=3.0        # Stricter query time
)
```

### Test Data Configuration

Adjust test data volumes:

```python
config = create_custom_config(
    ohlcv_baseline_records=2000,       # More baseline records
    concurrent_collectors=5,           # More concurrent collectors
    batch_sizes=[500, 1000, 2500]     # Custom batch sizes
)
```

## Performance Metrics

### Key Performance Indicators (KPIs)

1. **Throughput Metrics**:
   - Records per second for OHLCV data
   - Records per second for trade data
   - Concurrent operation throughput

2. **Response Time Metrics**:
   - Write operation duration
   - Query response times
   - Lock wait times

3. **Resource Usage Metrics**:
   - Peak memory consumption
   - Database file size growth
   - CPU utilization

4. **Reliability Metrics**:
   - Success rate under load
   - Error rates during concurrent operations
   - Resource cleanup efficiency

### Benchmark Results Interpretation

#### Baseline Performance
- **Good**: Throughput > thresholds, memory usage stable
- **Warning**: Throughput 50-100% of threshold, increasing memory
- **Critical**: Throughput < 50% of threshold, memory leaks detected

#### Scalability Analysis
- **Linear Scaling**: Performance degrades < 25% with 10x data volume
- **Acceptable Scaling**: Performance degrades 25-50% with 10x data volume  
- **Poor Scaling**: Performance degrades > 50% with 10x data volume

#### Migration Decision Matrix

| Metric | SQLite OK | Consider Migration | Migrate Now |
|--------|-----------|-------------------|-------------|
| Write Throughput | > 100 rec/sec | 50-100 rec/sec | < 50 rec/sec |
| Query Response | < 5 seconds | 5-10 seconds | > 10 seconds |
| Concurrent Users | > 3 users | 2-3 users | < 2 users |
| Database Size | < 200 MB | 200-500 MB | > 500 MB |
| Memory Usage | < 500 MB | 500-1000 MB | > 1000 MB |

## API Rate Limit Considerations

### GeckoTerminal Free API Constraints

The performance tests are designed to work within GeckoTerminal's Free API limits:

**Rate Limits**:
- **Per Minute**: 30 API calls maximum
- **Per Month**: 10,000 API calls maximum
- **Burst Protection**: Tests include exponential backoff for rate limit compliance

**Performance Test Adaptations**:

1. **Mock API Testing**: Most performance tests use mock API clients to avoid consuming real API quota
2. **Reduced Test Volumes**: API rate limit tests use smaller request volumes (10-40 requests) to complete quickly
3. **Realistic Timing**: Tests simulate actual API response times (100ms) and rate limiting behavior
4. **Monthly Tracking**: Tests include monthly usage tracking to prevent exceeding the 10,000 call cap

**Production Considerations**:

```python
# Example rate-limited collector configuration
collector_config = {
    'api_calls_per_minute': 25,  # Leave 5 calls buffer
    'monthly_call_budget': 9000,  # Leave 1000 calls buffer
    'backoff_strategy': 'exponential',
    'max_retries': 3
}
```

**Monitoring API Usage**:
- Track daily API usage to stay within monthly limits
- Implement circuit breakers when approaching rate limits
- Use exponential backoff with jitter to handle rate limiting gracefully
- Consider upgrading to paid plans for higher throughput requirements

**API Usage Calculator**:

Use the included calculator to plan your collection strategy:

```bash
# Calculate usage for 100 pools with 3 data points each
python scripts/api_usage_calculator.py --pools 100 --data-points 3

# Calculate with custom safety margin
python scripts/api_usage_calculator.py --pools 50 --safety-margin 0.3

# Check if daily collection is feasible
python scripts/api_usage_calculator.py --pools 200 --data-points 2
```

The calculator provides:
- Safe usage recommendations with configurable safety margins
- Collection time estimates
- Monthly usage analysis
- Specific recommendations for your use case

## Troubleshooting Performance Issues

### Common Performance Problems

1. **Slow Write Operations**:
   - Check batch sizes (optimal: 1000-2000 records)
   - Verify SQLite WAL mode is enabled
   - Monitor disk I/O and available space

2. **High Memory Usage**:
   - Implement proper connection pooling
   - Add garbage collection calls in long-running operations
   - Check for memory leaks in data processing

3. **Database Lock Contention**:
   - Reduce concurrent writer count
   - Implement exponential backoff
   - Consider read-only replicas for queries

4. **Query Performance Degradation**:
   - Add appropriate database indexes
   - Optimize query patterns
   - Consider data archiving strategies

### Performance Optimization Tips

1. **SQLite Optimization**:
   ```sql
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA cache_size=-64000;  -- 64MB cache
   PRAGMA temp_store=MEMORY;
   ```

2. **Connection Pool Tuning**:
   ```python
   DatabaseConfig(
       pool_size=5,
       max_overflow=10,
       pool_pre_ping=True,
       pool_recycle=3600
   )
   ```

3. **Batch Processing**:
   - Use batch sizes of 1000-2000 records
   - Implement transaction batching
   - Add periodic garbage collection

## Continuous Performance Monitoring

### Automated Performance Testing

Integrate performance tests into CI/CD pipeline:

```yaml
# .github/workflows/performance.yml
name: Performance Tests
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday
  
jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Performance Tests
        run: |
          python scripts/run_performance_tests.py --output performance_report.txt
          # Upload results to monitoring system
```

### Performance Alerting

Set up alerts for performance degradation:

```python
# Example monitoring integration
def check_performance_thresholds(results):
    alerts = []
    
    if results['baseline']['ohlcv_throughput'] < 100:
        alerts.append("OHLCV write throughput below threshold")
    
    if results['memory']['peak_usage'] > 500:
        alerts.append("Memory usage exceeds limit")
    
    return alerts
```

## Migration Planning

### PostgreSQL Migration Checklist

When performance tests indicate migration is needed:

1. **Pre-Migration**:
   - [ ] Validate SQLAlchemy abstraction layer
   - [ ] Test connection string changes
   - [ ] Plan data migration strategy
   - [ ] Set up PostgreSQL infrastructure

2. **Migration Process**:
   - [ ] Export existing SQLite data
   - [ ] Create PostgreSQL schema
   - [ ] Import data with validation
   - [ ] Update configuration files

3. **Post-Migration**:
   - [ ] Run performance tests on PostgreSQL
   - [ ] Compare performance metrics
   - [ ] Monitor production performance
   - [ ] Document lessons learned

### Expected Performance Improvements

After migrating to PostgreSQL:

- **Concurrent Users**: 10-50+ simultaneous users
- **Write Throughput**: 500-2000+ records/sec
- **Query Performance**: Complex queries < 1 second
- **Database Size**: Multi-GB databases supported
- **Memory Efficiency**: Better memory management

## Reporting and Analysis

### Performance Report Format

The test runner generates comprehensive reports including:

1. **Executive Summary**: Pass/fail rates and key metrics
2. **Detailed Results**: Individual test outcomes
3. **Performance Trends**: Throughput and response time analysis
4. **Resource Usage**: Memory and disk utilization
5. **Migration Recommendations**: Decision matrix and next steps

### Historical Performance Tracking

Maintain performance history for trend analysis:

```python
# Store results in time series database
performance_history = {
    'timestamp': datetime.utcnow(),
    'ohlcv_throughput': results['baseline']['ohlcv_throughput'],
    'memory_peak': results['memory']['peak_usage'],
    'migration_score': results['migration']['recommendation_score']
}
```

## Summary: API Rate Limit Alignment

**Yes, the performance tests are designed to align with GeckoTerminal Free API limits:**

✅ **Rate Limit Compliance**:
- Tests respect the 30 calls/minute limit
- Mock API clients simulate realistic rate limiting behavior
- Exponential backoff testing ensures proper handling of rate limits

✅ **Monthly Usage Awareness**:
- Tests track against the 10,000 calls/month cap
- API usage calculator helps plan collection strategies
- Performance tests use minimal real API calls (mostly mocked)

✅ **Realistic Testing**:
- Test volumes are sized appropriately for free tier constraints
- Timing simulates actual API response delays (100ms)
- Backoff strategies are tested with realistic delays

✅ **Production Guidance**:
- Clear recommendations for staying within limits
- Tools to calculate safe usage patterns
- Migration guidance when limits become constraining

**Key Takeaway**: The performance testing suite is specifically designed to work within the Free API constraints while providing meaningful performance insights. Most tests use mock APIs to avoid consuming your quota, and the few that might use real APIs are designed to stay well within the limits.

This comprehensive performance testing suite ensures the GeckoTerminal collector system maintains optimal performance and provides clear guidance for scaling decisions while respecting API rate limits.