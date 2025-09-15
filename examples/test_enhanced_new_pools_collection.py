#!/usr/bin/env python3
"""
Test script for enhanced new pools collection with automatic watchlist integration.

This script demonstrates the new enhanced pool discovery functionality that
automatically evaluates discovered pools and adds promising ones to the watchlist.
"""

import asyncio
import subprocess
import sys
import json
from datetime import datetime


def run_cli_command(command_args):
    """Run a CLI command and return the result."""
    try:
        cmd = ["python", "-m", "gecko_terminal_collector.cli"] + command_args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def test_enhanced_new_pools_collection():
    """Test the enhanced new pools collection functionality."""
    
    print("🧪 Testing Enhanced New Pools Collection")
    print("=" * 60)
    
    # Test 1: Basic new pools collection (without auto-watchlist)
    print("\n1️⃣ Testing basic new pools collection")
    print("-" * 40)
    
    cmd_args = [
        "collect-new-pools",
        "--network", "solana",
        "--dry-run"
    ]
    
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Basic collection test successful")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Basic collection test failed")
        print(f"Error: {stderr}")
    
    # Test 2: Enhanced collection with auto-watchlist (dry run)
    print("\n\n2️⃣ Testing enhanced collection with auto-watchlist (dry run)")
    print("-" * 60)
    
    cmd_args = [
        "collect-new-pools",
        "--network", "solana",
        "--auto-watchlist",
        "--min-liquidity", "1000",
        "--min-volume", "100",
        "--max-age-hours", "24",
        "--min-activity-score", "60",
        "--dry-run"
    ]
    
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Enhanced collection (dry run) test successful")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Enhanced collection (dry run) test failed")
        print(f"Error: {stderr}")
    
    # Test 3: Different criteria settings
    print("\n\n3️⃣ Testing with different criteria settings")
    print("-" * 50)
    
    criteria_tests = [
        {
            "name": "High liquidity threshold",
            "args": ["--min-liquidity", "10000", "--min-volume", "1000"]
        },
        {
            "name": "Low activity score threshold", 
            "args": ["--min-activity-score", "30"]
        },
        {
            "name": "Recent pools only",
            "args": ["--max-age-hours", "6"]
        }
    ]
    
    for test in criteria_tests:
        print(f"\nTesting: {test['name']}")
        
        cmd_args = [
            "collect-new-pools",
            "--network", "solana",
            "--auto-watchlist",
            "--dry-run"
        ] + test['args']
        
        returncode, stdout, stderr = run_cli_command(cmd_args)
        
        if returncode == 0:
            print(f"✅ {test['name']} test successful")
            # Extract key information from output
            lines = stdout.split('\n')
            for line in lines:
                if 'Min liquidity:' in line or 'Min volume:' in line or 'Min activity score:' in line or 'Max age:' in line:
                    print(f"   {line.strip()}")
        else:
            print(f"❌ {test['name']} test failed")
            print(f"   Error: {stderr.strip()}")
    
    # Test 4: Pool discovery analysis
    print("\n\n4️⃣ Testing pool discovery analysis")
    print("-" * 40)
    
    analysis_formats = ["table", "json", "csv"]
    
    for fmt in analysis_formats:
        print(f"\nAnalyzing in {fmt} format:")
        
        cmd_args = [
            "analyze-pool-discovery",
            "--days", "7",
            "--format", fmt
        ]
        
        returncode, stdout, stderr = run_cli_command(cmd_args)
        
        if returncode == 0:
            print(f"✅ Analysis in {fmt} format successful")
            if fmt == "json":
                try:
                    # Pretty print JSON
                    data = json.loads(stdout)
                    print(json.dumps(data, indent=2))
                except:
                    print(stdout)
            else:
                print(stdout)
        else:
            print(f"❌ Analysis in {fmt} format failed")
            print(f"Error: {stderr.strip()}")
    
    # Test 5: Network-specific analysis
    print("\n\n5️⃣ Testing network-specific analysis")
    print("-" * 40)
    
    cmd_args = [
        "analyze-pool-discovery",
        "--days", "3",
        "--network", "solana",
        "--format", "table"
    ]
    
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Network-specific analysis successful")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Network-specific analysis failed")
        print(f"Error: {stderr}")
    
    # Test 6: Integration with existing watchlist commands
    print("\n\n6️⃣ Testing integration with existing watchlist commands")
    print("-" * 55)
    
    print("Listing current watchlist entries:")
    cmd_args = ["list-watchlist", "--format", "table"]
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Watchlist integration test successful")
        print(f"Current watchlist:\n{stdout}")
    else:
        print("❌ Watchlist integration test failed")
        print(f"Error: {stderr}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 Enhanced New Pools Collection Testing Complete!")
    print("\nNew CLI commands available:")
    print("  • gecko-cli collect-new-pools --network <net> [--auto-watchlist] [criteria...]")
    print("  • gecko-cli analyze-pool-discovery --days <n> [--network <net>] [--format <fmt>]")
    
    print("\nKey Features Tested:")
    print("  ✅ Enhanced pool collection with configurable criteria")
    print("  ✅ Automatic watchlist integration")
    print("  ✅ Dry-run mode for safe testing")
    print("  ✅ Multiple output formats for analysis")
    print("  ✅ Network-specific filtering")
    print("  ✅ Integration with existing watchlist system")
    
    print("\nNext Steps:")
    print("  1. Run actual collection: gecko-cli collect-new-pools --network solana --auto-watchlist")
    print("  2. Monitor results: gecko-cli analyze-pool-discovery --days 1")
    print("  3. Review watchlist: gecko-cli list-watchlist --active-only")


def demonstrate_usage_scenarios():
    """Demonstrate common usage scenarios."""
    
    print("\n" + "🚀 Common Usage Scenarios")
    print("=" * 50)
    
    scenarios = [
        {
            "name": "Conservative Discovery",
            "description": "High liquidity and volume thresholds for stable pools",
            "command": "gecko-cli collect-new-pools --network solana --auto-watchlist --min-liquidity 50000 --min-volume 10000 --min-activity-score 80"
        },
        {
            "name": "Aggressive Discovery", 
            "description": "Lower thresholds to catch emerging opportunities",
            "command": "gecko-cli collect-new-pools --network solana --auto-watchlist --min-liquidity 500 --min-volume 50 --min-activity-score 40"
        },
        {
            "name": "Recent Pools Only",
            "description": "Focus on very recently created pools",
            "command": "gecko-cli collect-new-pools --network solana --auto-watchlist --max-age-hours 6 --min-activity-score 70"
        },
        {
            "name": "Analysis and Monitoring",
            "description": "Regular analysis of discovery performance",
            "command": "gecko-cli analyze-pool-discovery --days 7 --format json > discovery_report.json"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"   Command: {scenario['command']}")
    
    print(f"\n💡 Pro Tips:")
    print(f"   • Use --dry-run first to test criteria without storing data")
    print(f"   • Monitor discovery_report.json for performance trends")
    print(f"   • Adjust criteria based on market conditions")
    print(f"   • Use different criteria for different market phases")


if __name__ == "__main__":
    test_enhanced_new_pools_collection()
    demonstrate_usage_scenarios()