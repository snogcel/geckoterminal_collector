#!/usr/bin/env python3
"""
Debug script specifically for new pools history data capture issues.
This script helps identify and diagnose problems with the new_pools_history collection process.
"""

import asyncio
import yaml
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any


async def debug_new_pools_history():
    """Debug new pools history data capture process."""
    
    print("🔍 NEW POOLS HISTORY DEBUG ANALYSIS")
    print("=" * 50)
    
    try:
        # Load config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        db_manager = SQLAlchemyDatabaseManager(config['database'])
        await db_manager.initialize()
        
        # Debug 1: Check table structure
        await debug_table_structure(db_manager)
        
        # Debug 2: Analyze recent collection patterns
        await debug_collection_patterns(db_manager)
        
        # Debug 3: Check data quality issues
        await debug_data_quality(db_manager)
        
        # Debug 4: Validate signal analysis data
        await debug_signal_analysis(db_manager)
        
        # Debug 5: Check for collection gaps
        await debug_collection_gaps(db_manager)
        
        # Debug 6: Analyze pool lifecycle
        await debug_pool_lifecycle(db_manager)
        
        await db_manager.close()
        
    except Exception as e:
        print(f"❌ Debug analysis failed: {e}")
        import traceback
        traceback.print_exc()


async def debug_table_structure(db_manager):
    """Debug the new_pools_history table structure."""
    print("\n1️⃣ TABLE STRUCTURE ANALYSIS")
    print("-" * 30)
    
    try:
        # Check if table exists
        table_check = await db_manager.execute_query("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'new_pools_history'
            )
        """)
        
        if not table_check[0][0]:
            print("❌ new_pools_history table does not exist!")
            return
        
        print("✅ new_pools_history table exists")
        
        # Get column information
        columns_query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'new_pools_history'
        ORDER BY ordinal_position
        """
        
        columns = await db_manager.execute_query(columns_query)
        
        print(f"📊 Table has {len(columns)} columns:")
        for col in columns:
            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
            default = f" DEFAULT {col[3]}" if col[3] else ""
            print(f"   • {col[0]}: {col[1]} {nullable}{default}")
        
        # Check indexes
        indexes_query = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'new_pools_history'
        """
        
        indexes = await db_manager.execute_query(indexes_query)
        
        if indexes:
            print(f"\n📋 Table indexes ({len(indexes)}):")
            for idx in indexes:
                print(f"   • {idx[0]}")
        else:
            print("\n⚠️  No indexes found - this may cause performance issues")
        
    except Exception as e:
        print(f"❌ Table structure check failed: {e}")


async def debug_collection_patterns(db_manager):
    """Debug collection patterns and frequency."""
    print("\n2️⃣ COLLECTION PATTERNS ANALYSIS")
    print("-" * 30)
    
    try:
        # Check collection frequency over time
        frequency_query = """
        SELECT 
            DATE_TRUNC('hour', collected_at) as hour,
            COUNT(*) as records_count,
            COUNT(DISTINCT pool_id) as unique_pools
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '24 hours'
        GROUP BY DATE_TRUNC('hour', collected_at)
        ORDER BY hour DESC
        LIMIT 12
        """
        
        frequency_data = await db_manager.execute_query(frequency_query)
        
        if frequency_data:
            print("📊 Collection frequency (last 12 hours):")
            for row in frequency_data:
                hour = row[0].strftime("%Y-%m-%d %H:00")
                print(f"   {hour}: {row[1]} records, {row[2]} unique pools")
        else:
            print("⚠️  No collection data found in last 24 hours")
        
        # Check for collection gaps
        gaps_query = """
        WITH hourly_expected AS (
            SELECT generate_series(
                DATE_TRUNC('hour', NOW() - INTERVAL '24 hours'),
                DATE_TRUNC('hour', NOW()),
                INTERVAL '1 hour'
            ) as expected_hour
        ),
        actual_collections AS (
            SELECT DISTINCT DATE_TRUNC('hour', collected_at) as actual_hour
            FROM new_pools_history
            WHERE collected_at > NOW() - INTERVAL '24 hours'
        )
        SELECT he.expected_hour
        FROM hourly_expected he
        LEFT JOIN actual_collections ac ON he.expected_hour = ac.actual_hour
        WHERE ac.actual_hour IS NULL
        ORDER BY he.expected_hour
        """
        
        gaps = await db_manager.execute_query(gaps_query)
        
        if gaps:
            print(f"\n⚠️  Found {len(gaps)} collection gaps in last 24 hours:")
            for gap in gaps[:5]:  # Show first 5 gaps
                print(f"   • Missing: {gap[0].strftime('%Y-%m-%d %H:00')}")
        else:
            print("\n✅ No collection gaps detected")
        
    except Exception as e:
        print(f"❌ Collection patterns analysis failed: {e}")


async def debug_data_quality(db_manager):
    """Debug data quality issues."""
    print("\n3️⃣ DATA QUALITY ANALYSIS")
    print("-" * 30)
    
    try:
        # Check for null/missing critical fields
        quality_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN pool_id IS NULL OR pool_id = '' THEN 1 END) as missing_pool_id,
            COUNT(CASE WHEN volume_usd_h24 IS NULL THEN 1 END) as missing_volume,
            COUNT(CASE WHEN reserve_in_usd IS NULL THEN 1 END) as missing_liquidity,
            COUNT(CASE WHEN pool_created_at IS NULL THEN 1 END) as missing_creation_date,
            COUNT(CASE WHEN dex_id IS NULL OR dex_id = '' THEN 1 END) as missing_dex_id,
            COUNT(CASE WHEN network_id IS NULL OR network_id = '' THEN 1 END) as missing_network
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        """
        
        quality_result = await db_manager.execute_query(quality_query)
        
        if quality_result:
            stats = quality_result[0]
            total = stats[0]
            
            print(f"📊 Data quality (last 6 hours, {total} records):")
            
            issues = [
                ("Missing pool_id", stats[1]),
                ("Missing volume", stats[2]),
                ("Missing liquidity", stats[3]),
                ("Missing creation date", stats[4]),
                ("Missing dex_id", stats[5]),
                ("Missing network", stats[6])
            ]
            
            for issue_name, count in issues:
                if count > 0:
                    percentage = (count / total * 100) if total > 0 else 0
                    print(f"   ⚠️  {issue_name}: {count} ({percentage:.1f}%)")
                else:
                    print(f"   ✅ {issue_name}: 0")
        
        # Check for data anomalies
        anomalies_query = """
        SELECT 
            'Extremely high volume' as anomaly_type,
            COUNT(*) as count
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        AND volume_usd_h24 > 10000000  -- > $10M
        
        UNION ALL
        
        SELECT 
            'Negative volume' as anomaly_type,
            COUNT(*) as count
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        AND volume_usd_h24 < 0
        
        UNION ALL
        
        SELECT 
            'Future creation date' as anomaly_type,
            COUNT(*) as count
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        AND pool_created_at > NOW()
        
        UNION ALL
        
        SELECT 
            'Very old pools (>30 days)' as anomaly_type,
            COUNT(*) as count
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        AND pool_created_at < NOW() - INTERVAL '30 days'
        """
        
        anomalies = await db_manager.execute_query(anomalies_query)
        
        if anomalies:
            print(f"\n🔍 Data anomalies detected:")
            for anomaly in anomalies:
                if anomaly[1] > 0:
                    print(f"   ⚠️  {anomaly[0]}: {anomaly[1]} records")
        
    except Exception as e:
        print(f"❌ Data quality analysis failed: {e}")


async def debug_signal_analysis(db_manager):
    """Debug signal analysis data."""
    print("\n4️⃣ SIGNAL ANALYSIS DEBUG")
    print("-" * 30)
    
    try:
        # Check signal score distribution
        signal_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN signal_score IS NOT NULL THEN 1 END) as has_signal_score,
            AVG(signal_score) as avg_signal_score,
            MIN(signal_score) as min_signal_score,
            MAX(signal_score) as max_signal_score,
            COUNT(CASE WHEN signal_score >= 70 THEN 1 END) as high_signal_count,
            COUNT(CASE WHEN volume_trend IS NOT NULL THEN 1 END) as has_volume_trend,
            COUNT(CASE WHEN liquidity_trend IS NOT NULL THEN 1 END) as has_liquidity_trend
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        """
        
        signal_result = await db_manager.execute_query(signal_query)
        
        if signal_result:
            stats = signal_result[0]
            total = stats[0]
            
            print(f"📊 Signal analysis (last 6 hours, {total} records):")
            print(f"   📈 Records with signal scores: {stats[1]} ({stats[1]/total*100:.1f}%)")
            
            if stats[2]:
                print(f"   📊 Average signal score: {stats[2]:.1f}")
                print(f"   📊 Signal score range: {stats[3]:.1f} - {stats[4]:.1f}")
                print(f"   🎯 High signals (≥70): {stats[5]}")
            
            print(f"   📈 Volume trend data: {stats[6]} ({stats[6]/total*100:.1f}%)")
            print(f"   📈 Liquidity trend data: {stats[7]} ({stats[7]/total*100:.1f}%)")
        
        # Check trend distribution
        trend_query = """
        SELECT 
            volume_trend,
            COUNT(*) as count
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '6 hours'
        AND volume_trend IS NOT NULL
        GROUP BY volume_trend
        ORDER BY count DESC
        """
        
        trends = await db_manager.execute_query(trend_query)
        
        if trends:
            print(f"\n📊 Volume trend distribution:")
            for trend in trends:
                print(f"   • {trend[0] or 'NULL'}: {trend[1]} records")
        
    except Exception as e:
        print(f"❌ Signal analysis debug failed: {e}")


async def debug_collection_gaps(db_manager):
    """Debug collection gaps and timing issues."""
    print("\n5️⃣ COLLECTION GAPS ANALYSIS")
    print("-" * 30)
    
    try:
        # Find the largest gaps between collections
        gaps_query = """
        WITH collection_times AS (
            SELECT 
                collected_at,
                LAG(collected_at) OVER (ORDER BY collected_at) as prev_collected_at
            FROM (
                SELECT DISTINCT collected_at
                FROM new_pools_history
                WHERE collected_at > NOW() - INTERVAL '24 hours'
                ORDER BY collected_at
            ) t
        )
        SELECT 
            prev_collected_at,
            collected_at,
            EXTRACT(EPOCH FROM (collected_at - prev_collected_at))/60 as gap_minutes
        FROM collection_times
        WHERE prev_collected_at IS NOT NULL
        AND EXTRACT(EPOCH FROM (collected_at - prev_collected_at))/60 > 60  -- Gaps > 1 hour
        ORDER BY gap_minutes DESC
        LIMIT 10
        """
        
        gaps = await db_manager.execute_query(gaps_query)
        
        if gaps:
            print(f"⚠️  Found {len(gaps)} significant collection gaps (>1 hour):")
            for gap in gaps:
                prev_time = gap[0].strftime("%Y-%m-%d %H:%M")
                curr_time = gap[1].strftime("%Y-%m-%d %H:%M")
                gap_hours = gap[2] / 60
                print(f"   • {prev_time} → {curr_time} ({gap_hours:.1f} hours)")
        else:
            print("✅ No significant collection gaps found")
        
        # Check collection consistency
        consistency_query = """
        SELECT 
            DATE_TRUNC('day', collected_at) as day,
            COUNT(DISTINCT DATE_TRUNC('hour', collected_at)) as hours_with_data,
            COUNT(*) as total_records,
            COUNT(DISTINCT pool_id) as unique_pools
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '7 days'
        GROUP BY DATE_TRUNC('day', collected_at)
        ORDER BY day DESC
        """
        
        consistency = await db_manager.execute_query(consistency_query)
        
        if consistency:
            print(f"\n📊 Daily collection consistency (last 7 days):")
            for day in consistency:
                day_str = day[0].strftime("%Y-%m-%d")
                print(f"   {day_str}: {day[1]}/24 hours, {day[2]} records, {day[3]} pools")
        
    except Exception as e:
        print(f"❌ Collection gaps analysis failed: {e}")


async def debug_pool_lifecycle(db_manager):
    """Debug pool lifecycle and tracking."""
    print("\n6️⃣ POOL LIFECYCLE ANALYSIS")
    print("-" * 30)
    
    try:
        # Find pools that appear and disappear
        lifecycle_query = """
        WITH pool_appearances AS (
            SELECT 
                pool_id,
                MIN(collected_at) as first_seen,
                MAX(collected_at) as last_seen,
                COUNT(*) as total_records,
                COUNT(DISTINCT DATE_TRUNC('hour', collected_at)) as hours_tracked
            FROM new_pools_history
            WHERE collected_at > NOW() - INTERVAL '48 hours'
            GROUP BY pool_id
        )
        SELECT 
            COUNT(*) as total_pools,
            COUNT(CASE WHEN hours_tracked = 1 THEN 1 END) as single_hour_pools,
            COUNT(CASE WHEN hours_tracked >= 24 THEN 1 END) as long_tracked_pools,
            AVG(hours_tracked) as avg_hours_tracked,
            AVG(total_records) as avg_records_per_pool
        FROM pool_appearances
        """
        
        lifecycle_result = await db_manager.execute_query(lifecycle_query)
        
        if lifecycle_result:
            stats = lifecycle_result[0]
            print(f"📊 Pool lifecycle (last 48 hours):")
            print(f"   🏊 Total unique pools: {stats[0]}")
            print(f"   ⚡ Single-hour pools: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
            print(f"   🔄 Long-tracked pools (≥24h): {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
            print(f"   📊 Average tracking duration: {stats[3]:.1f} hours")
            print(f"   📊 Average records per pool: {stats[4]:.1f}")
        
        # Find pools with unusual patterns
        unusual_query = """
        SELECT 
            pool_id,
            COUNT(*) as record_count,
            MIN(volume_usd_h24) as min_volume,
            MAX(volume_usd_h24) as max_volume,
            CASE 
                WHEN MAX(volume_usd_h24) > 0 AND MIN(volume_usd_h24) >= 0 
                THEN MAX(volume_usd_h24) / NULLIF(MIN(volume_usd_h24), 0)
                ELSE NULL 
            END as volume_ratio
        FROM new_pools_history
        WHERE collected_at > NOW() - INTERVAL '24 hours'
        AND volume_usd_h24 IS NOT NULL
        GROUP BY pool_id
        HAVING COUNT(*) >= 5  -- At least 5 records
        AND MAX(volume_usd_h24) / NULLIF(MIN(volume_usd_h24), 0) > 100  -- 100x volume change
        ORDER BY volume_ratio DESC
        LIMIT 5
        """
        
        unusual = await db_manager.execute_query(unusual_query)
        
        if unusual:
            print(f"\n🚨 Pools with unusual volume patterns:")
            for pool in unusual:
                pool_id = pool[0][:20] + "..." if len(pool[0]) > 20 else pool[0]
                print(f"   • {pool_id}: {pool[4]:.1f}x volume change ({pool[1]} records)")
        
    except Exception as e:
        print(f"❌ Pool lifecycle analysis failed: {e}")


async def main():
    """Run the debug analysis."""
    await debug_new_pools_history()
    
    print("\n" + "=" * 50)
    print("🔧 DEBUG RECOMMENDATIONS")
    print("=" * 50)
    
    print("\n💡 If you found issues:")
    print("   1. Check collector configuration in config.yaml")
    print("   2. Verify API connectivity and rate limits")
    print("   3. Review database indexes for performance")
    print("   4. Check signal analysis configuration")
    print("   5. Monitor collection scheduling")
    
    print("\n🔍 For deeper investigation:")
    print("   • Run: python -m gecko_terminal_collector.cli run-collector new-pools --dry-run")
    print("   • Check logs for collection errors")
    print("   • Verify database constraints and foreign keys")
    print("   • Test signal analysis with sample data")


if __name__ == "__main__":
    asyncio.run(main())