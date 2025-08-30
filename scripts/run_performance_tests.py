#!/usr/bin/env python3
"""
Performance test runner script for GeckoTerminal collector system.

This script provides a command-line interface for running performance
and load tests with various configurations and reporting options.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from tests.performance_config import get_performance_config, create_custom_config
from tests.test_performance_load import (
    TestSQLitePerformanceBaseline,
    TestConcurrentCollectionScenarios,
    TestDatabaseScalabilityLimits,
    TestMemoryResourceMonitoring,
    TestAPIRateLimitCompliance,
    TestPostgreSQLMigrationBenchmarks,
    test_comprehensive_performance_suite
)

logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """Performance test runner with reporting capabilities."""
    
    def __init__(self, config_overrides: Optional[Dict] = None):
        """Initialize the test runner."""
        self.config = create_custom_config(**(config_overrides or {}))
        self.results = {}
        self.start_time = None
        self.end_time = None
        
    async def setup_test_database(self) -> SQLAlchemyDatabaseManager:
        """Set up a temporary test database."""
        temp_dir = tempfile.mkdtemp(prefix="gecko_perf_test_")
        db_path = os.path.join(temp_dir, "performance_test.db")
        
        db_config = DatabaseConfig(
            url=f"sqlite:///{db_path}",
            pool_size=self.config.test_database_settings['connection_pool_settings']['pool_size'],
            max_overflow=self.config.test_database_settings['connection_pool_settings']['max_overflow'],
            echo=False
        )
        
        db_manager = SQLAlchemyDatabaseManager(db_config)
        await db_manager.initialize()
        
        logger.info(f"Test database created at: {db_path}")
        return db_manager
    
    async def run_baseline_tests(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run baseline performance tests."""
        logger.info("Running baseline performance tests...")
        
        baseline_tester = TestSQLitePerformanceBaseline()
        results = {}
        
        try:
            # OHLCV write throughput test
            logger.info("Testing OHLCV write throughput...")
            await baseline_tester.test_ohlcv_write_throughput_baseline(db_manager)
            results['ohlcv_throughput'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"OHLCV throughput test failed: {e}")
            results['ohlcv_throughput'] = f'FAILED: {e}'
        
        try:
            # Trade write throughput test
            logger.info("Testing trade write throughput...")
            await baseline_tester.test_trade_write_throughput_baseline(db_manager)
            results['trade_throughput'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"Trade throughput test failed: {e}")
            results['trade_throughput'] = f'FAILED: {e}'
        
        try:
            # Batch size optimization test
            logger.info("Testing batch size optimization...")
            await baseline_tester.test_batch_size_optimization(db_manager)
            results['batch_optimization'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"Batch optimization test failed: {e}")
            results['batch_optimization'] = f'FAILED: {e}'
        
        return results
    
    async def run_concurrency_tests(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run concurrency and contention tests."""
        logger.info("Running concurrency tests...")
        
        concurrency_tester = TestConcurrentCollectionScenarios()
        results = {}
        
        try:
            # Concurrent OHLCV collectors test
            logger.info("Testing concurrent OHLCV collectors...")
            await concurrency_tester.test_concurrent_ohlcv_collectors(db_manager)
            results['concurrent_ohlcv'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"Concurrent OHLCV test failed: {e}")
            results['concurrent_ohlcv'] = f'FAILED: {e}'
        
        try:
            # Mixed data type concurrency test
            logger.info("Testing mixed data type concurrency...")
            await concurrency_tester.test_mixed_data_type_concurrency(db_manager)
            results['mixed_concurrency'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"Mixed concurrency test failed: {e}")
            results['mixed_concurrency'] = f'FAILED: {e}'
        
        try:
            # Database contention measurement
            logger.info("Testing database contention...")
            await concurrency_tester.test_database_contention_measurement(db_manager)
            results['database_contention'] = 'PASSED'
            
        except Exception as e:
            logger.error(f"Database contention test failed: {e}")
            results['database_contention'] = f'FAILED: {e}'
        
        return results
    
    async def run_scalability_tests(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run scalability and limits tests."""
        logger.info("Running scalability tests...")
        
        scalability_tester = TestDatabaseScalabilityLimits()
        results = {}
        
        try:
            # Data volume limits test
            logger.info("Testing data volume limits...")
            volume_results = await scalability_tester.test_data_volume_limits(db_manager)
            results['data_volume_limits'] = 'PASSED'
            results['volume_details'] = volume_results
            
        except Exception as e:
            logger.error(f"Data volume limits test failed: {e}")
            results['data_volume_limits'] = f'FAILED: {e}'
        
        try:
            # Query performance scaling test
            logger.info("Testing query performance scaling...")
            query_results = await scalability_tester.test_query_performance_scaling(db_manager)
            results['query_performance_scaling'] = 'PASSED'
            results['query_details'] = query_results
            
        except Exception as e:
            logger.error(f"Query performance scaling test failed: {e}")
            results['query_performance_scaling'] = f'FAILED: {e}'
        
        try:
            # File size growth patterns test
            logger.info("Testing file size growth patterns...")
            growth_results = await scalability_tester.test_file_size_growth_patterns(db_manager)
            results['file_size_growth'] = 'PASSED'
            results['growth_details'] = growth_results
            
        except Exception as e:
            logger.error(f"File size growth test failed: {e}")
            results['file_size_growth'] = f'FAILED: {e}'
        
        return results
    
    async def run_memory_tests(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run memory and resource monitoring tests."""
        logger.info("Running memory and resource tests...")
        
        memory_tester = TestMemoryResourceMonitoring()
        results = {}
        
        try:
            # Memory usage during high-volume collection
            logger.info("Testing memory usage during high-volume collection...")
            memory_samples = await memory_tester.test_memory_usage_during_high_volume_collection(db_manager)
            results['memory_usage_high_volume'] = 'PASSED'
            results['memory_samples_count'] = len(memory_samples)
            
        except Exception as e:
            logger.error(f"Memory usage test failed: {e}")
            results['memory_usage_high_volume'] = f'FAILED: {e}'
        
        try:
            # Resource cleanup verification
            logger.info("Testing resource cleanup...")
            cleanup_results = await memory_tester.test_resource_cleanup_verification(db_manager)
            results['resource_cleanup'] = 'PASSED'
            results['cleanup_details'] = cleanup_results
            
        except Exception as e:
            logger.error(f"Resource cleanup test failed: {e}")
            results['resource_cleanup'] = f'FAILED: {e}'
        
        return results
    
    async def run_rate_limit_tests(self) -> Dict:
        """Run API rate limit compliance tests."""
        logger.info("Running API rate limit tests...")
        
        rate_limit_tester = TestAPIRateLimitCompliance()
        results = {}
        
        try:
            # Rate limit backoff behavior test
            logger.info("Testing rate limit backoff behavior...")
            backoff_results = await rate_limit_tester.test_rate_limit_backoff_behavior()
            results['rate_limit_backoff'] = 'PASSED'
            results['backoff_details'] = {
                'successful_requests': backoff_results['successful_requests'],
                'failed_requests': backoff_results['failed_requests'],
                'backoff_events': len(backoff_results['backoff_delays'])
            }
            
        except Exception as e:
            logger.error(f"Rate limit backoff test failed: {e}")
            results['rate_limit_backoff'] = f'FAILED: {e}'
        
        try:
            # Concurrent rate limit compliance test
            logger.info("Testing concurrent rate limit compliance...")
            concurrent_results = await rate_limit_tester.test_concurrent_rate_limit_compliance()
            results['concurrent_rate_limit'] = 'PASSED'
            results['concurrent_details'] = {
                'collectors': len(concurrent_results),
                'total_successful': sum(r['successful_requests'] for r in concurrent_results),
                'total_backoff_events': sum(r['backoff_events'] for r in concurrent_results)
            }
            
        except Exception as e:
            logger.error(f"Concurrent rate limit test failed: {e}")
            results['concurrent_rate_limit'] = f'FAILED: {e}'
        
        return results
    
    async def run_migration_benchmark_tests(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run PostgreSQL migration benchmark tests."""
        logger.info("Running PostgreSQL migration benchmark tests...")
        
        migration_tester = TestPostgreSQLMigrationBenchmarks()
        results = {}
        
        try:
            # SQLite performance thresholds test
            logger.info("Testing SQLite performance thresholds...")
            threshold_results = await migration_tester.test_sqlite_performance_thresholds(db_manager)
            results['performance_thresholds'] = 'PASSED'
            results['migration_recommended'] = threshold_results['migration_recommended']
            results['threshold_details'] = threshold_results['indicators']
            
        except Exception as e:
            logger.error(f"Performance thresholds test failed: {e}")
            results['performance_thresholds'] = f'FAILED: {e}'
        
        try:
            # SQLAlchemy abstraction validation test
            logger.info("Testing SQLAlchemy abstraction validation...")
            abstraction_results = await migration_tester.test_sqlalchemy_abstraction_validation(db_manager)
            results['abstraction_validation'] = 'PASSED'
            results['migration_ready'] = abstraction_results['migration_ready']
            results['abstraction_details'] = abstraction_results['test_results']
            
        except Exception as e:
            logger.error(f"Abstraction validation test failed: {e}")
            results['abstraction_validation'] = f'FAILED: {e}'
        
        return results
    
    async def run_comprehensive_suite(self, db_manager: SQLAlchemyDatabaseManager) -> Dict:
        """Run the comprehensive performance test suite."""
        logger.info("Running comprehensive performance suite...")
        
        try:
            suite_results = await test_comprehensive_performance_suite(db_manager)
            return {
                'comprehensive_suite': 'PASSED',
                'suite_details': suite_results
            }
            
        except Exception as e:
            logger.error(f"Comprehensive suite failed: {e}")
            return {
                'comprehensive_suite': f'FAILED: {e}'
            }
    
    async def run_all_tests(self, test_categories: Optional[List[str]] = None) -> Dict:
        """Run all performance tests or specified categories."""
        self.start_time = datetime.utcnow()
        
        # Set up test database
        db_manager = await self.setup_test_database()
        
        try:
            all_categories = [
                'baseline', 'concurrency', 'scalability', 
                'memory', 'rate_limit', 'migration', 'comprehensive'
            ]
            
            categories_to_run = test_categories or all_categories
            
            for category in categories_to_run:
                if category == 'baseline':
                    self.results['baseline'] = await self.run_baseline_tests(db_manager)
                elif category == 'concurrency':
                    self.results['concurrency'] = await self.run_concurrency_tests(db_manager)
                elif category == 'scalability':
                    self.results['scalability'] = await self.run_scalability_tests(db_manager)
                elif category == 'memory':
                    self.results['memory'] = await self.run_memory_tests(db_manager)
                elif category == 'rate_limit':
                    self.results['rate_limit'] = await self.run_rate_limit_tests()
                elif category == 'migration':
                    self.results['migration'] = await self.run_migration_benchmark_tests(db_manager)
                elif category == 'comprehensive':
                    self.results['comprehensive'] = await self.run_comprehensive_suite(db_manager)
        
        finally:
            await db_manager.close()
            self.end_time = datetime.utcnow()
        
        return self.results
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a performance test report."""
        if not self.results:
            return "No test results available."
        
        report_lines = [
            "=" * 80,
            "GECKO TERMINAL COLLECTOR - PERFORMANCE TEST REPORT",
            "=" * 80,
            f"Test Start Time: {self.start_time}",
            f"Test End Time: {self.end_time}",
            f"Total Duration: {(self.end_time - self.start_time).total_seconds():.2f} seconds",
            "",
        ]
        
        # Summary section
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.results.items():
            if isinstance(tests, dict):
                for test_name, result in tests.items():
                    if not test_name.endswith('_details'):
                        total_tests += 1
                        if result == 'PASSED':
                            passed_tests += 1
        
        report_lines.extend([
            "SUMMARY",
            "-" * 40,
            f"Total Tests: {total_tests}",
            f"Passed: {passed_tests}",
            f"Failed: {total_tests - passed_tests}",
            f"Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "N/A",
            "",
        ])
        
        # Detailed results
        report_lines.append("DETAILED RESULTS")
        report_lines.append("-" * 40)
        
        for category, tests in self.results.items():
            report_lines.append(f"\n{category.upper()} TESTS:")
            
            if isinstance(tests, dict):
                for test_name, result in tests.items():
                    if not test_name.endswith('_details'):
                        status = "PASS" if result == 'PASSED' else "FAIL"
                        report_lines.append(f"  [{status}] {test_name}: {result}")
            else:
                status = "PASS" if tests == 'PASSED' else "FAIL"
                report_lines.append(f"  [{status}] {category}: {tests}")
        
        # Migration recommendations
        if 'migration' in self.results:
            migration_data = self.results['migration']
            if 'migration_recommended' in migration_data:
                report_lines.extend([
                    "",
                    "POSTGRESQL MIGRATION RECOMMENDATION",
                    "-" * 40,
                    f"Migration Recommended: {'YES' if migration_data['migration_recommended'] else 'NO'}",
                ])
                
                if 'threshold_details' in migration_data:
                    for indicator, details in migration_data['threshold_details'].items():
                        if 'migration_recommended' in details:
                            status = "MIGRATE" if details['migration_recommended'] else "OK"
                            report_lines.append(f"  {indicator}: {status}")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"Performance report saved to: {output_file}")
        
        return report_content


async def main():
    """Main entry point for the performance test runner."""
    parser = argparse.ArgumentParser(description="Run GeckoTerminal collector performance tests")
    
    parser.add_argument(
        '--categories', 
        nargs='+', 
        choices=['baseline', 'concurrency', 'scalability', 'memory', 'rate_limit', 'migration', 'comprehensive'],
        help='Test categories to run (default: all)'
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        help='Output file for test report'
    )
    
    parser.add_argument(
        '--json-output', 
        type=str, 
        help='Output file for JSON results'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true', 
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    runner = PerformanceTestRunner()
    
    try:
        results = await runner.run_all_tests(args.categories)
        
        # Generate and display report
        report = runner.generate_report(args.output)
        print(report)
        
        # Save JSON results if requested
        if args.json_output:
            with open(args.json_output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"JSON results saved to: {args.json_output}")
        
        # Exit with appropriate code
        total_tests = sum(
            len([k for k in v.keys() if not k.endswith('_details')]) if isinstance(v, dict) else 1
            for v in results.values()
        )
        
        passed_tests = sum(
            len([k for k, r in v.items() if not k.endswith('_details') and r == 'PASSED']) if isinstance(v, dict) 
            else (1 if v == 'PASSED' else 0)
            for v in results.values()
        )
        
        if passed_tests == total_tests:
            logger.info("All performance tests passed!")
            sys.exit(0)
        else:
            logger.error(f"Some performance tests failed: {passed_tests}/{total_tests} passed")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Performance test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())