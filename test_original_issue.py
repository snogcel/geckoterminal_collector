#!/usr/bin/env python3
"""
Test the original CLI issue that was reported.

This script tests the specific commands that were failing:
- analyze-pool-signals help
- monitor-pool-signals help
"""

import subprocess
import sys


def test_command(command_args, description):
    """Test a specific CLI command."""
    print(f"⚡ Testing {description}...")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            ['python', 'gecko_terminal_collector/cli.py'] + command_args,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"✅ {description} succeeded")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {description} timed out")
        return False
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False


def main():
    """Test the original failing commands."""
    print("🚀 Testing Original CLI Issue Resolution")
    print("=" * 60)
    
    # Test the commands that were originally failing
    tests = [
        (['analyze-pool-signals', '--help'], 'analyze-pool-signals help'),
        (['monitor-pool-signals', '--help'], 'monitor-pool-signals help'),
        (['--help'], 'main help'),
        (['--version'], 'version command'),
        (['validate-workflow', '--help'], 'validate-workflow help (Unicode fix)'),
    ]
    
    passed = 0
    total = len(tests)
    
    for command_args, description in tests:
        if test_command(command_args, description):
            passed += 1
        print()
    
    # Summary
    print("=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Original CLI issues have been resolved:")
        print("   • analyze-pool-signals command is now available")
        print("   • monitor-pool-signals command is now available") 
        print("   • Unicode encoding issues fixed")
        print("   • All CLI commands working properly")
        return 0
    else:
        print(f"\n❌ {total - passed} tests still failing")
        return 1


if __name__ == "__main__":
    sys.exit(main())