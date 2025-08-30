"""
Performance and load testing suite for GeckoTerminal collector system.

This module implements comprehensive performance testing including:
- SQLite performance baseline tests for OHLCV and trade data write throughput
- Concurrent collection scenarios with multiple collectors
- Database scalability testing to identify SQLite limits
- Memory usage and resource consumption monitoring
- API rate limit compliance and backoff behavior validation
- Performance benchmarks for PostgreSQL migration decision points
- SQLAlchemy abstraction layer validation for database migration scenarios

Requirements covered: 1.4, 2.4, 9.2
"""

import asyncio
import gc
import logging
import os
import psutil
import pytest
import pytest_asyncio
import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.models.core import OHLCVRecord, TradeRecord, Pool, Token

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Container for performance metrics and measurements."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.memory_start: Optional[float] = None
        self.memory_peak: Optional[float] = None
        self.memory_end: Optional[float] = None
        self.records_processed: int = 0
        self.errors: List[str] = []
        self.database_size_start: Optional[int] = None
        self.database_size_end: Optional[int] = None
    
    @property
    def duration(self) -> float:
        """Get test duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def throughput(self) -> float:
        """Get records per second throughput."""
        if self.duration > 0:
            return self.records_processed / self.duration
        return 0.0
    
    @property
    def memory_usage_mb(self) -> float:
        """Get peak memory usage in MB."""
        if self.memory_peak:
            return self.memory_peak / (1024 * 1024)
        return 0.0


class DatabasePerformanceTester:
    """Database performance testing utilities."""
    
    def __init__(self, db_manager: SQLAlchemyDatabaseManager):
        self.db_manager = db_manager
        self.process = psutil.Process()
    
    def start_monitoring(self, metrics: PerformanceMetrics) -> None:
        """Start performance monitoring."""
        metrics.start_time = time.time()
        metrics.memory_start = self.process.memory_info().rss
        metrics.memory_peak = metrics.memory_start
        
        # Get database file size if SQLite
        if hasattr(self.db_manager.connection, 'engine'):
            db_url = str(self.db_manager.connection.engine.url)
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    metrics.database_size_start = os.path.getsize(db_path)
    
    def update_monitoring(self, metrics: PerformanceMetrics) -> None:
        """Update performance monitoring metrics."""
        current_memory = self.process.memory_info().rss
        if current_memory > metrics.memory_peak:
            metrics.memory_peak = current_memory
    
    def stop_monitoring(self, metrics: PerformanceMetrics) -> None:
        """Stop performance monitoring and finalize metrics."""
        metrics.end_time = time.time()
        metrics.memory_end = self.process.memory_info().rss
        
        # Get final database file size if SQLite
        if hasattr(self.db_manager.connection, 'engine'):
            db_url = str(self.db_manager.connection.engine.url)
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    metrics.database_size_end = os.path.getsize(db_path)


def generate_test_ohlcv_data(
    pool_id: str, 
    timeframe: str, 
    count: int, 
    start_time: Optional[datetime] = None
) -> List[OHLCVRecord]:
    """Generate test OHLCV data for performance testing."""
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(hours=count)
    
    # Calculate interval based on timeframe
    if timeframe.endswith('m'):
        interval_minutes = int(timeframe[:-1])
        interval = timedelta(minutes=interval_minutes)
    elif timeframe.endswith('h'):
        interval_hours = int(timeframe[:-1])
        interval = timedelta(hours=interval_hours)
    elif timeframe.endswith('d'):
        interval_days = int(timeframe[:-1])
        interval = timedelta(days=interval_days)
    else:
        interval = timedelta(hours=1)  # Default to 1 hour
    
    records = []
    current_time = start_time
    base_price = Decimal('100.0')
    
    for i in range(count):
        # Generate realistic OHLCV data with some variation
        price_variation = Decimal(str(0.95 + (i % 20) * 0.005))  # ±5% variation
        open_price = base_price * price_variation
        high_price = open_price * Decimal('1.02')  # 2% higher
        low_price = open_price * Decimal('0.98')   # 2% lower
        close_price = open_price * Decimal(str(0.99 + (i % 10) * 0.002))
        volume_usd = Decimal(str(1000 + (i % 100) * 50))
        
        record = OHLCVRecord(
            pool_id=pool_id,
            timeframe=timeframe,
            timestamp=int(current_time.timestamp()),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume_usd=volume_usd,
            datetime=current_time
        )
        records.append(record)
        current_time += interval
    
    return records


def generate_test_trade_data(
    pool_id: str, 
    count: int, 
    start_time: Optional[datetime] = None
) -> List[TradeRecord]:
    """Generate test trade data for performance testing."""
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(hours=1)
    
    records = []
    current_time = start_time
    
    for i in range(count):
        record = TradeRecord(
            id=f"trade_{pool_id}_{i}_{int(current_time.timestamp())}",
            pool_id=pool_id,
            block_number=1000000 + i,
            tx_hash=f"0x{'a' * 60}{i:04d}",
            from_token_amount=Decimal(str(100 + i % 1000)),
            to_token_amount=Decimal(str(200 + i % 2000)),
            price_usd=Decimal(str(50 + (i % 100) * 0.5)),
            volume_usd=Decimal(str(1000 + i % 5000)),
            side='buy' if i % 2 == 0 else 'sell',
            block_timestamp=current_time
        )
        records.append(record)
        current_time += timedelta(seconds=30)  # 30 second intervals
    
    return records


@pytest.fixture
def temp_database_config():
    """Create a temporary database configuration for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_performance.db")
    
    config = DatabaseConfig(
        url=f"sqlite:///{db_path}",
        pool_size=5,
        max_overflow=10,
        echo=False
    )
    
    yield config
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    os.rmdir(temp_dir)


@pytest_asyncio.fixture
async def performance_db_manager(temp_database_config):
    """Create a database manager for performance testing."""
    manager = SQLAlchemyDatabaseManager(temp_database_config)
    await manager.initialize()
    
    yield manager
    
    await manager.close()


class TestSQLitePerformanceBaseline:
    """Test SQLite performance baselines for OHLCV and trade data."""
    
    @pytest.mark.asyncio
    async def test_ohlcv_write_throughput_baseline(self, performance_db_manager):
        """Test OHLCV data write throughput baseline performance."""
        tester = DatabasePerformanceTester(performance_db_manager)
        metrics = PerformanceMetrics()
        
        # Test parameters
        pool_id = "test_pool_ohlcv_baseline"
        timeframe = "1h"
        record_count = 1000
        
        # Generate test data
        test_data = generate_test_ohlcv_data(pool_id, timeframe, record_count)
        metrics.records_processed = len(test_data)
        
        # Start monitoring
        tester.start_monitoring(metrics)
        
        try:
            # Perform the write operation
            stored_count = await performance_db_manager.store_ohlcv_data(test_data)
            assert stored_count == record_count
            
        finally:
            tester.stop_monitoring(metrics)
        
        # Performance assertions
        assert metrics.throughput > 100, f"OHLCV write throughput too low: {metrics.throughput:.2f} records/sec"
        assert metrics.duration < 30, f"OHLCV write took too long: {metrics.duration:.2f} seconds"
        assert metrics.memory_usage_mb < 100, f"Memory usage too high: {metrics.memory_usage_mb:.2f} MB"
        
        logger.info(f"OHLCV Baseline - Throughput: {metrics.throughput:.2f} records/sec, "
                   f"Duration: {metrics.duration:.2f}s, Memory: {metrics.memory_usage_mb:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_trade_write_throughput_baseline(self, performance_db_manager):
        """Test trade data write throughput baseline performance."""
        tester = DatabasePerformanceTester(performance_db_manager)
        metrics = PerformanceMetrics()
        
        # Test parameters
        pool_id = "test_pool_trade_baseline"
        record_count = 1000
        
        # Generate test data
        test_data = generate_test_trade_data(pool_id, record_count)
        metrics.records_processed = len(test_data)
        
        # Start monitoring
        tester.start_monitoring(metrics)
        
        try:
            # Perform the write operation
            stored_count = await performance_db_manager.store_trade_data(test_data)
            assert stored_count == record_count
            
        finally:
            tester.stop_monitoring(metrics)
        
        # Performance assertions
        assert metrics.throughput > 200, f"Trade write throughput too low: {metrics.throughput:.2f} records/sec"
        assert metrics.duration < 20, f"Trade write took too long: {metrics.duration:.2f} seconds"
        assert metrics.memory_usage_mb < 100, f"Memory usage too high: {metrics.memory_usage_mb:.2f} MB"
        
        logger.info(f"Trade Baseline - Throughput: {metrics.throughput:.2f} records/sec, "
                   f"Duration: {metrics.duration:.2f}s, Memory: {metrics.memory_usage_mb:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_batch_size_optimization(self, performance_db_manager):
        """Test optimal batch sizes for different data types."""
        batch_sizes = [100, 500, 1000, 2000, 5000]
        results = {}
        
        for batch_size in batch_sizes:
            tester = DatabasePerformanceTester(performance_db_manager)
            metrics = PerformanceMetrics()
            
            # Test OHLCV batch performance
            pool_id = f"test_pool_batch_{batch_size}"
            test_data = generate_test_ohlcv_data(pool_id, "1h", batch_size)
            metrics.records_processed = len(test_data)
            
            tester.start_monitoring(metrics)
            try:
                await performance_db_manager.store_ohlcv_data(test_data)
            finally:
                tester.stop_monitoring(metrics)
            
            results[batch_size] = {
                'throughput': metrics.throughput,
                'duration': metrics.duration,
                'memory_mb': metrics.memory_usage_mb
            }
        
        # Find optimal batch size (highest throughput with reasonable memory usage)
        optimal_batch = max(
            results.keys(), 
            key=lambda x: results[x]['throughput'] if results[x]['memory_mb'] < 200 else 0
        )
        
        logger.info(f"Batch size optimization results: {results}")
        logger.info(f"Optimal batch size: {optimal_batch}")
        
        # Assert that we found a reasonable optimal batch size
        assert optimal_batch >= 500, "Optimal batch size should be at least 500 for efficiency"


class TestConcurrentCollectionScenarios:
    """Test concurrent collection scenarios with multiple collectors."""
    
    @pytest.mark.asyncio
    async def test_concurrent_ohlcv_collectors(self, performance_db_manager):
        """Test multiple OHLCV collectors running concurrently."""
        num_collectors = 3
        records_per_collector = 500
        
        async def collector_task(collector_id: int) -> PerformanceMetrics:
            """Simulate a single collector task."""
            tester = DatabasePerformanceTester(performance_db_manager)
            metrics = PerformanceMetrics()
            
            pool_id = f"concurrent_pool_{collector_id}"
            test_data = generate_test_ohlcv_data(pool_id, "1h", records_per_collector)
            metrics.records_processed = len(test_data)
            
            tester.start_monitoring(metrics)
            try:
                stored_count = await performance_db_manager.store_ohlcv_data(test_data)
                assert stored_count == records_per_collector
            except Exception as e:
                metrics.errors.append(str(e))
                raise
            finally:
                tester.stop_monitoring(metrics)
            
            return metrics
        
        # Run collectors concurrently
        start_time = time.time()
        tasks = [collector_task(i) for i in range(num_collectors)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        # Analyze results
        successful_results = [r for r in results if isinstance(r, PerformanceMetrics)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(failed_results) == 0, f"Some collectors failed: {failed_results}"
        assert len(successful_results) == num_collectors
        
        total_records = sum(m.records_processed for m in successful_results)
        overall_throughput = total_records / total_duration
        
        # Performance assertions for concurrent execution
        assert overall_throughput > 300, f"Concurrent throughput too low: {overall_throughput:.2f} records/sec"
        assert total_duration < 60, f"Concurrent execution took too long: {total_duration:.2f} seconds"
        
        logger.info(f"Concurrent OHLCV - {num_collectors} collectors, "
                   f"Overall throughput: {overall_throughput:.2f} records/sec, "
                   f"Duration: {total_duration:.2f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_data_type_concurrency(self, performance_db_manager):
        """Test concurrent collection of different data types (OHLCV + trades)."""
        
        async def ohlcv_collector() -> PerformanceMetrics:
            """OHLCV collector task."""
            tester = DatabasePerformanceTester(performance_db_manager)
            metrics = PerformanceMetrics()
            
            test_data = generate_test_ohlcv_data("mixed_pool_ohlcv", "1h", 800)
            metrics.records_processed = len(test_data)
            
            tester.start_monitoring(metrics)
            try:
                await performance_db_manager.store_ohlcv_data(test_data)
            finally:
                tester.stop_monitoring(metrics)
            
            return metrics
        
        async def trade_collector() -> PerformanceMetrics:
            """Trade collector task."""
            tester = DatabasePerformanceTester(performance_db_manager)
            metrics = PerformanceMetrics()
            
            test_data = generate_test_trade_data("mixed_pool_trades", 1200)
            metrics.records_processed = len(test_data)
            
            tester.start_monitoring(metrics)
            try:
                await performance_db_manager.store_trade_data(test_data)
            finally:
                tester.stop_monitoring(metrics)
            
            return metrics
        
        # Run both collectors concurrently
        start_time = time.time()
        ohlcv_result, trade_result = await asyncio.gather(
            ohlcv_collector(), 
            trade_collector()
        )
        total_duration = time.time() - start_time
        
        total_records = ohlcv_result.records_processed + trade_result.records_processed
        overall_throughput = total_records / total_duration
        
        # Performance assertions
        assert overall_throughput > 400, f"Mixed concurrency throughput too low: {overall_throughput:.2f} records/sec"
        assert total_duration < 45, f"Mixed concurrent execution took too long: {total_duration:.2f} seconds"
        
        logger.info(f"Mixed Concurrency - OHLCV + Trades, "
                   f"Overall throughput: {overall_throughput:.2f} records/sec, "
                   f"Duration: {total_duration:.2f}s")
    
    @pytest.mark.asyncio
    async def test_database_contention_measurement(self, performance_db_manager):
        """Measure database contention under concurrent load."""
        num_concurrent_writers = 5
        records_per_writer = 300
        contention_metrics = []
        
        async def contention_writer(writer_id: int) -> Dict:
            """Writer that measures lock wait times."""
            lock_waits = []
            successful_writes = 0
            failed_writes = 0
            
            for batch in range(10):  # 10 batches per writer
                batch_start = time.time()
                
                pool_id = f"contention_pool_{writer_id}_{batch}"
                test_data = generate_test_ohlcv_data(pool_id, "5m", records_per_writer // 10)
                
                try:
                    write_start = time.time()
                    await performance_db_manager.store_ohlcv_data(test_data)
                    write_duration = time.time() - write_start
                    
                    lock_waits.append(write_duration)
                    successful_writes += len(test_data)
                    
                except Exception as e:
                    failed_writes += len(test_data)
                    logger.warning(f"Writer {writer_id} batch {batch} failed: {e}")
                
                # Small delay between batches to simulate real collection intervals
                await asyncio.sleep(0.1)
            
            return {
                'writer_id': writer_id,
                'avg_lock_wait': sum(lock_waits) / len(lock_waits) if lock_waits else 0,
                'max_lock_wait': max(lock_waits) if lock_waits else 0,
                'successful_writes': successful_writes,
                'failed_writes': failed_writes,
                'lock_waits': lock_waits
            }
        
        # Run concurrent writers
        start_time = time.time()
        tasks = [contention_writer(i) for i in range(num_concurrent_writers)]
        results = await asyncio.gather(*tasks)
        total_duration = time.time() - start_time
        
        # Analyze contention metrics
        avg_lock_waits = [r['avg_lock_wait'] for r in results]
        max_lock_waits = [r['max_lock_wait'] for r in results]
        total_successful = sum(r['successful_writes'] for r in results)
        total_failed = sum(r['failed_writes'] for r in results)
        
        overall_avg_lock_wait = sum(avg_lock_waits) / len(avg_lock_waits)
        overall_max_lock_wait = max(max_lock_waits)
        
        # Performance assertions for contention
        assert overall_avg_lock_wait < 1.0, f"Average lock wait too high: {overall_avg_lock_wait:.3f}s"
        assert overall_max_lock_wait < 5.0, f"Maximum lock wait too high: {overall_max_lock_wait:.3f}s"
        assert total_failed == 0, f"Some writes failed due to contention: {total_failed}"
        
        logger.info(f"Database Contention - {num_concurrent_writers} writers, "
                   f"Avg lock wait: {overall_avg_lock_wait:.3f}s, "
                   f"Max lock wait: {overall_max_lock_wait:.3f}s, "
                   f"Success rate: {total_successful/(total_successful+total_failed)*100:.1f}%")


class TestDatabaseScalabilityLimits:
    """Test database scalability to identify SQLite limits."""
    
    @pytest.mark.asyncio
    async def test_data_volume_limits(self, performance_db_manager):
        """Test SQLite performance with increasing data volumes."""
        volume_tests = [
            {'records': 5000, 'description': 'Small volume'},
            {'records': 25000, 'description': 'Medium volume'},
            {'records': 100000, 'description': 'Large volume'},
            {'records': 500000, 'description': 'Very large volume'}
        ]
        
        results = {}
        
        for test_config in volume_tests:
            record_count = test_config['records']
            description = test_config['description']
            
            tester = DatabasePerformanceTester(performance_db_manager)
            metrics = PerformanceMetrics()
            
            # Generate large dataset
            pool_id = f"volume_test_{record_count}"
            test_data = generate_test_ohlcv_data(pool_id, "1m", record_count)
            metrics.records_processed = len(test_data)
            
            tester.start_monitoring(metrics)
            
            try:
                # Store data in batches to avoid memory issues
                batch_size = 1000
                total_stored = 0
                
                for i in range(0, len(test_data), batch_size):
                    batch = test_data[i:i + batch_size]
                    stored = await performance_db_manager.store_ohlcv_data(batch)
                    total_stored += stored
                    tester.update_monitoring(metrics)
                    
                    # Force garbage collection to manage memory
                    if i % (batch_size * 10) == 0:
                        gc.collect()
                
                assert total_stored == record_count
                
            finally:
                tester.stop_monitoring(metrics)
            
            results[record_count] = {
                'description': description,
                'throughput': metrics.throughput,
                'duration': metrics.duration,
                'memory_mb': metrics.memory_usage_mb,
                'db_size_mb': (metrics.database_size_end - metrics.database_size_start) / (1024 * 1024) 
                             if metrics.database_size_start and metrics.database_size_end else 0
            }
            
            logger.info(f"{description} ({record_count:,} records) - "
                       f"Throughput: {metrics.throughput:.2f} records/sec, "
                       f"Duration: {metrics.duration:.2f}s, "
                       f"Memory: {metrics.memory_usage_mb:.2f}MB, "
                       f"DB Size: {results[record_count]['db_size_mb']:.2f}MB")
        
        # Analyze scalability trends
        throughputs = [results[r]['throughput'] for r in sorted(results.keys())]
        
        # Check for performance degradation
        performance_degradation = (throughputs[0] - throughputs[-1]) / throughputs[0]
        assert performance_degradation < 0.5, f"Performance degraded too much: {performance_degradation:.2%}"
        
        # Check database size growth is reasonable
        largest_db_size = max(results[r]['db_size_mb'] for r in results.keys())
        assert largest_db_size < 1000, f"Database size too large: {largest_db_size:.2f}MB"
        
        return results
    
    @pytest.mark.asyncio
    async def test_query_performance_scaling(self, performance_db_manager):
        """Test query performance as data volume increases."""
        # First, populate database with test data
        base_pool_id = "query_perf_test"
        record_counts = [1000, 5000, 25000, 100000]
        
        # Populate data
        for i, count in enumerate(record_counts):
            pool_id = f"{base_pool_id}_{i}"
            test_data = generate_test_ohlcv_data(pool_id, "1h", count)
            await performance_db_manager.store_ohlcv_data(test_data)
        
        query_results = {}
        
        # Test different query patterns
        query_tests = [
            {
                'name': 'single_pool_recent',
                'description': 'Recent data for single pool',
                'query_func': lambda: performance_db_manager.get_ohlcv_data(
                    f"{base_pool_id}_3", "1h", 
                    start_time=datetime.utcnow() - timedelta(days=7)
                )
            },
            {
                'name': 'single_pool_all',
                'description': 'All data for single pool',
                'query_func': lambda: performance_db_manager.get_ohlcv_data(f"{base_pool_id}_2", "1h")
            },
            {
                'name': 'gap_detection',
                'description': 'Gap detection query',
                'query_func': lambda: performance_db_manager.get_data_gaps(
                    f"{base_pool_id}_1", "1h",
                    datetime.utcnow() - timedelta(days=30),
                    datetime.utcnow()
                )
            }
        ]
        
        for query_test in query_tests:
            start_time = time.time()
            
            try:
                result = await query_test['query_func']()
                duration = time.time() - start_time
                
                query_results[query_test['name']] = {
                    'description': query_test['description'],
                    'duration': duration,
                    'result_count': len(result) if hasattr(result, '__len__') else 0,
                    'success': True
                }
                
            except Exception as e:
                duration = time.time() - start_time
                query_results[query_test['name']] = {
                    'description': query_test['description'],
                    'duration': duration,
                    'error': str(e),
                    'success': False
                }
            
            logger.info(f"Query {query_test['name']} - Duration: {duration:.3f}s")
        
        # Performance assertions for queries
        for query_name, result in query_results.items():
            assert result['success'], f"Query {query_name} failed: {result.get('error')}"
            assert result['duration'] < 10.0, f"Query {query_name} too slow: {result['duration']:.3f}s"
        
        return query_results
    
    @pytest.mark.asyncio
    async def test_file_size_growth_patterns(self, performance_db_manager):
        """Test SQLite file size growth patterns and identify limits."""
        growth_data = []
        
        # Test incremental data addition
        for batch_num in range(20):  # 20 batches
            batch_size = 2000
            pool_id = f"growth_test_pool_{batch_num}"
            
            # Get database size before
            db_url = str(performance_db_manager.connection.engine.url)
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
                size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            else:
                size_before = 0
            
            # Add batch of data
            test_data = generate_test_ohlcv_data(pool_id, "5m", batch_size)
            start_time = time.time()
            await performance_db_manager.store_ohlcv_data(test_data)
            write_duration = time.time() - start_time
            
            # Get database size after
            size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            size_growth = size_after - size_before
            
            growth_data.append({
                'batch_num': batch_num,
                'records_added': batch_size,
                'size_before_mb': size_before / (1024 * 1024),
                'size_after_mb': size_after / (1024 * 1024),
                'size_growth_mb': size_growth / (1024 * 1024),
                'write_duration': write_duration,
                'throughput': batch_size / write_duration
            })
        
        # Analyze growth patterns
        total_records = sum(d['records_added'] for d in growth_data)
        final_size_mb = growth_data[-1]['size_after_mb']
        avg_throughput = sum(d['throughput'] for d in growth_data) / len(growth_data)
        
        # Check for reasonable file size efficiency
        bytes_per_record = (final_size_mb * 1024 * 1024) / total_records
        assert bytes_per_record < 1000, f"Storage efficiency poor: {bytes_per_record:.2f} bytes/record"
        
        # Check for performance consistency
        throughput_variance = max(d['throughput'] for d in growth_data) / min(d['throughput'] for d in growth_data)
        assert throughput_variance < 3.0, f"Throughput too variable: {throughput_variance:.2f}x difference"
        
        logger.info(f"File Growth Analysis - Total records: {total_records:,}, "
                   f"Final size: {final_size_mb:.2f}MB, "
                   f"Bytes/record: {bytes_per_record:.2f}, "
                   f"Avg throughput: {avg_throughput:.2f} records/sec")
        
        return growth_data


class TestMemoryResourceMonitoring:
    """Test memory usage and resource consumption monitoring."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_high_volume_collection(self, performance_db_manager):
        """Monitor memory usage during high-volume data collection."""
        process = psutil.Process()
        memory_samples = []
        
        # Baseline memory usage
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        async def memory_monitor():
            """Background memory monitoring task."""
            while True:
                try:
                    memory_info = process.memory_info()
                    memory_samples.append({
                        'timestamp': time.time(),
                        'rss_mb': memory_info.rss / (1024 * 1024),
                        'vms_mb': memory_info.vms / (1024 * 1024)
                    })
                    await asyncio.sleep(0.5)  # Sample every 500ms
                except asyncio.CancelledError:
                    break
        
        # Start memory monitoring
        monitor_task = asyncio.create_task(memory_monitor())
        
        try:
            # Perform high-volume data collection
            total_records = 0
            
            for batch_num in range(10):  # 10 large batches
                batch_size = 5000
                pool_id = f"memory_test_pool_{batch_num}"
                
                # Generate and store OHLCV data
                ohlcv_data = generate_test_ohlcv_data(pool_id, "1m", batch_size)
                await performance_db_manager.store_ohlcv_data(ohlcv_data)
                
                # Generate and store trade data
                trade_data = generate_test_trade_data(pool_id, batch_size * 2)
                await performance_db_manager.store_trade_data(trade_data)
                
                total_records += len(ohlcv_data) + len(trade_data)
                
                # Force garbage collection periodically
                if batch_num % 3 == 0:
                    gc.collect()
                
                await asyncio.sleep(0.1)  # Brief pause between batches
        
        finally:
            # Stop memory monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # Analyze memory usage patterns
        if memory_samples:
            peak_memory = max(s['rss_mb'] for s in memory_samples)
            final_memory = memory_samples[-1]['rss_mb']
            memory_growth = peak_memory - baseline_memory
            
            # Check for memory leaks (final memory should be close to peak)
            memory_leak_indicator = (final_memory - baseline_memory) / memory_growth if memory_growth > 0 else 0
            
            # Performance assertions
            assert peak_memory < 500, f"Peak memory usage too high: {peak_memory:.2f}MB"
            assert memory_growth < 300, f"Memory growth too large: {memory_growth:.2f}MB"
            assert memory_leak_indicator > 0.7, f"Possible memory leak detected: {memory_leak_indicator:.2f}"
            
            logger.info(f"Memory Analysis - Baseline: {baseline_memory:.2f}MB, "
                       f"Peak: {peak_memory:.2f}MB, "
                       f"Growth: {memory_growth:.2f}MB, "
                       f"Final: {final_memory:.2f}MB, "
                       f"Records processed: {total_records:,}")
        
        return memory_samples
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_verification(self, performance_db_manager):
        """Verify proper resource cleanup after operations."""
        process = psutil.Process()
        
        # Baseline measurements
        baseline_memory = process.memory_info().rss / (1024 * 1024)
        baseline_open_files = len(process.open_files())
        
        # Perform intensive operations
        for i in range(5):
            pool_id = f"cleanup_test_pool_{i}"
            
            # Large data operations
            ohlcv_data = generate_test_ohlcv_data(pool_id, "1h", 10000)
            await performance_db_manager.store_ohlcv_data(ohlcv_data)
            
            trade_data = generate_test_trade_data(pool_id, 15000)
            await performance_db_manager.store_trade_data(trade_data)
            
            # Query operations
            await performance_db_manager.get_ohlcv_data(pool_id, "1h")
            await performance_db_manager.get_trade_data(pool_id)
        
        # Force cleanup
        gc.collect()
        await asyncio.sleep(1)  # Allow time for cleanup
        
        # Post-operation measurements
        final_memory = process.memory_info().rss / (1024 * 1024)
        final_open_files = len(process.open_files())
        
        memory_increase = final_memory - baseline_memory
        file_handle_increase = final_open_files - baseline_open_files
        
        # Resource cleanup assertions
        assert memory_increase < 100, f"Memory not properly cleaned up: {memory_increase:.2f}MB increase"
        assert file_handle_increase <= 2, f"File handles not cleaned up: {file_handle_increase} increase"
        
        logger.info(f"Resource Cleanup - Memory increase: {memory_increase:.2f}MB, "
                   f"File handle increase: {file_handle_increase}")
        
        return {
            'baseline_memory_mb': baseline_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': memory_increase,
            'baseline_open_files': baseline_open_files,
            'final_open_files': final_open_files,
            'file_handle_increase': file_handle_increase
        }


class TestAPIRateLimitCompliance:
    """Test API rate limit compliance and backoff behavior validation."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_backoff_behavior(self):
        """Test API rate limiting and exponential backoff behavior."""
        
        class MockAPIClient:
            """Mock API client that simulates rate limiting."""
            
            def __init__(self, rate_limit_per_minute=60):
                self.rate_limit = rate_limit_per_minute
                self.requests = []
                self.rate_limited_responses = 0
                
            async def make_request(self, endpoint: str) -> Dict:
                """Simulate API request with rate limiting."""
                current_time = time.time()
                self.requests.append(current_time)
                
                # Check rate limit (requests in last minute)
                recent_requests = [r for r in self.requests if current_time - r < 60]
                
                if len(recent_requests) > self.rate_limit:
                    self.rate_limited_responses += 1
                    raise Exception("Rate limit exceeded")
                
                # Simulate API response delay
                await asyncio.sleep(0.1)
                return {"status": "success", "data": []}
        
        class RateLimitedCollector:
            """Collector with rate limiting and backoff logic."""
            
            def __init__(self, api_client: MockAPIClient):
                self.api_client = api_client
                self.backoff_delays = []
                self.successful_requests = 0
                self.failed_requests = 0
                
            async def collect_with_backoff(self, endpoints: List[str]) -> Dict:
                """Collect data with exponential backoff on rate limits."""
                results = []
                
                for endpoint in endpoints:
                    max_retries = 5
                    base_delay = 1.0
                    
                    for attempt in range(max_retries):
                        try:
                            result = await self.api_client.make_request(endpoint)
                            results.append(result)
                            self.successful_requests += 1
                            break
                            
                        except Exception as e:
                            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                                # Exponential backoff
                                delay = base_delay * (2 ** attempt)
                                self.backoff_delays.append(delay)
                                
                                logger.debug(f"Rate limited, backing off for {delay:.2f}s")
                                await asyncio.sleep(delay)
                            else:
                                self.failed_requests += 1
                                break
                
                return {
                    'successful_requests': self.successful_requests,
                    'failed_requests': self.failed_requests,
                    'backoff_delays': self.backoff_delays,
                    'results': results
                }
        
        # Test rate limiting behavior
        api_client = MockAPIClient(rate_limit_per_minute=30)  # Strict rate limit
        collector = RateLimitedCollector(api_client)
        
        # Generate many endpoints to trigger rate limiting
        endpoints = [f"endpoint_{i}" for i in range(100)]
        
        start_time = time.time()
        results = await collector.collect_with_backoff(endpoints)
        duration = time.time() - start_time
        
        # Analyze rate limiting behavior
        success_rate = results['successful_requests'] / (results['successful_requests'] + results['failed_requests'])
        avg_backoff_delay = sum(results['backoff_delays']) / len(results['backoff_delays']) if results['backoff_delays'] else 0
        
        # Assertions for proper rate limiting
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2%}"
        assert len(results['backoff_delays']) > 0, "No backoff delays recorded - rate limiting not working"
        assert avg_backoff_delay > 1.0, f"Average backoff delay too short: {avg_backoff_delay:.2f}s"
        assert duration > 60, f"Collection completed too quickly, rate limiting bypassed: {duration:.2f}s"
        
        logger.info(f"Rate Limit Test - Success rate: {success_rate:.2%}, "
                   f"Backoff events: {len(results['backoff_delays'])}, "
                   f"Avg backoff: {avg_backoff_delay:.2f}s, "
                   f"Duration: {duration:.2f}s")
        
        return results
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_compliance(self):
        """Test rate limit compliance with multiple concurrent collectors."""
        
        class SharedRateLimitedAPI:
            """Shared API client with global rate limiting."""
            
            def __init__(self, global_rate_limit=100):
                self.global_rate_limit = global_rate_limit
                self.request_timestamps = []
                self.lock = asyncio.Lock()
                
            async def make_request(self, collector_id: int, endpoint: str) -> Dict:
                """Make API request with global rate limiting."""
                async with self.lock:
                    current_time = time.time()
                    
                    # Clean old requests (older than 1 minute)
                    self.request_timestamps = [
                        t for t in self.request_timestamps 
                        if current_time - t < 60
                    ]
                    
                    # Check global rate limit
                    if len(self.request_timestamps) >= self.global_rate_limit:
                        raise Exception("Global rate limit exceeded")
                    
                    self.request_timestamps.append(current_time)
                
                # Simulate API delay
                await asyncio.sleep(0.05)
                return {"collector_id": collector_id, "endpoint": endpoint, "data": []}
        
        async def concurrent_collector(collector_id: int, api_client: SharedRateLimitedAPI) -> Dict:
            """Individual collector that respects shared rate limits."""
            successful_requests = 0
            failed_requests = 0
            backoff_events = 0
            
            endpoints = [f"collector_{collector_id}_endpoint_{i}" for i in range(30)]
            
            for endpoint in endpoints:
                max_retries = 3
                base_delay = 0.5
                
                for attempt in range(max_retries):
                    try:
                        await api_client.make_request(collector_id, endpoint)
                        successful_requests += 1
                        break
                        
                    except Exception as e:
                        if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            backoff_events += 1
                            await asyncio.sleep(delay)
                        else:
                            failed_requests += 1
                            break
            
            return {
                'collector_id': collector_id,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'backoff_events': backoff_events
            }
        
        # Test with multiple concurrent collectors
        api_client = SharedRateLimitedAPI(global_rate_limit=80)
        num_collectors = 5
        
        start_time = time.time()
        tasks = [concurrent_collector(i, api_client) for i in range(num_collectors)]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        # Analyze concurrent rate limiting
        total_successful = sum(r['successful_requests'] for r in results)
        total_failed = sum(r['failed_requests'] for r in results)
        total_backoff_events = sum(r['backoff_events'] for r in results)
        
        overall_success_rate = total_successful / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0
        
        # Assertions for concurrent rate limiting
        assert overall_success_rate > 0.7, f"Concurrent success rate too low: {overall_success_rate:.2%}"
        assert total_backoff_events > 0, "No backoff events in concurrent scenario"
        assert duration > 30, f"Concurrent collection too fast: {duration:.2f}s"
        
        logger.info(f"Concurrent Rate Limit Test - {num_collectors} collectors, "
                   f"Success rate: {overall_success_rate:.2%}, "
                   f"Backoff events: {total_backoff_events}, "
                   f"Duration: {duration:.2f}s")
        
        return results


class TestPostgreSQLMigrationBenchmarks:
    """Create performance benchmarks for PostgreSQL migration decision points."""
    
    @pytest.mark.asyncio
    async def test_sqlite_performance_thresholds(self, performance_db_manager):
        """Establish SQLite performance thresholds that indicate PostgreSQL migration needs."""
        
        # Define performance threshold tests
        threshold_tests = [
            {
                'name': 'write_throughput_degradation',
                'description': 'Write throughput below acceptable levels',
                'test_func': self._test_write_throughput_threshold,
                'threshold': 100,  # records/sec
                'unit': 'records/sec'
            },
            {
                'name': 'query_response_time',
                'description': 'Query response time exceeds limits',
                'test_func': self._test_query_response_threshold,
                'threshold': 5.0,  # seconds
                'unit': 'seconds'
            },
            {
                'name': 'concurrent_user_limit',
                'description': 'Concurrent access performance degradation',
                'test_func': self._test_concurrent_access_threshold,
                'threshold': 3,  # concurrent users
                'unit': 'concurrent users'
            },
            {
                'name': 'database_size_limit',
                'description': 'Database file size approaching practical limits',
                'test_func': self._test_database_size_threshold,
                'threshold': 500,  # MB
                'unit': 'MB'
            }
        ]
        
        migration_indicators = {}
        
        for test in threshold_tests:
            try:
                result = await test['test_func'](performance_db_manager)
                
                migration_indicators[test['name']] = {
                    'description': test['description'],
                    'measured_value': result['value'],
                    'threshold': test['threshold'],
                    'unit': test['unit'],
                    'exceeds_threshold': result['value'] > test['threshold'] if 'response_time' in test['name'] or 'size' in test['name'] else result['value'] < test['threshold'],
                    'migration_recommended': result['value'] > test['threshold'] if 'response_time' in test['name'] or 'size' in test['name'] else result['value'] < test['threshold']
                }
                
            except Exception as e:
                migration_indicators[test['name']] = {
                    'description': test['description'],
                    'error': str(e),
                    'migration_recommended': True  # Error indicates potential issues
                }
        
        # Overall migration recommendation
        migration_recommended = any(
            indicator.get('migration_recommended', False) 
            for indicator in migration_indicators.values()
        )
        
        logger.info("PostgreSQL Migration Analysis:")
        for name, indicator in migration_indicators.items():
            if 'error' not in indicator:
                logger.info(f"  {indicator['description']}: {indicator['measured_value']} {indicator['unit']} "
                           f"(threshold: {indicator['threshold']} {indicator['unit']}) "
                           f"- {'MIGRATE' if indicator['migration_recommended'] else 'OK'}")
            else:
                logger.info(f"  {indicator['description']}: ERROR - {indicator['error']}")
        
        logger.info(f"Overall migration recommendation: {'YES' if migration_recommended else 'NO'}")
        
        return {
            'migration_recommended': migration_recommended,
            'indicators': migration_indicators
        }
    
    async def _test_write_throughput_threshold(self, db_manager) -> Dict:
        """Test write throughput threshold."""
        tester = DatabasePerformanceTester(db_manager)
        metrics = PerformanceMetrics()
        
        # Test with moderate load
        test_data = generate_test_ohlcv_data("threshold_test_pool", "1h", 5000)
        metrics.records_processed = len(test_data)
        
        tester.start_monitoring(metrics)
        try:
            await db_manager.store_ohlcv_data(test_data)
        finally:
            tester.stop_monitoring(metrics)
        
        return {'value': metrics.throughput}
    
    async def _test_query_response_threshold(self, db_manager) -> Dict:
        """Test query response time threshold."""
        # First populate with data
        test_data = generate_test_ohlcv_data("query_threshold_pool", "1h", 50000)
        await db_manager.store_ohlcv_data(test_data)
        
        # Test complex query
        start_time = time.time()
        await db_manager.get_ohlcv_data(
            "query_threshold_pool", "1h",
            start_time=datetime.utcnow() - timedelta(days=30)
        )
        query_duration = time.time() - start_time
        
        return {'value': query_duration}
    
    async def _test_concurrent_access_threshold(self, db_manager) -> Dict:
        """Test concurrent access threshold."""
        async def concurrent_operation(operation_id: int) -> float:
            """Single concurrent operation."""
            start_time = time.time()
            
            pool_id = f"concurrent_threshold_{operation_id}"
            test_data = generate_test_ohlcv_data(pool_id, "5m", 1000)
            await db_manager.store_ohlcv_data(test_data)
            
            return time.time() - start_time
        
        # Test increasing levels of concurrency
        max_successful_concurrent = 0
        
        for concurrent_level in range(1, 11):  # Test up to 10 concurrent operations
            try:
                start_time = time.time()
                tasks = [concurrent_operation(i) for i in range(concurrent_level)]
                durations = await asyncio.gather(*tasks)
                total_time = time.time() - start_time
                
                # Check if performance is acceptable
                avg_duration = sum(durations) / len(durations)
                if avg_duration < 10.0 and total_time < 30.0:  # Acceptable performance
                    max_successful_concurrent = concurrent_level
                else:
                    break
                    
            except Exception:
                break
        
        return {'value': max_successful_concurrent}
    
    async def _test_database_size_threshold(self, db_manager) -> Dict:
        """Test database size threshold."""
        # Add substantial data to test size limits
        for i in range(10):
            pool_id = f"size_test_pool_{i}"
            test_data = generate_test_ohlcv_data(pool_id, "1m", 10000)
            await db_manager.store_ohlcv_data(test_data)
        
        # Get database file size
        db_url = str(db_manager.connection.engine.url)
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            if os.path.exists(db_path):
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                return {'value': size_mb}
        
        return {'value': 0}
    
    @pytest.mark.asyncio
    async def test_sqlalchemy_abstraction_validation(self, performance_db_manager):
        """Validate SQLAlchemy abstraction layer for database migration scenarios."""
        
        # Test database-agnostic operations
        abstraction_tests = [
            {
                'name': 'connection_management',
                'description': 'Connection pooling and management',
                'test_func': self._test_connection_abstraction
            },
            {
                'name': 'transaction_handling',
                'description': 'Transaction management across databases',
                'test_func': self._test_transaction_abstraction
            },
            {
                'name': 'query_portability',
                'description': 'Query compatibility across database engines',
                'test_func': self._test_query_portability
            },
            {
                'name': 'data_type_compatibility',
                'description': 'Data type handling across databases',
                'test_func': self._test_data_type_compatibility
            }
        ]
        
        abstraction_results = {}
        
        for test in abstraction_tests:
            try:
                result = await test['test_func'](performance_db_manager)
                abstraction_results[test['name']] = {
                    'description': test['description'],
                    'success': result.get('success', True),
                    'details': result.get('details', {}),
                    'migration_ready': result.get('migration_ready', True)
                }
                
            except Exception as e:
                abstraction_results[test['name']] = {
                    'description': test['description'],
                    'success': False,
                    'error': str(e),
                    'migration_ready': False
                }
        
        # Overall abstraction readiness
        migration_ready = all(
            result.get('migration_ready', False) 
            for result in abstraction_results.values()
        )
        
        logger.info("SQLAlchemy Abstraction Validation:")
        for name, result in abstraction_results.items():
            status = "READY" if result.get('migration_ready', False) else "NOT READY"
            logger.info(f"  {result['description']}: {status}")
            if 'error' in result:
                logger.info(f"    Error: {result['error']}")
        
        return {
            'migration_ready': migration_ready,
            'test_results': abstraction_results
        }
    
    async def _test_connection_abstraction(self, db_manager) -> Dict:
        """Test connection management abstraction."""
        try:
            # Test connection health check
            health_check = db_manager.connection.health_check()
            
            # Test session management
            session = db_manager.connection.get_session()
            session.close()
            
            return {
                'success': True,
                'migration_ready': health_check,
                'details': {'health_check': health_check}
            }
            
        except Exception as e:
            return {
                'success': False,
                'migration_ready': False,
                'details': {'error': str(e)}
            }
    
    async def _test_transaction_abstraction(self, db_manager) -> Dict:
        """Test transaction handling abstraction."""
        try:
            # Test transaction rollback
            test_data = generate_test_ohlcv_data("transaction_test", "1h", 100)
            
            # This should work regardless of database backend
            stored_count = await db_manager.store_ohlcv_data(test_data)
            
            return {
                'success': stored_count == 100,
                'migration_ready': True,
                'details': {'stored_count': stored_count}
            }
            
        except Exception as e:
            return {
                'success': False,
                'migration_ready': False,
                'details': {'error': str(e)}
            }
    
    async def _test_query_portability(self, db_manager) -> Dict:
        """Test query portability across database engines."""
        try:
            # Test standard SQLAlchemy queries that should work on any backend
            pool_id = "portability_test"
            test_data = generate_test_ohlcv_data(pool_id, "1h", 500)
            await db_manager.store_ohlcv_data(test_data)
            
            # Test various query patterns
            recent_data = await db_manager.get_ohlcv_data(
                pool_id, "1h", 
                start_time=datetime.utcnow() - timedelta(hours=24)
            )
            
            gaps = await db_manager.get_data_gaps(
                pool_id, "1h",
                datetime.utcnow() - timedelta(hours=48),
                datetime.utcnow()
            )
            
            return {
                'success': True,
                'migration_ready': True,
                'details': {
                    'recent_data_count': len(recent_data),
                    'gaps_found': len(gaps)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'migration_ready': False,
                'details': {'error': str(e)}
            }
    
    async def _test_data_type_compatibility(self, db_manager) -> Dict:
        """Test data type handling across database engines."""
        try:
            # Test with edge case data types and values
            pool_id = "data_type_test"
            
            # Create record with edge case values
            edge_case_record = OHLCVRecord(
                pool_id=pool_id,
                timeframe="1h",
                timestamp=int(datetime.utcnow().timestamp()),
                open_price=Decimal('0.000000000000000001'),  # Very small decimal
                high_price=Decimal('999999999999.999999999'),  # Very large decimal
                low_price=Decimal('0.000000000000000001'),
                close_price=Decimal('123.456789012345678901'),  # High precision
                volume_usd=Decimal('0'),  # Zero volume
                datetime=datetime.utcnow()
            )
            
            stored_count = await db_manager.store_ohlcv_data([edge_case_record])
            retrieved_data = await db_manager.get_ohlcv_data(pool_id, "1h")
            
            return {
                'success': stored_count == 1 and len(retrieved_data) == 1,
                'migration_ready': True,
                'details': {
                    'stored_count': stored_count,
                    'retrieved_count': len(retrieved_data)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'migration_ready': False,
                'details': {'error': str(e)}
            }


# Integration test that combines multiple performance aspects
@pytest.mark.asyncio
async def test_comprehensive_performance_suite(performance_db_manager):
    """Comprehensive performance test combining all aspects."""
    
    logger.info("Starting comprehensive performance test suite...")
    
    # Initialize performance tracking
    suite_start_time = time.time()
    suite_metrics = {
        'total_records_processed': 0,
        'total_operations': 0,
        'peak_memory_mb': 0,
        'test_results': {}
    }
    
    process = psutil.Process()
    baseline_memory = process.memory_info().rss / (1024 * 1024)
    
    try:
        # 1. Baseline performance tests
        logger.info("Running baseline performance tests...")
        tester = DatabasePerformanceTester(performance_db_manager)
        
        # OHLCV baseline
        ohlcv_metrics = PerformanceMetrics()
        ohlcv_data = generate_test_ohlcv_data("comprehensive_ohlcv", "1h", 2000)
        ohlcv_metrics.records_processed = len(ohlcv_data)
        
        tester.start_monitoring(ohlcv_metrics)
        await performance_db_manager.store_ohlcv_data(ohlcv_data)
        tester.stop_monitoring(ohlcv_metrics)
        
        suite_metrics['test_results']['ohlcv_baseline'] = {
            'throughput': ohlcv_metrics.throughput,
            'duration': ohlcv_metrics.duration,
            'memory_mb': ohlcv_metrics.memory_usage_mb
        }
        
        # Trade baseline
        trade_metrics = PerformanceMetrics()
        trade_data = generate_test_trade_data("comprehensive_trades", 3000)
        trade_metrics.records_processed = len(trade_data)
        
        tester.start_monitoring(trade_metrics)
        await performance_db_manager.store_trade_data(trade_data)
        tester.stop_monitoring(trade_metrics)
        
        suite_metrics['test_results']['trade_baseline'] = {
            'throughput': trade_metrics.throughput,
            'duration': trade_metrics.duration,
            'memory_mb': trade_metrics.memory_usage_mb
        }
        
        # 2. Concurrent operations test
        logger.info("Running concurrent operations test...")
        
        async def concurrent_mixed_operation(op_id: int) -> Dict:
            """Mixed OHLCV and trade operations."""
            pool_id = f"comprehensive_concurrent_{op_id}"
            
            # OHLCV data
            ohlcv_data = generate_test_ohlcv_data(pool_id, "5m", 1000)
            await performance_db_manager.store_ohlcv_data(ohlcv_data)
            
            # Trade data
            trade_data = generate_test_trade_data(pool_id, 1500)
            await performance_db_manager.store_trade_data(trade_data)
            
            return {
                'ohlcv_records': len(ohlcv_data),
                'trade_records': len(trade_data)
            }
        
        concurrent_start = time.time()
        concurrent_tasks = [concurrent_mixed_operation(i) for i in range(3)]
        concurrent_results = await asyncio.gather(*concurrent_tasks)
        concurrent_duration = time.time() - concurrent_start
        
        total_concurrent_records = sum(
            r['ohlcv_records'] + r['trade_records'] 
            for r in concurrent_results
        )
        
        suite_metrics['test_results']['concurrent_operations'] = {
            'total_records': total_concurrent_records,
            'duration': concurrent_duration,
            'throughput': total_concurrent_records / concurrent_duration
        }
        
        # 3. Query performance test
        logger.info("Running query performance test...")
        
        query_start = time.time()
        
        # Complex queries
        recent_ohlcv = await performance_db_manager.get_ohlcv_data(
            "comprehensive_ohlcv", "1h",
            start_time=datetime.utcnow() - timedelta(hours=24)
        )
        
        recent_trades = await performance_db_manager.get_trade_data(
            "comprehensive_trades",
            start_time=datetime.utcnow() - timedelta(hours=12)
        )
        
        gaps = await performance_db_manager.get_data_gaps(
            "comprehensive_ohlcv", "1h",
            datetime.utcnow() - timedelta(hours=48),
            datetime.utcnow()
        )
        
        query_duration = time.time() - query_start
        
        suite_metrics['test_results']['query_performance'] = {
            'ohlcv_results': len(recent_ohlcv),
            'trade_results': len(recent_trades),
            'gaps_found': len(gaps),
            'total_duration': query_duration
        }
        
        # Update suite totals
        suite_metrics['total_records_processed'] = (
            ohlcv_metrics.records_processed + 
            trade_metrics.records_processed + 
            total_concurrent_records
        )
        suite_metrics['total_operations'] = 6  # Number of major operations
        
        # Final memory check
        final_memory = process.memory_info().rss / (1024 * 1024)
        suite_metrics['peak_memory_mb'] = final_memory - baseline_memory
        
    finally:
        suite_duration = time.time() - suite_start_time
        suite_metrics['total_duration'] = suite_duration
    
    # Performance assertions for the comprehensive suite
    assert suite_metrics['total_records_processed'] > 10000, "Insufficient test data processed"
    assert suite_metrics['peak_memory_mb'] < 300, f"Memory usage too high: {suite_metrics['peak_memory_mb']:.2f}MB"
    assert suite_duration < 120, f"Suite took too long: {suite_duration:.2f}s"
    
    # Log comprehensive results
    logger.info("Comprehensive Performance Suite Results:")
    logger.info(f"  Total records processed: {suite_metrics['total_records_processed']:,}")
    logger.info(f"  Total duration: {suite_duration:.2f}s")
    logger.info(f"  Overall throughput: {suite_metrics['total_records_processed']/suite_duration:.2f} records/sec")
    logger.info(f"  Peak memory usage: {suite_metrics['peak_memory_mb']:.2f}MB")
    
    for test_name, results in suite_metrics['test_results'].items():
        logger.info(f"  {test_name}: {results}")
    
    return suite_metrics