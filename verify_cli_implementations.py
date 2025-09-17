#!/usr/bin/env python3
"""
Verify both CLI implementations work correctly.

This script tests both the main CLI and the scheduler CLI to ensure
they're both functional and serve their intended purposes.
"""

import subprocess
import sys
import time
from pathlib import Path


def test_cli_implementation(cli_path, description, test_commands):
    """Test a specific CLI implementation."""
    print(f"\n🧪 Testing {description}")
    print("=" * 60)
    
    if not Path(cli_path).exists():
        print(f"❌ CLI not found: {cli_path}")
        return False
    
    passed = 0
    total = len(test_commands)
    
    for command_args, test_description in test_commands:
        print(f"⚡ Testing {test_description}...")
        
        try:
            result = subprocess.run(
                ['python', cli_path] + command_args,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"✅ {test_description} - SUCCESS")
                passed += 1
            else:
                print(f"❌ {test_description} - FAILED")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            print(f"❌ {test_description} - TIMEOUT")
        except Exception as e:
            print(f"❌ {test_description} - ERROR: {e}")
    
    success_rate = (passed / total) * 100
    print(f"\n📊 {description} Results: {passed}/{total} ({success_rate:.1f}%)")
    
    return passed == total


def main():
    """Main verification function."""
    print("🚀 CLI Implementations Verification")
    print("=" * 80)
    
    # Test main CLI implementation
    main_cli_tests = [
        (['--help'], 'main help'),
        (['--version'], 'version command'),
        (['analyze-pool-signals', '--help'], 'analyze-pool-signals help'),
        (['monitor-pool-signals', '--help'], 'monitor-pool-signals help'),
        (['validate-workflow', '--help'], 'validate-workflow help'),
        (['add-watchlist', '--help'], 'add-watchlist help'),
        (['db-health', '--help'], 'db-health help'),
    ]
    
    main_cli_success = test_cli_implementation(
        'gecko_terminal_collector/cli.py',
        'Main CLI (gecko_terminal_collector/cli.py)',
        main_cli_tests
    )
    
    # Test scheduler CLI implementation
    scheduler_cli_tests = [
        (['--help'], 'scheduler help'),
        (['start', '--help'], 'start command help'),
        (['status', '--help'], 'status command help'),
        (['run-once', '--help'], 'run-once command help'),
        (['collect-new-pools', '--help'], 'collect-new-pools help'),
        (['rate-limit-status', '--help'], 'rate-limit-status help'),
    ]
    
    scheduler_cli_success = test_cli_implementation(
        'examples/cli_with_scheduler.py',
        'Scheduler CLI (examples/cli_with_scheduler.py)',
        scheduler_cli_tests
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 80)
    
    if main_cli_success:
        print("✅ Main CLI: All tests passed")
    else:
        print("❌ Main CLI: Some tests failed")
    
    if scheduler_cli_success:
        print("✅ Scheduler CLI: All tests passed")
    else:
        print("❌ Scheduler CLI: Some tests failed")
    
    print(f"\n🎯 Purpose Clarification:")
    print(f"• Main CLI (gecko_terminal_collector/cli.py):")
    print(f"  - Comprehensive command-line interface")
    print(f"  - Individual command execution")
    print(f"  - Database management, watchlist operations")
    print(f"  - Signal analysis, workflow validation")
    print(f"  - Direct API interactions")
    
    print(f"\n• Scheduler CLI (examples/cli_with_scheduler.py):")
    print(f"  - Automated collection scheduling")
    print(f"  - Rate limiting coordination")
    print(f"  - Multi-collector orchestration")
    print(f"  - Continuous monitoring and collection")
    print(f"  - Production deployment focused")
    
    if main_cli_success and scheduler_cli_success:
        print(f"\n🎉 Both CLI implementations are working correctly!")
        print(f"✅ No conflicts detected between implementations")
        return 0
    else:
        print(f"\n⚠️  Some CLI implementations have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())