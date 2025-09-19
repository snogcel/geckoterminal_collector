#!/usr/bin/env python3
"""
Test runner for OHLCV and Trade data QLib integration
Runs all test suites and provides comprehensive reporting
"""

import asyncio
import subprocess
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'ohlcv_trade_tests_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class OHLCVTradeTestRunner:
    """Test runner for OHLCV/Trade QLib integration tests"""
    
    def __init__(self):
        self.test_files = [
            'test_ohlcv_trade_schema.py',
            'test_qlib_ohlcv_trade_export.py', 
            'test_complete_ohlcv_trade_pipeline.py'
        ]
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_test_file(self, test_file):
        """Run a single test file and capture results"""
        logger.info(f"Running {test_file}...")  # Remove emoji to avoid encoding issues
        
        start_time = time.time()
        
        try:
            # Run the test file
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"PASSED: {test_file} ({duration:.2f}s)")
                status = "PASSED"
                error_message = None
            else:
                logger.error(f"FAILED: {test_file} ({duration:.2f}s)")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                status = "FAILED"
                error_message = result.stderr
            
            return {
                'status': status,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'error_message': error_message
            }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error(f"TIMEOUT: {test_file} ({duration:.2f}s)")
            return {
                'status': 'TIMEOUT',
                'duration': duration,
                'stdout': '',
                'stderr': 'Test timed out after 5 minutes',
                'error_message': 'Timeout'
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"ERROR: {test_file} ({duration:.2f}s): {e}")
            return {
                'status': 'ERROR',
                'duration': duration,
                'stdout': '',
                'stderr': str(e),
                'error_message': str(e)
            }
    
    def check_prerequisites(self):
        """Check if all test files exist and prerequisites are met"""
        logger.info("CHECK: Checking prerequisites...")
        
        missing_files = []
        for test_file in self.test_files:
            if not Path(test_file).exists():
                missing_files.append(test_file)
        
        if missing_files:
            logger.error(f"FAIL: Missing test files: {missing_files}")
            return False
        
        # Check if we can import required modules
        try:
            import asyncpg
            import pytest
            logger.info("PASS: Required modules available")
        except ImportError as e:
            logger.error(f"FAIL: Missing required module: {e}")
            return False
        
        logger.info("PASS: Prerequisites check passed")
        return True
    
    def run_all_tests(self):
        """Run all OHLCV/Trade integration tests"""
        logger.info("START: Starting OHLCV/Trade QLib Integration Test Suite")
        
        if not self.check_prerequisites():
            return False
        
        self.start_time = time.time()
        
        # Run each test file
        for test_file in self.test_files:
            self.results[test_file] = self.run_test_file(test_file)
        
        self.end_time = time.time()
        
        # Generate summary report
        self.generate_summary_report()
        
        # Return overall success
        return all(result['status'] == 'PASSED' for result in self.results.values())
    
    def generate_summary_report(self):
        """Generate comprehensive test summary report"""
        total_duration = self.end_time - self.start_time
        
        logger.info("=" * 80)
        logger.info("STATS: OHLCV/TRADE QLIB INTEGRATION TEST SUMMARY")
        logger.info("=" * 80)
        
        passed_tests = []
        failed_tests = []
        timeout_tests = []
        error_tests = []
        
        for test_file, result in self.results.items():
            if result['status'] == 'PASSED':
                passed_tests.append(test_file)
            elif result['status'] == 'FAILED':
                failed_tests.append(test_file)
            elif result['status'] == 'TIMEOUT':
                timeout_tests.append(test_file)
            else:
                error_tests.append(test_file)
        
        # Overall statistics
        total_tests = len(self.test_files)
        passed_count = len(passed_tests)
        failed_count = len(failed_tests)
        timeout_count = len(timeout_tests)
        error_count = len(error_tests)
        
        success_rate = (passed_count / total_tests) * 100 if total_tests > 0 else 0
        
        logger.info(f"RESULTS: OVERALL RESULTS:")
        logger.info(f"   Total Tests: {total_tests}")
        logger.info(f"   PASS: Passed: {passed_count}")
        logger.info(f"   FAIL: Failed: {failed_count}")
        logger.info(f"   TIMEOUT: Timeout: {timeout_count}")
        logger.info(f"   ERROR: Error: {error_count}")
        logger.info(f"   STATS: Success Rate: {success_rate:.1f}%")
        logger.info(f"   ⏱️  Total Duration: {total_duration:.2f}s")
        
        # Detailed results
        logger.info(f"\nDETAILS: DETAILED RESULTS:")
        for test_file, result in self.results.items():
            status_emoji = {
                'PASSED': 'PASS:',
                'FAILED': 'FAIL:', 
                'TIMEOUT': 'TIMEOUT:',
                'ERROR': 'ERROR:'
            }.get(result['status'], '❓')
            
            logger.info(f"   {status_emoji} {test_file}: {result['status']} ({result['duration']:.2f}s)")
            
            if result['status'] != 'PASSED' and result['error_message']:
                logger.info(f"      Error: {result['error_message'][:100]}...")
        
        # Test coverage analysis
        logger.info(f"\nCOVERAGE: TEST COVERAGE ANALYSIS:")
        
        coverage_areas = {
            'test_ohlcv_trade_schema.py': [
                'OHLCV table CRUD operations',
                'Trade table CRUD operations', 
                'Data integrity constraints',
                'Bulk insert performance',
                'QLib export readiness'
            ],
            'test_qlib_ohlcv_trade_export.py': [
                'QLib data query integration',
                'QLib bin file generation',
                'Export metadata tracking',
                'QLib health check integration'
            ],
            'test_complete_ohlcv_trade_pipeline.py': [
                'End-to-end data collection simulation',
                'Data consistency validation',
                'Complete QLib export pipeline',
                'Performance benchmarks'
            ]
        }
        
        for test_file, areas in coverage_areas.items():
            result = self.results.get(test_file, {})
            status = result.get('status', 'UNKNOWN')
            status_emoji = {
                'PASSED': 'PASS:',
                'FAILED': 'FAIL:',
                'TIMEOUT': 'TIMEOUT:', 
                'ERROR': 'ERROR:'
            }.get(status, '❓')
            
            logger.info(f"   {status_emoji} {test_file}:")
            for area in areas:
                logger.info(f"      • {area}")
        
        # Recommendations
        logger.info(f"\nRECOMMENDATIONS: RECOMMENDATIONS:")
        
        if passed_count == total_tests:
            logger.info("   SUCCESS: All tests passed! OHLCV/Trade QLib integration is ready for production.")
            logger.info("   RESULTS: Consider running these tests regularly as part of CI/CD pipeline.")
            logger.info("   MONITOR: Monitor performance metrics in production environment.")
        else:
            logger.info("   FIX: Address failing tests before deploying to production.")
            if failed_tests:
                logger.info(f"   FAIL: Priority: Fix failed tests: {', '.join(failed_tests)}")
            if timeout_tests:
                logger.info(f"   TIMEOUT: Investigate timeout issues: {', '.join(timeout_tests)}")
            if error_tests:
                logger.info(f"   ERROR: Resolve error conditions: {', '.join(error_tests)}")
        
        # Performance insights
        total_test_duration = sum(result['duration'] for result in self.results.values())
        avg_test_duration = total_test_duration / total_tests if total_tests > 0 else 0
        
        logger.info(f"\nPERFORMANCE: PERFORMANCE INSIGHTS:")
        logger.info(f"   Average test duration: {avg_test_duration:.2f}s")
        logger.info(f"   Total test execution time: {total_test_duration:.2f}s")
        logger.info(f"   Test suite overhead: {total_duration - total_test_duration:.2f}s")
        
        # Fastest and slowest tests
        if self.results:
            fastest_test = min(self.results.items(), key=lambda x: x[1]['duration'])
            slowest_test = max(self.results.items(), key=lambda x: x[1]['duration'])
            
            logger.info(f"   FASTEST: Fastest test: {fastest_test[0]} ({fastest_test[1]['duration']:.2f}s)")
            logger.info(f"   SLOWEST: Slowest test: {slowest_test[0]} ({slowest_test[1]['duration']:.2f}s)")
        
        logger.info("=" * 80)
        
        # Save detailed report to file
        report_file = f"ohlcv_trade_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write("OHLCV/TRADE QLIB INTEGRATION TEST REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Test Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Duration: {total_duration:.2f}s\n")
            f.write(f"Success Rate: {success_rate:.1f}%\n\n")
            
            for test_file, result in self.results.items():
                f.write(f"\n{test_file}:\n")
                f.write(f"  Status: {result['status']}\n")
                f.write(f"  Duration: {result['duration']:.2f}s\n")
                if result['error_message']:
                    f.write(f"  Error: {result['error_message']}\n")
                if result['stdout']:
                    f.write(f"  Output:\n{result['stdout']}\n")
        
        logger.info(f"REPORT: Detailed report saved to: {report_file}")

def main():
    """Main test runner entry point"""
    runner = OHLCVTradeTestRunner()
    success = runner.run_all_tests()
    
    if success:
        logger.info("SUCCESS: All OHLCV/Trade QLib integration tests completed successfully!")
        sys.exit(0)
    else:
        logger.error("FAIL: Some tests failed. Check the report for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()