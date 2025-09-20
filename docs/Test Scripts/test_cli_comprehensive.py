#!/usr/bin/env python3
"""
Comprehensive CLI Test Suite for GeckoTerminal Data Collector

This test suite analyzes CLI command availability, validates command structure,
and identifies missing or broken commands.
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommandTest:
    """Represents a CLI command test case."""
    name: str
    command: List[str]
    expected_success: bool = True
    expected_in_output: Optional[str] = None
    expected_not_in_output: Optional[str] = None
    timeout: int = 10


@dataclass
class TestResult:
    """Represents the result of a command test."""
    command_name: str
    success: bool
    output: str
    error: str
    execution_time: float
    issues: List[str]


class CLITestSuite:
    """Comprehensive CLI testing suite."""
    
    def __init__(self, cli_script: str = "gecko_terminal_collector/cli.py"):
        self.cli_script = cli_script
        self.results: List[TestResult] = []
        
        # Expected commands based on CLI analysis
        self.expected_commands = [
            # System setup and configuration
            'init', 'validate', 'db-setup',
            # Collection management
            'start', 'stop', 'status', 'run-collector',
            # Data management
            'backfill', 'export', 'cleanup',
            # Maintenance and monitoring
            'health-check', 'metrics', 'logs',
            # Backup and restore
            'backup', 'restore',
            # Workflow validation
            'build-ohlcv', 'validate-workflow',
            # Migration
            'migrate-pool-ids',
            # Watchlist management
            'add-watchlist', 'list-watchlist', 'update-watchlist', 'remove-watchlist',
            # Enhanced pool discovery
            'collect-new-pools', 'analyze-pool-discovery',
            # Signal analysis (currently missing)
            'analyze-pool-signals', 'monitor-pool-signals',
            # Database health
            'db-health', 'db-monitor'
        ]
    
    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[int, str, str, float]:
        """Run a CLI command and return results."""
        start_time = time.time()
        try:
            result = subprocess.run(
                ['python', self.cli_script] + cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time
            return result.returncode, result.stdout, result.stderr, execution_time
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return -1, "", f"Command timed out after {timeout} seconds", execution_time
        except Exception as e:
            execution_time = time.time() - start_time
            return -2, "", f"Exception running command: {str(e)}", execution_time
    
    def test_help_command(self) -> TestResult:
        """Test the main help command."""
        returncode, stdout, stderr, exec_time = self.run_command(['--help'])
        
        issues = []
        success = returncode == 0
        
        if not success:
            issues.append(f"Help command failed with return code {returncode}")
        
        if stderr and "error" in stderr.lower():
            issues.append(f"Help command produced error: {stderr}")
        
        # Check if expected commands are listed in help
        missing_commands = []
        for cmd in self.expected_commands:
            if cmd not in stdout:
                missing_commands.append(cmd)
        
        if missing_commands:
            issues.append(f"Missing commands in help: {', '.join(missing_commands)}")
        
        return TestResult(
            command_name="--help",
            success=success and len(issues) == 0,
            output=stdout,
            error=stderr,
            execution_time=exec_time,
            issues=issues
        )
    
    def test_command_help(self, command: str) -> TestResult:
        """Test help for a specific command."""
        returncode, stdout, stderr, exec_time = self.run_command([command, '--help'])
        
        issues = []
        success = returncode == 0
        
        if not success:
            if "invalid choice" in stderr:
                issues.append(f"Command '{command}' not available in CLI")
            else:
                issues.append(f"Command help failed with return code {returncode}")
        
        if stderr and "error" in stderr.lower() and "invalid choice" not in stderr:
            issues.append(f"Command help produced error: {stderr}")
        
        return TestResult(
            command_name=f"{command} --help",
            success=success,
            output=stdout,
            error=stderr,
            execution_time=exec_time,
            issues=issues
        )
    
    def test_version_command(self) -> TestResult:
        """Test version command."""
        returncode, stdout, stderr, exec_time = self.run_command(['--version'])
        
        issues = []
        success = returncode == 0
        
        if not success:
            issues.append(f"Version command failed with return code {returncode}")
        
        if not stdout or "gecko-terminal-collector" not in stdout:
            issues.append("Version output doesn't contain expected application name")
        
        return TestResult(
            command_name="--version",
            success=success and len(issues) == 0,
            output=stdout,
            error=stderr,
            execution_time=exec_time,
            issues=issues
        )
    
    def test_command_structure(self) -> TestResult:
        """Test overall command structure and availability."""
        # Get main help to see available commands
        returncode, stdout, stderr, exec_time = self.run_command(['--help'])
        
        issues = []
        success = returncode == 0
        
        if not success:
            issues.append("Cannot get main help output")
            return TestResult(
                command_name="command-structure",
                success=False,
                output=stdout,
                error=stderr,
                execution_time=exec_time,
                issues=issues
            )
        
        # Parse available commands from help output
        available_commands = []
        lines = stdout.split('\n')
        in_commands_section = False
        
        for line in lines:
            # Start parsing when we see positional arguments section
            if 'positional arguments:' in line:
                in_commands_section = True
                continue
            
            # Stop parsing when we reach options or examples section
            if in_commands_section and ('options:' in line or 'Examples:' in line):
                break
                
            if in_commands_section and line.strip():
                # Look for command lines that start with 4 spaces (individual commands)
                if line.startswith('    ') and not line.startswith('      '):
                    # This looks like a command line
                    parts = line.strip().split()
                    if parts:
                        cmd = parts[0].rstrip(',')
                        # Skip the command choices line and help text
                        if (cmd and not cmd.startswith('-') and not cmd.startswith('{') 
                            and cmd != 'Available' and cmd != 'commands'):
                            available_commands.append(cmd)
        
        # Check for missing expected commands
        missing_commands = []
        for expected_cmd in self.expected_commands:
            if expected_cmd not in available_commands:
                missing_commands.append(expected_cmd)
        
        if missing_commands:
            issues.append(f"Missing expected commands: {', '.join(missing_commands)}")
        
        # Check for unexpected commands (might indicate typos or deprecated commands)
        unexpected_commands = []
        for available_cmd in available_commands:
            if available_cmd not in self.expected_commands and available_cmd != 'command':
                unexpected_commands.append(available_cmd)
        
        if unexpected_commands:
            issues.append(f"Unexpected commands found: {', '.join(unexpected_commands)}")
        
        return TestResult(
            command_name="command-structure",
            success=len(issues) == 0,
            output=f"Available: {', '.join(available_commands)}",
            error=stderr,
            execution_time=exec_time,
            issues=issues
        )
    
    def run_comprehensive_test(self) -> Dict[str, any]:
        """Run comprehensive CLI test suite."""
        print("🚀 Starting Comprehensive CLI Test Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        # Test basic functionality
        print("\n📋 Testing Basic CLI Functionality...")
        print("-" * 40)
        
        # Test main help
        result = self.test_help_command()
        self.results.append(result)
        self._print_test_result("Main Help", result)
        
        # Test version
        result = self.test_version_command()
        self.results.append(result)
        self._print_test_result("Version", result)
        
        # Test command structure
        result = self.test_command_structure()
        self.results.append(result)
        self._print_test_result("Command Structure", result)
        
        # Test individual command help
        print("\n🔍 Testing Individual Command Help...")
        print("-" * 40)
        
        for command in self.expected_commands:
            result = self.test_command_help(command)
            self.results.append(result)
            self._print_test_result(f"{command} help", result)
        
        # Generate summary
        total_time = time.time() - start_time
        return self._generate_summary(total_time)
    
    def _print_test_result(self, test_name: str, result: TestResult):
        """Print formatted test result."""
        status = "✅" if result.success else "❌"
        print(f"{status} {test_name:<30} ({result.execution_time:.2f}s)")
        
        if result.issues:
            for issue in result.issues:
                print(f"   ⚠️  {issue}")
    
    def _generate_summary(self, total_time: float) -> Dict[str, any]:
        """Generate test summary."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        # Collect all issues
        all_issues = []
        for result in self.results:
            for issue in result.issues:
                all_issues.append(f"{result.command_name}: {issue}")
        
        # Identify critical issues
        critical_issues = []
        missing_commands = []
        
        for issue in all_issues:
            if "not available in CLI" in issue:
                cmd = issue.split("'")[1] if "'" in issue else "unknown"
                missing_commands.append(cmd)
                critical_issues.append(issue)
            elif "Missing expected commands" in issue:
                critical_issues.append(issue)
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_time": total_time,
            "all_issues": all_issues,
            "critical_issues": critical_issues,
            "missing_commands": missing_commands,
            "timestamp": datetime.now().isoformat()
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Total Time: {total_time:.2f}s")
        
        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES ({len(critical_issues)}):")
            for issue in critical_issues:
                print(f"   • {issue}")
        
        if missing_commands:
            print(f"\n❌ MISSING COMMANDS ({len(missing_commands)}):")
            for cmd in missing_commands:
                print(f"   • {cmd}")
        
        if all_issues:
            print(f"\n⚠️  ALL ISSUES ({len(all_issues)}):")
            for issue in all_issues:
                print(f"   • {issue}")
        
        return summary
    
    def generate_fix_recommendations(self) -> List[str]:
        """Generate recommendations to fix identified issues."""
        recommendations = []
        
        # Check for missing signal analysis commands
        missing_signal_commands = [cmd for cmd in ['analyze-pool-signals', 'monitor-pool-signals'] 
                                 if any('not available in CLI' in issue and cmd in issue 
                                       for result in self.results for issue in result.issues)]
        
        if missing_signal_commands:
            recommendations.append(
                "CRITICAL: Uncomment signal analysis commands in cli.py:\n"
                "  - Uncomment _add_analyze_pool_signals_command(subparsers) around line 1050\n"
                "  - Uncomment _add_monitor_pool_signals_command(subparsers) around line 1051\n"
                "  - Uncomment command handlers in command_handlers dict around line 1100"
            )
        
        # Check for other missing commands
        other_missing = [cmd for cmd in self.expected_commands 
                        if cmd not in missing_signal_commands and 
                        any('not available in CLI' in issue and cmd in issue 
                           for result in self.results for issue in result.issues)]
        
        if other_missing:
            recommendations.append(
                f"Missing commands need implementation: {', '.join(other_missing)}"
            )
        
        # Check for structural issues
        structure_issues = [result for result in self.results 
                          if result.command_name == "command-structure" and not result.success]
        
        if structure_issues:
            recommendations.append(
                "Command structure issues detected - review main() function parser setup"
            )
        
        return recommendations


def main():
    """Main test runner."""
    if len(sys.argv) > 1:
        cli_script = sys.argv[1]
    else:
        cli_script = "gecko_terminal_collector/cli.py"
    
    # Check if CLI script exists
    if not Path(cli_script).exists():
        print(f"❌ CLI script not found: {cli_script}")
        return 1
    
    # Run test suite
    test_suite = CLITestSuite(cli_script)
    summary = test_suite.run_comprehensive_test()
    
    # Generate fix recommendations
    recommendations = test_suite.generate_fix_recommendations()
    
    if recommendations:
        print("\n" + "=" * 60)
        print("🔧 FIX RECOMMENDATIONS")
        print("=" * 60)
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}\n")
    
    # Save detailed results
    results_file = f"cli_test_results_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "summary": summary,
            "recommendations": recommendations,
            "detailed_results": [
                {
                    "command_name": r.command_name,
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "issues": r.issues,
                    "output_length": len(r.output),
                    "error_length": len(r.error)
                }
                for r in test_suite.results
            ]
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {results_file}")
    
    # Return appropriate exit code
    return 0 if summary['success_rate'] > 90 else 1


if __name__ == "__main__":
    sys.exit(main())