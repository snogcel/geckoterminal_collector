#!/usr/bin/env python3
"""
Simple script to fix database issues without complex imports.
"""

import sqlite3
import sys
from datetime import datetime

def fix_database_issues():
    """Fix database issues using direct SQLite operations."""
    try:
        print("Connecting to database...")
        conn = sqlite3.connect('gecko_data.db', timeout=30.0)
        cursor = conn.cursor()
        
        print("Starting database fixes...")
        
        # 1. Clean up blank pool entries that have no associated data
        print("\n1. Cleaning up orphaned blank pool entries...")
        
        # First, identify pools with no associated data
        cursor.execute('''
            SELECT p.id 
            FROM pools p
            LEFT JOIN ohlcv_data o ON p.id = o.pool_id
            LEFT JOIN trades t ON p.id = t.pool_id  
            LEFT JOIN watchlist w ON p.id = w.pool_id
            WHERE (p.name IS NULL OR p.name = '' OR TRIM(p.name) = ''
                   OR p.base_token_id IS NULL 
                   OR p.quote_token_id IS NULL)
            GROUP BY p.id
            HAVING COUNT(o.id) = 0 AND COUNT(t.id) = 0 AND COUNT(w.id) = 0
        ''')
        
        orphaned_pools = cursor.fetchall()
        orphaned_count = len(orphaned_pools)
        print(f"Found {orphaned_count} orphaned pools to delete")
        
        if orphaned_count > 0:
            # Delete orphaned pools
            orphaned_ids = [pool[0] for pool in orphaned_pools]
            placeholders = ','.join(['?' for _ in orphaned_ids])
            
            cursor.execute(f'''
                DELETE FROM pools 
                WHERE id IN ({placeholders})
            ''', orphaned_ids)
            
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} orphaned pool entries")
        
        # 2. Check remaining pools with incomplete data
        print("\n2. Checking remaining pools with incomplete data...")
        cursor.execute('''
            SELECT p.id, 
                   COUNT(o.id) as ohlcv_count,
                   COUNT(t.id) as trade_count,
                   COUNT(w.id) as watchlist_count
            FROM pools p
            LEFT JOIN ohlcv_data o ON p.id = o.pool_id
            LEFT JOIN trades t ON p.id = t.pool_id  
            LEFT JOIN watchlist w ON p.id = w.pool_id
            WHERE (p.name IS NULL OR p.name = '' OR TRIM(p.name) = ''
                   OR p.base_token_id IS NULL 
                   OR p.quote_token_id IS NULL)
            GROUP BY p.id
            HAVING COUNT(o.id) > 0 OR COUNT(t.id) > 0 OR COUNT(w.id) > 0
        ''')
        
        pools_with_data = cursor.fetchall()
        if pools_with_data:
            print(f"Found {len(pools_with_data)} pools with incomplete metadata but existing data:")
            for pool in pools_with_data[:5]:  # Show first 5
                print(f"  Pool {pool[0]}: {pool[1]} OHLCV, {pool[2]} trades, {pool[3]} watchlist entries")
            if len(pools_with_data) > 5:
                print(f"  ... and {len(pools_with_data) - 5} more")
        
        # 3. Final statistics
        print("\n3. Final database statistics:")
        cursor.execute('SELECT COUNT(*) FROM pools')
        total_pools = cursor.fetchone()[0]
        print(f"Total pools: {total_pools}")
        
        cursor.execute('''
            SELECT COUNT(*) FROM pools 
            WHERE name IS NOT NULL AND name != '' AND TRIM(name) != ''
                  AND base_token_id IS NOT NULL 
                  AND quote_token_id IS NOT NULL
        ''')
        complete_pools = cursor.fetchone()[0]
        print(f"Pools with complete metadata: {complete_pools}")
        
        cursor.execute('''
            SELECT COUNT(*) FROM pools 
            WHERE name IS NULL OR name = '' OR TRIM(name) = ''
                  OR base_token_id IS NULL 
                  OR quote_token_id IS NULL
        ''')
        incomplete_pools = cursor.fetchone()[0]
        print(f"Pools with incomplete metadata: {incomplete_pools}")
        
        # Commit changes
        conn.commit()
        print("\nDatabase fixes completed successfully!")
        
        conn.close()
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("Error: Database is locked. Please stop any running collectors and try again.")
            print("You can also try running this script when the system is idle.")
        else:
            print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def create_watchlist_fix_summary():
    """Create a summary of the watchlist entry fix."""
    print("\n" + "="*60)
    print("WATCHLIST ENTRY FIX SUMMARY")
    print("="*60)
    print("Fixed the 'added_at' error in watchlist_monitor.py:")
    print("- Removed 'added_at=datetime.now()' parameter")
    print("- WatchlistEntry model uses 'created_at' field automatically")
    print("- This will prevent the 'invalid keyword argument' error")
    print()
    print("DATETIME COMPARISON FIX SUMMARY")
    print("="*60)
    print("Fixed timezone handling in sqlalchemy_manager.py:")
    print("- Added _ensure_timezone_aware() helper method")
    print("- All datetime comparisons now use timezone-aware datetimes")
    print("- This will prevent 'offset-naive vs offset-aware' errors")
    print()

if __name__ == "__main__":
    print("Database Issue Fix Script")
    print("=" * 40)
    
    # Show the code fixes that were already applied
    create_watchlist_fix_summary()
    
    # Ask user if they want to proceed with database cleanup
    response = input("Do you want to proceed with database cleanup? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        success = fix_database_issues()
        if success:
            print("\nAll fixes completed successfully!")
        else:
            print("\nSome fixes failed. Please check the errors above.")
            sys.exit(1)
    else:
        print("Skipping database cleanup. Code fixes have already been applied.")