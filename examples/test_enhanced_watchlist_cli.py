#!/usr/bin/env python3
"""
Test script for the enhanced watchlist CLI functionality.

This script demonstrates all the new watchlist management commands:
- add-watchlist (with all fields)
- list-watchlist (with different formats)
- update-watchlist (updating individual fields)
- remove-watchlist (with confirmation)
"""

import asyncio
import subprocess
import sys
import tempfile
import os
from pathlib import Path


def run_cli_command(command_args):
    """Run a CLI command and return the result."""
    try:
        # Use the gecko-cli command (assuming it's in PATH or use python -m)
        cmd = ["python", "-m", "gecko_terminal_collector.cli"] + command_args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def test_enhanced_watchlist_cli():
    """Test the enhanced watchlist CLI functionality."""
    
    print("🧪 Testing Enhanced Watchlist CLI Functionality")
    print("=" * 60)
    
    # Test data
    test_entries = [
        {
            "pool_id": "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            "symbol": "CBRL",
            "name": "Cracker Barrel Old Country Store",
            "network_address": "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump",
            "active": "true"
        },
        {
            "pool_id": "solana_4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama",
            "symbol": "TROLL",
            "name": "TROLL Token",
            "network_address": "5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2",
            "active": "true"
        }
    ]
    
    # Test 1: Add watchlist entries with all fields
    print("\n1️⃣ Testing add-watchlist with all fields")
    print("-" * 40)
    
    for i, entry in enumerate(test_entries, 1):
        print(f"\nAdding entry {i}: {entry['symbol']}")
        
        cmd_args = [
            "add-watchlist",
            "--pool-id", entry["pool_id"],
            "--symbol", entry["symbol"],
            "--name", entry["name"],
            "--network-address", entry["network_address"],
            "--active", entry["active"]
        ]
        
        returncode, stdout, stderr = run_cli_command(cmd_args)
        
        if returncode == 0:
            print(f"✅ Successfully added {entry['symbol']}")
            print(f"   Output: {stdout.strip()}")
        else:
            print(f"❌ Failed to add {entry['symbol']}")
            print(f"   Error: {stderr.strip()}")
    
    # Test 2: List watchlist entries in different formats
    print("\n\n2️⃣ Testing list-watchlist with different formats")
    print("-" * 50)
    
    formats = ["table", "csv", "json"]
    
    for fmt in formats:
        print(f"\nListing entries in {fmt} format:")
        
        cmd_args = ["list-watchlist", "--format", fmt]
        returncode, stdout, stderr = run_cli_command(cmd_args)
        
        if returncode == 0:
            print(f"✅ Successfully listed entries in {fmt} format")
            print(f"Output:\n{stdout}")
        else:
            print(f"❌ Failed to list entries in {fmt} format")
            print(f"Error: {stderr.strip()}")
    
    # Test 3: List only active entries
    print("\n\n3️⃣ Testing list-watchlist --active-only")
    print("-" * 40)
    
    cmd_args = ["list-watchlist", "--active-only", "--format", "table"]
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Successfully listed active entries")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Failed to list active entries")
        print(f"Error: {stderr.strip()}")
    
    # Test 4: Update watchlist entries
    print("\n\n4️⃣ Testing update-watchlist")
    print("-" * 30)
    
    # Update the first entry
    entry = test_entries[0]
    print(f"\nUpdating {entry['symbol']} - changing name and setting inactive")
    
    cmd_args = [
        "update-watchlist",
        "--pool-id", entry["pool_id"],
        "--name", "Updated Cracker Barrel Token",
        "--active", "false"
    ]
    
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print(f"✅ Successfully updated {entry['symbol']}")
        print(f"   Output: {stdout.strip()}")
    else:
        print(f"❌ Failed to update {entry['symbol']}")
        print(f"   Error: {stderr.strip()}")
    
    # Test 5: List entries again to see the update
    print("\n\n5️⃣ Testing list after update")
    print("-" * 30)
    
    cmd_args = ["list-watchlist", "--format", "table"]
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Successfully listed entries after update")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Failed to list entries after update")
        print(f"Error: {stderr.strip()}")
    
    # Test 6: Remove watchlist entries (with force to skip confirmation)
    print("\n\n6️⃣ Testing remove-watchlist")
    print("-" * 30)
    
    for entry in test_entries:
        print(f"\nRemoving entry: {entry['symbol']}")
        
        cmd_args = [
            "remove-watchlist",
            "--pool-id", entry["pool_id"],
            "--force"
        ]
        
        returncode, stdout, stderr = run_cli_command(cmd_args)
        
        if returncode == 0:
            print(f"✅ Successfully removed {entry['symbol']}")
            print(f"   Output: {stdout.strip()}")
        else:
            print(f"❌ Failed to remove {entry['symbol']}")
            print(f"   Error: {stderr.strip()}")
    
    # Test 7: List entries after removal
    print("\n\n7️⃣ Testing list after removal")
    print("-" * 30)
    
    cmd_args = ["list-watchlist", "--format", "table"]
    returncode, stdout, stderr = run_cli_command(cmd_args)
    
    if returncode == 0:
        print("✅ Successfully listed entries after removal")
        print(f"Output:\n{stdout}")
    else:
        print("❌ Failed to list entries after removal")
        print(f"Error: {stderr.strip()}")
    
    print("\n" + "=" * 60)
    print("🎉 Enhanced Watchlist CLI Testing Complete!")
    print("\nNew CLI commands available:")
    print("  • gecko-cli add-watchlist --pool-id <id> --symbol <sym> [--name <name>] [--network-address <addr>] [--active true/false]")
    print("  • gecko-cli list-watchlist [--active-only] [--format table/csv/json]")
    print("  • gecko-cli update-watchlist --pool-id <id> [--symbol <sym>] [--name <name>] [--network-address <addr>] [--active true/false]")
    print("  • gecko-cli remove-watchlist --pool-id <id> [--force]")


if __name__ == "__main__":
    test_enhanced_watchlist_cli()