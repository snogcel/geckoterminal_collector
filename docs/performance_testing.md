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

**Purpose**: Validate rate limiting and backoff behavior under load.

**Tests Included**:
- `test_rate_limit_backoff_behavior`: Exponential backoff implementation
- `test_concurrent_rate_limit_compliance`: Rate limiting with multiple collectors

**Performance Thresholds**:
- Success rate with rate limiting: > 80%
- Backoff delay: > 1.0 second average
- Concurrent compliance: No rate limit violations

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

This comprehensive performance testing suite ensures the GeckoTerminal collector system maintains optimal performance and provides clear guidance for scaling decisions.