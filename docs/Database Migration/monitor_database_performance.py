#!/usr/bin/env python3
"""
Monitor database performance and lock optimization effectiveness.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabasePerformanceMonitor:
    """Monitor database performance and optimization effectiveness."""
    
    def __init__(self, db_path: str):
        """Initialize the performance monitor."""
        self.db_path = db_path
        self.config = DatabaseConfig(
            url=f"sqlite:///{db_path}",
            echo=False
        )
        self.db_manager = None
        self.monitoring_active = False
        
    async def initialize(self):
        """Initialize the database manager."""
        self.db_manager = SQLAlchemyDatabaseManager(self.config)
        await self.db_manager.initialize()
        
    async def close(self):
        """Close the database manager."""
        if self.db_manager:
            await self.db_manager.close()
    
    async def get_performance_snapshot(self) -> Dict[str, Any]:
        """Get a comprehensive performance snapshot."""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'health_metrics': {},
            'table_stats': {},
            'performance_tests': {}
        }
        
        try:
            # Get health metrics
            snapshot['health_metrics'] = await self.db_manager.get_database_health_metrics()
            
            # Get table statistics
            tables = ['pools', 'trades', 'ohlcv_data', 'tokens', 'watchlist']
            for table in tables:
                count = await self.db_manager.count_records(table)
                snapshot['table_stats'][table] = count
            
            # Performance tests
            snapshot['performance_tests'] = await self._run_performance_tests()
            
        except Exception as e:
            logger.error(f"Error getting performance snapshot: {e}")
            snapshot['error'] = str(e)
        
        return snapshot
    
    async def _run_performance_tests(self) -> Dict[str, Any]:
        """Run basic performance tests."""
        tests = {}
        
        try:
            # Test simple query performance
            start_time = time.time()
            with self.db_manager.optimized_session(read_only=True) as session:
                session.execute(text("SELECT COUNT(*) FROM pools")).fetchone()
            tests['simple_query_ms'] = (time.time() - start_time) * 1000
            
            # Test concurrent read performance
            start_time = time.time()
            tasks = []
            for _ in range(5):
                tasks.append(self._concurrent_read_test())
            
            await asyncio.gather(*tasks)
            tests['concurrent_reads_ms'] = (time.time() - start_time) * 1000
            
        except Exception as e:
            tests['error'] = str(e)
        
        return tests
    
    async def _concurrent_read_test(self):
        """Perform a concurrent read test."""
        with self.db_manager.optimized_session(read_only=True) as session:
            session.execute(text("SELECT COUNT(*) FROM trades LIMIT 1")).fetchone()
    
    async def monitor_continuous(self, duration_minutes: int = 60, interval_seconds: int = 30):
        """Monitor database performance continuously."""
        logger.info(f"Starting continuous monitoring for {duration_minutes} minutes")
        
        self.monitoring_active = True
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        snapshots = []
        
        try:
            while datetime.now() < end_time and self.monitoring_active:
                snapshot = await self.get_performance_snapshot()
                snapshots.append(snapshot)
                
                # Log key metrics
                health = snapshot.get('health_metrics', {})
                logger.info(
                    f"Performance: Query latency: {health.get('query_latency_ms', 0):.2f}ms, "
                    f"Status: {health.get('optimization_status', 'unknown')}, "
                    f"WAL: {health.get('wal_mode_enabled', False)}"
                )
                
                await asyncio.sleep(interval_seconds)
            
            # Generate summary report
            await self._generate_monitoring_report(snapshots)
            
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
        finally:
            self.monitoring_active = False
    
    async def _generate_monitoring_report(self, snapshots: list):
        """Generate a monitoring report from collected snapshots."""
        if not snapshots:
            logger.warning("No snapshots collected for report")
            return
        
        logger.info("\n=== Database Performance Monitoring Report ===")
        
        # Calculate averages and trends
        query_latencies = []
        lock_contentions = 0
        
        for snapshot in snapshots:
            health = snapshot.get('health_metrics', {})
            
            if 'query_latency_ms' in health:
                query_latencies.append(health['query_latency_ms'])
            
            if health.get('lock_contention_detected', False):
                lock_contentions += 1
        
        if query_latencies:
            avg_latency = sum(query_latencies) / len(query_latencies)
            max_latency = max(query_latencies)
            min_latency = min(query_latencies)
            
            logger.info(f"Query Latency - Avg: {avg_latency:.2f}ms, Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms")
        
        logger.info(f"Lock Contention Events: {lock_contentions}/{len(snapshots)} snapshots")
        
        # Optimization status
        last_snapshot = snapshots[-1]
        health = last_snapshot.get('health_metrics', {})
        
        logger.info(f"Final Optimization Status: {health.get('optimization_status', 'unknown')}")
        logger.info(f"WAL Mode Enabled: {health.get('wal_mode_enabled', False)}")
        logger.info(f"Busy Timeout: {health.get('busy_timeout_ms', 0)}ms")
        
        # Table growth
        first_stats = snapshots[0].get('table_stats', {})
        last_stats = last_snapshot.get('table_stats', {})
        
        logger.info("\nTable Growth During Monitoring:")
        for table in ['pools', 'trades', 'ohlcv_data']:
            first_count = first_stats.get(table, 0)
            last_count = last_stats.get(table, 0)
            growth = last_count - first_count
            
            if growth > 0:
                logger.info(f"  {table}: +{growth} records ({first_count} -> {last_count})")
            else:
                logger.info(f"  {table}: {last_count} records (no change)")
        
        logger.info("=== End of Report ===\n")
    
    async def benchmark_optimization_impact(self):
        """Benchmark the impact of optimizations by comparing with/without."""
        logger.info("Running optimization impact benchmark...")
        
        # Get current performance
        logger.info("Testing current (optimized) performance...")
        optimized_snapshot = await self.get_performance_snapshot()
        
        # Temporarily disable optimizations for comparison
        logger.info("Testing performance without optimizations...")
        
        try:
            # Create a temporary database manager without optimizations
            temp_config = DatabaseConfig(
                url=f"sqlite:///{self.db_path}",
                echo=False
            )
            
            temp_manager = SQLAlchemyDatabaseManager(temp_config)
            # Skip the optimization application
            temp_manager._apply_sqlite_optimizations = lambda: None
            
            await temp_manager.initialize()
            
            # Run performance test without optimizations
            start_time = time.time()
            with temp_manager.connection.get_session() as session:
                session.execute(text("SELECT COUNT(*) FROM pools")).fetchone()
            unoptimized_latency = (time.time() - start_time) * 1000
            
            await temp_manager.close()
            
            # Compare results
            optimized_latency = optimized_snapshot['health_metrics'].get('query_latency_ms', 0)
            
            if unoptimized_latency > 0 and optimized_latency > 0:
                improvement = ((unoptimized_latency - optimized_latency) / unoptimized_latency) * 100
                logger.info(f"Performance Improvement: {improvement:.1f}%")
                logger.info(f"  Unoptimized: {unoptimized_latency:.2f}ms")
                logger.info(f"  Optimized: {optimized_latency:.2f}ms")
            else:
                logger.warning("Could not calculate performance improvement")
                
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")


async def main():
    """Main monitoring function."""
    import sys
    
    logger.info("=== Database Performance Monitor ===")
    
    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "gecko_data.db"  # Default path
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        logger.info("Usage: python monitor_database_performance.py [database_path]")
        sys.exit(1)
    
    monitor = DatabasePerformanceMonitor(db_path)
    
    try:
        await monitor.initialize()
        
        # Get initial snapshot
        logger.info("Getting initial performance snapshot...")
        snapshot = await monitor.get_performance_snapshot()
        
        logger.info("Current Database Status:")
        health = snapshot.get('health_metrics', {})
        for key, value in health.items():
            logger.info(f"  {key}: {value}")
        
        # Ask user what to do
        print("\nMonitoring Options:")
        print("1. Single snapshot (default)")
        print("2. Continuous monitoring (60 minutes)")
        print("3. Benchmark optimization impact")
        print("4. Custom continuous monitoring")
        
        try:
            choice = input("Enter choice (1-4): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
        
        if choice == "2":
            await monitor.monitor_continuous(duration_minutes=60)
        elif choice == "3":
            await monitor.benchmark_optimization_impact()
        elif choice == "4":
            try:
                duration = int(input("Duration in minutes: "))
                interval = int(input("Interval in seconds: "))
                await monitor.monitor_continuous(duration_minutes=duration, interval_seconds=interval)
            except (ValueError, EOFError, KeyboardInterrupt):
                logger.info("Using default values: 30 minutes, 30 second intervals")
                await monitor.monitor_continuous(duration_minutes=30, interval_seconds=30)
        else:
            logger.info("Single snapshot completed")
        
    finally:
        await monitor.close()


if __name__ == "__main__":
    import os
    from sqlalchemy import text
    asyncio.run(main())