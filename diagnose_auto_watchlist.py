#!/usr/bin/env python3
"""
Diagnostic script to check auto-watchlist configuration and recent activity.

This script checks:
1. Auto-watchlist configuration in config.yaml
2. Recent pools with high signal scores
3. Pools that should have been added to watchlist
4. Current watchlist entries
5. Potential issues preventing auto-watchlist from working
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, '.')

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from sqlalchemy import text


async def diagnose_auto_watchlist():
    """Diagnose auto-watchlist functionality."""
    
    print("=" * 80)
    print("AUTO-WATCHLIST DIAGNOSTIC")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # 1. Check configuration
        print("\n1. CONFIGURATION CHECK")
        print("-" * 80)
        
        new_pools_config = getattr(config, 'new_pools', None)
        if new_pools_config:
            signal_config = getattr(new_pools_config, 'signal_detection', None)
            if signal_config:
                print(f"   Signal detection enabled: {getattr(signal_config, 'enabled', False)}")
                print(f"   Auto-watchlist threshold: {getattr(signal_config, 'auto_watchlist_threshold', 'N/A')}")
                print(f"   Min signal score: {getattr(signal_config, 'min_signal_score', 'N/A')}")
            else:
                print("   ⚠️  Signal detection config not found")
            
            networks = getattr(new_pools_config, 'networks', {})
            print(f"\n   Configured networks: {list(networks.keys())}")
            for network_name, network_config in networks.items():
                auto_watchlist = getattr(network_config, 'auto_watchlist_integration', False)
                print(f"   - {network_name}: auto_watchlist = {auto_watchlist}")
        else:
            print("   ⚠️  New pools config not found")
        
        # 2. Check recent pools with high signal scores
        print("\n2. RECENT HIGH-SIGNAL POOLS (Last 24 hours)")
        print("-" * 80)
        
        with db_manager.connection.get_session() as session:
            result = session.execute(text("""
                SELECT 
                    pool_id,
                    name,
                    signal_score,
                    volume_trend,
                    liquidity_trend,
                    collected_at,
                    dex_id
                FROM new_pools_history
                WHERE signal_score >= 60.0
                    AND collected_at >= NOW() - INTERVAL '24 hours'
                ORDER BY signal_score DESC, collected_at DESC
                LIMIT 10
            """))
            
            rows = result.fetchall()
            
            if rows:
                print(f"   Found {len(rows)} pools with signal_score >= 60.0:")
                for row in rows:
                    pool_id, name, signal_score, vol_trend, liq_trend, collected_at, dex_id = row
                    print(f"\n   Pool: {pool_id}")
                    print(f"   - Name: {name}")
                    print(f"   - Signal Score: {signal_score}")
                    print(f"   - Volume Trend: {vol_trend}")
                    print(f"   - Liquidity Trend: {liq_trend}")
                    print(f"   - DEX: {dex_id}")
                    print(f"   - Collected: {collected_at}")
                    
                    # Check if in watchlist
                    is_in_watchlist = await db_manager.is_pool_in_watchlist(pool_id)
                    print(f"   - In Watchlist: {'✓ YES' if is_in_watchlist else '✗ NO'}")
                    
                    # Check if pool exists in pools table
                    pool_exists = session.execute(text("""
                        SELECT COUNT(*) FROM pools WHERE id = :pool_id
                    """), {'pool_id': pool_id}).scalar()
                    print(f"   - In Pools Table: {'✓ YES' if pool_exists else '✗ NO (ISSUE!)'}")
            else:
                print("   No pools with signal_score >= 60.0 found in last 24 hours")
        
        # 3. Check current watchlist
        print("\n3. CURRENT WATCHLIST")
        print("-" * 80)
        
        with db_manager.connection.get_session() as session:
            result = session.execute(text("""
                SELECT 
                    w.pool_id,
                    w.token_symbol,
                    w.token_name,
                    w.is_active,
                    w.created_at,
                    w.metadata_json
                FROM watchlist w
                ORDER BY w.created_at DESC
                LIMIT 10
            """))
            
            rows = result.fetchall()
            
            if rows:
                print(f"   Found {len(rows)} watchlist entries (showing last 10):")
                for row in rows:
                    pool_id, symbol, name, is_active, created_at, metadata = row
                    print(f"\n   - {symbol} ({name})")
                    print(f"     Pool ID: {pool_id}")
                    print(f"     Active: {is_active}")
                    print(f"     Created: {created_at}")
                    print(f"     Metadata: {metadata}")
            else:
                print("   ⚠️  Watchlist is empty!")
        
        # 4. Check for pools that should be in watchlist but aren't
        print("\n4. MISSING FROM WATCHLIST")
        print("-" * 80)
        
        with db_manager.connection.get_session() as session:
            result = session.execute(text("""
                SELECT 
                    h.pool_id,
                    h.name,
                    MAX(h.signal_score) as max_signal_score,
                    COUNT(*) as record_count,
                    MAX(h.collected_at) as last_seen
                FROM new_pools_history h
                LEFT JOIN watchlist w ON h.pool_id = w.pool_id
                WHERE h.signal_score >= 75.0
                    AND w.pool_id IS NULL
                    AND h.collected_at >= NOW() - INTERVAL '7 days'
                GROUP BY h.pool_id, h.name
                ORDER BY max_signal_score DESC
                LIMIT 10
            """))
            
            rows = result.fetchall()
            
            if rows:
                print(f"   Found {len(rows)} pools with signal >= 75.0 NOT in watchlist:")
                for row in rows:
                    pool_id, name, max_score, count, last_seen = row
                    print(f"\n   Pool: {pool_id}")
                    print(f"   - Name: {name}")
                    print(f"   - Max Signal Score: {max_score}")
                    print(f"   - Records: {count}")
                    print(f"   - Last Seen: {last_seen}")
                    
                    # Check if pool exists in pools table
                    pool_exists = session.execute(text("""
                        SELECT COUNT(*) FROM pools WHERE id = :pool_id
                    """), {'pool_id': pool_id}).scalar()
                    
                    if not pool_exists:
                        print(f"   - ⚠️  ISSUE: Pool not in pools table (foreign key constraint)")
                    else:
                        print(f"   - ✓ Pool exists in pools table")
            else:
                print("   All high-signal pools are in watchlist (or none found)")
        
        # 5. Summary and recommendations
        print("\n5. SUMMARY & RECOMMENDATIONS")
        print("-" * 80)
        
        # Count pools missing from pools table
        with db_manager.connection.get_session() as session:
            result = session.execute(text("""
                SELECT COUNT(DISTINCT h.pool_id)
                FROM new_pools_history h
                LEFT JOIN pools p ON h.pool_id = p.id
                WHERE p.id IS NULL
                    AND h.collected_at >= NOW() - INTERVAL '24 hours'
            """))
            missing_pools = result.scalar()
            
            if missing_pools > 0:
                print(f"   ⚠️  {missing_pools} pools in history but NOT in pools table")
                print("   This prevents them from being added to watchlist (foreign key)")
                print("   Recommendation: Ensure _ensure_pool_exists() is working correctly")
            else:
                print("   ✓ All recent pools exist in pools table")
        
        print("\n" + "=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ DIAGNOSTIC FAILED: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(diagnose_auto_watchlist())
