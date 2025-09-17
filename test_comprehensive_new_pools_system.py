#!/usr/bin/env python3
"""
Comprehensive test script for the new pools system including:
- New pools collection
- History data capture
- Signal analysis
- Watchlist integration
- Database validation
"""

import asyncio
import subprocess
import sys
import yaml
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def run_cli_command(command_args, timeout=60):
    """Run a CLI command and return the result."""
    try:
        cmd = ["python", "-m", "gecko_terminal_collector.cli"] + command_args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


async def test_database_connection():
    """Test database connection and basic functionality."""
    print("🔌 Testing Database Connection")
    print("-" * 40)
    
    try:
        # Load config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        db_manager = SQLAlchemyDatabaseManager(config['database'])
        await db_manager.initialize()
        
        print("✅ Database connection successful")
        
        # Test basic queries
        try:
            # Check if new_pools_history table exists and has data
            query = "SELECT COUNT(*) FROM new_pools_history WHERE collected_at > NOW() - INTERVAL '24 hours'"
            result = await db_manager.execute_query(query)
            recent_records = result[0][0] if result else 0
            print(f"📊 Recent history records (24h): {recent_records}")
            
            # Check watchlist entries
            watchlist_entries = await db_manager.get_all_watchlist_entries()
            print(f"📋 Total watchlist entries: {len(watchlist_entries)}")
            
        except Exception as e:
            print(f"⚠️  Database query test failed: {e}")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_new_pools_collection():
    """Test new pools collection with various parameters."""
    print("\n🔍 Testing New Pools Collection")
    print("-" * 40)
    
    test_scenarios = [
        {
            "name": "Basic Collection (Dry Run)",
            "args": ["run-collector", "new-pools", "--network", "solana", "--dry-run"],
            "timeout": 30
        },
        {
            "name": "Collection with Auto-Watchlist (Dry Run)",
            "args": ["run-collector", "new-pools", "--network", "solana", "--auto-watchlist", 
                    "--min-liquidity", "5000", "--min-volume", "1000", "--dry-run"],
            "timeout": 30
        },
        {
            "name": "Enhanced Collection (Real)",
            "args": ["collect-new-pools", "--network", "solana", "--auto-watchlist", 
                    "--min-liquidity", "1000", "--min-volume", "100", "--min-activity-score", "60"],
            "timeout": 120
        }
    ]
    
    results = {}
    
    for scenario in test_scenarios:
        print(f"\n🧪 {scenario['name']}")
        print(f"   Command: {' '.join(scenario['args'])}")
        
        returncode, stdout, stderr = run_cli_command(scenario['args'], scenario['timeout'])
        
        if returncode == 0:
            print("✅ Success")
            if stdout:
                # Extract key metrics from output
                lines = stdout.split('\n')
                for line in lines:
                    if 'pools' in line.lower() or 'records' in line.lower():
                        print(f"   📊 {line.strip()}")
            results[scenario['name']] = {'success': True, 'output': stdout}
        else:
            print("❌ Failed")
            if stderr:
                print(f"   Error: {stderr.strip()}")
            results[scenario['name']] = {'success': False, 'error': stderr}
    
    return results


async def test_new_pools_history_data():
    """Test new pools history data capture and validation."""
    print("\n📈 Testing New Pools History Data")
    print("-" * 40)
    
    try:
        # Load config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        db_manager = SQLAlchemyDatabaseManager(config['database'])
        await db_manager.initialize()
        
        # Test 1: Check recent history records
        print("1️⃣ Checking recent history records...")
        
        query = """
        SELECT 
            pool_id,
            collected_at,
            volume_usd_h24,
            reserve_in_usd,
            signal_score,
            volume_trend,
            liquidity_trend
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '2 hours'
        ORDER BY collected_at DESC 
        LIMIT 10
        """
        
        recent_records = await db_manager.execute_query(query)
        
        if recent_records:
            print(f"✅ Found {len(recent_records)} recent records")
            for record in recent_records[:3]:  # Show first 3
                pool_id = record[0][:20] + "..." if len(record[0]) > 20 else record[0]
                collected_at = record[1]
                volume = record[2] or 0
                liquidity = record[3] or 0
                signal_score = record[4] or 0
                print(f"   📊 {pool_id} | {collected_at} | Vol: ${volume:,.0f} | Liq: ${liquidity:,.0f} | Signal: {signal_score}")
        else:
            print("⚠️  No recent history records found")
        
        # Test 2: Check data quality and completeness
        print("\n2️⃣ Checking data quality...")
        
        quality_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN volume_usd_h24 IS NOT NULL THEN 1 END) as has_volume,
            COUNT(CASE WHEN reserve_in_usd IS NOT NULL THEN 1 END) as has_liquidity,
            COUNT(CASE WHEN signal_score IS NOT NULL THEN 1 END) as has_signal_score,
            COUNT(CASE WHEN pool_created_at IS NOT NULL THEN 1 END) as has_creation_date,
            AVG(CASE WHEN signal_score IS NOT NULL THEN signal_score END) as avg_signal_score
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '24 hours'
        """
        
        quality_result = await db_manager.execute_query(quality_query)
        
        if quality_result:
            stats = quality_result[0]
            total = stats[0]
            print(f"   📊 Total records (24h): {total}")
            print(f"   📊 Volume data: {stats[1]}/{total} ({stats[1]/total*100:.1f}%)")
            print(f"   📊 Liquidity data: {stats[2]}/{total} ({stats[2]/total*100:.1f}%)")
            print(f"   📊 Signal scores: {stats[3]}/{total} ({stats[3]/total*100:.1f}%)")
            print(f"   📊 Creation dates: {stats[4]}/{total} ({stats[4]/total*100:.1f}%)")
            if stats[5]:
                print(f"   📊 Avg signal score: {stats[5]:.1f}")
        
        # Test 3: Check for potential issues
        print("\n3️⃣ Checking for potential issues...")
        
        issues_found = []
        
        # Check for duplicate records
        duplicate_query = """
        SELECT pool_id, COUNT(*) as count
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '1 hour'
        GROUP BY pool_id
        HAVING COUNT(*) > 1
        LIMIT 5
        """
        
        duplicates = await db_manager.execute_query(duplicate_query)
        if duplicates:
            issues_found.append(f"Found {len(duplicates)} pools with duplicate records in last hour")
            for dup in duplicates[:3]:
                pool_id = dup[0][:20] + "..." if len(dup[0]) > 20 else dup[0]
                print(f"   ⚠️  {pool_id}: {dup[1]} records")
        
        # Check for missing critical data
        missing_data_query = """
        SELECT COUNT(*) 
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '1 hour'
        AND (volume_usd_h24 IS NULL OR reserve_in_usd IS NULL)
        """
        
        missing_result = await db_manager.execute_query(missing_data_query)
        if missing_result and missing_result[0][0] > 0:
            issues_found.append(f"Found {missing_result[0][0]} records with missing volume/liquidity data")
        
        # Check for extremely old pool_created_at dates (potential data issues)
        old_pools_query = """
        SELECT COUNT(*) 
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '1 hour'
        AND pool_created_at < NOW() - INTERVAL '30 days'
        """
        
        old_result = await db_manager.execute_query(old_pools_query)
        if old_result and old_result[0][0] > 0:
            issues_found.append(f"Found {old_result[0][0]} records with pools older than 30 days (check 'new' pool criteria)")
        
        if issues_found:
            print("   ⚠️  Issues detected:")
            for issue in issues_found:
                print(f"      • {issue}")
        else:
            print("   ✅ No major issues detected")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ History data test failed: {e}")
        return False


def test_signal_analysis():
    """Test signal analysis functionality."""
    print("\n🎯 Testing Signal Analysis")
    print("-" * 40)
    
    # Test signal analysis CLI commands
    test_commands = [
        {
            "name": "Analyze Pool Signals",
            "args": ["analyze-pool-signals", "--network", "solana", "--hours", "6", "--min-signal-score", "50", "--limit", "10"],
            "timeout": 30
        }
    ]
    
    results = {}
    
    for test in test_commands:
        print(f"\n🧪 {test['name']}")
        
        returncode, stdout, stderr = run_cli_command(test['args'], test['timeout'])
        
        if returncode == 0:
            print("✅ Success")
            if stdout:
                lines = stdout.split('\n')
                for line in lines[:10]:  # Show first 10 lines
                    if line.strip():
                        print(f"   {line}")
            results[test['name']] = {'success': True, 'output': stdout}
        else:
            print("❌ Failed")
            if stderr:
                print(f"   Error: {stderr.strip()}")
            results[test['name']] = {'success': False, 'error': stderr}
    
    return results


def test_watchlist_integration():
    """Test watchlist integration with new pools system."""
    print("\n📋 Testing Watchlist Integration")
    print("-" * 40)
    
    # Test watchlist commands
    test_commands = [
        {
            "name": "List Current Watchlist",
            "args": ["list-watchlist", "--format", "table"],
            "timeout": 15
        },
        {
            "name": "List Active Watchlist (JSON)",
            "args": ["list-watchlist", "--active-only", "--format", "json"],
            "timeout": 15
        },
        {
            "name": "Analyze Pool Discovery",
            "args": ["analyze-pool-discovery", "--days", "1", "--format", "table"],
            "timeout": 30
        }
    ]
    
    results = {}
    
    for test in test_commands:
        print(f"\n🧪 {test['name']}")
        
        returncode, stdout, stderr = run_cli_command(test['args'], test['timeout'])
        
        if returncode == 0:
            print("✅ Success")
            if stdout:
                lines = stdout.split('\n')
                # Show relevant output lines
                for line in lines[:15]:
                    if line.strip():
                        print(f"   {line}")
            results[test['name']] = {'success': True, 'output': stdout}
        else:
            print("❌ Failed")
            if stderr:
                print(f"   Error: {stderr.strip()}")
            results[test['name']] = {'success': False, 'error': stderr}
    
    return results


async def test_database_performance():
    """Test database performance for new pools operations."""
    print("\n⚡ Testing Database Performance")
    print("-" * 40)
    
    try:
        # Load config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        db_manager = SQLAlchemyDatabaseManager(config['database'])
        await db_manager.initialize()
        
        # Test 1: Query performance for recent data
        print("1️⃣ Testing query performance...")
        
        start_time = datetime.now()
        
        query = """
        SELECT pool_id, volume_usd_h24, reserve_in_usd, signal_score
        FROM new_pools_history 
        WHERE collected_at > NOW() - INTERVAL '24 hours'
        ORDER BY signal_score DESC NULLS LAST
        LIMIT 100
        """
        
        result = await db_manager.execute_query(query)
        query_time = (datetime.now() - start_time).total_seconds()
        
        print(f"   📊 Query returned {len(result)} records in {query_time:.2f}s")
        
        if query_time > 2.0:
            print("   ⚠️  Query performance may be slow (>2s)")
        else:
            print("   ✅ Query performance good")
        
        # Test 2: Check index usage
        print("\n2️⃣ Checking database indexes...")
        
        index_query = """
        SELECT schemaname, tablename, indexname, indexdef
        FROM pg_indexes 
        WHERE tablename IN ('new_pools_history', 'watchlist_entries', 'pools')
        ORDER BY tablename, indexname
        """
        
        indexes = await db_manager.execute_query(index_query)
        
        if indexes:
            print(f"   📊 Found {len(indexes)} indexes")
            for idx in indexes:
                table = idx[1]
                index_name = idx[2]
                print(f"   📋 {table}: {index_name}")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


def generate_test_report(results: Dict):
    """Generate a comprehensive test report."""
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("=" * 60)
    
    total_tests = 0
    passed_tests = 0
    
    for category, tests in results.items():
        print(f"\n📂 {category}")
        print("-" * 30)
        
        if isinstance(tests, dict):
            for test_name, result in tests.items():
                total_tests += 1
                if result.get('success', False):
                    print(f"✅ {test_name}")
                    passed_tests += 1
                else:
                    print(f"❌ {test_name}")
                    if 'error' in result:
                        print(f"   Error: {result['error'][:100]}...")
        else:
            total_tests += 1
            if tests:
                print(f"✅ {category}")
                passed_tests += 1
            else:
                print(f"❌ {category}")
    
    print(f"\n📊 SUMMARY")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {total_tests - passed_tests}")
    print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    if passed_tests == total_tests:
        print("   🎉 All tests passed! System is working well.")
    elif passed_tests / total_tests >= 0.8:
        print("   ✅ Most tests passed. Address any failed tests.")
    else:
        print("   ⚠️  Multiple test failures detected. Review system configuration.")
    
    print("\n🔧 NEXT STEPS")
    print("   1. Review any failed tests above")
    print("   2. Check database performance if queries are slow")
    print("   3. Verify signal analysis is producing meaningful results")
    print("   4. Monitor watchlist integration for auto-additions")
    print("   5. Set up regular monitoring of new pools collection")


async def main():
    """Run comprehensive new pools system tests."""
    print("🧪 COMPREHENSIVE NEW POOLS SYSTEM TEST")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    results = {}
    
    # Test 1: Database Connection
    results['Database Connection'] = await test_database_connection()
    
    # Test 2: New Pools Collection
    results['New Pools Collection'] = test_new_pools_collection()
    
    # Test 3: History Data Validation
    results['History Data Validation'] = await test_new_pools_history_data()
    
    # Test 4: Signal Analysis
    results['Signal Analysis'] = test_signal_analysis()
    
    # Test 5: Watchlist Integration
    results['Watchlist Integration'] = test_watchlist_integration()
    
    # Test 6: Database Performance
    results['Database Performance'] = await test_database_performance()
    
    # Generate comprehensive report
    generate_test_report(results)
    
    print(f"\n🏁 Testing completed at: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())