#!/usr/bin/env python3
"""
Script to clean up blank entries in the pools table.
"""

import sqlite3
import sys

def cleanup_blank_pools():
    """Clean up blank/incomplete entries in pools table."""
    try:
        # Connect to the database
        conn = sqlite3.connect('gecko_data.db')
        cursor = conn.cursor()
        
        # First, let's see what we're dealing with
        cursor.execute('''
            SELECT COUNT(*) FROM pools 
            WHERE name IS NULL OR name = '' OR TRIM(name) = ''
               OR base_token_id IS NULL 
               OR quote_token_id IS NULL
        ''')
        incomplete_count = cursor.fetchone()[0]
        print(f'Found {incomplete_count} incomplete pool entries')
        
        # Check if these pools have any associated data
        cursor.execute('''
            SELECT p.id, 
                   COUNT(o.id) as ohlcv_count,
                   COUNT(t.id) as trade_count,
                   COUNT(w.id) as watchlist_count
            FROM pools p
            LEFT JOIN ohlcv_data o ON p.id = o.pool_id
            LEFT JOIN trades t ON p.id = t.pool_id  
            LEFT JOIN watchlist w ON p.id = w.pool_id
            WHERE p.name IS NULL OR p.name = '' OR TRIM(p.name) = ''
               OR p.base_token_id IS NULL 
               OR p.quote_token_id IS NULL
            GROUP BY p.id
            HAVING ohlcv_count = 0 AND trade_count = 0 AND watchlist_count = 0
        ''')
        
        orphaned_pools = cursor.fetchall()
        print(f'Found {len(orphaned_pools)} pools with no associated data that can be safely deleted')
        
        if orphaned_pools:
            # Delete orphaned pools with no data
            orphaned_ids = [pool[0] for pool in orphaned_pools]
            placeholders = ','.join(['?' for _ in orphaned_ids])
            
            cursor.execute(f'''
                DELETE FROM pools 
                WHERE id IN ({placeholders})
            ''', orphaned_ids)
            
            deleted_count = cursor.rowcount
            print(f'Deleted {deleted_count} orphaned pool entries')
        
        # Check for pools that have data but incomplete metadata
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
            HAVING ohlcv_count > 0 OR trade_count > 0 OR watchlist_count > 0
        ''')
        
        pools_with_data = cursor.fetchall()
        if pools_with_data:
            print(f'Found {len(pools_with_data)} pools with incomplete metadata but existing data:')
            for pool in pools_with_data:
                print(f'  Pool {pool[0]}: {pool[1]} OHLCV records, {pool[2]} trades, {pool[3]} watchlist entries')
        
        # Commit changes
        conn.commit()
        
        # Final count
        cursor.execute('SELECT COUNT(*) FROM pools')
        final_count = cursor.fetchone()[0]
        print(f'Final pool count: {final_count}')
        
        conn.close()
        return True
        
    except Exception as e:
        print(f'Error: {e}')
        return False

if __name__ == "__main__":
    cleanup_blank_pools()