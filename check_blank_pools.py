#!/usr/bin/env python3
"""
Script to check for blank entries in the pools table.
"""

import sqlite3
import sys

def check_blank_pools():
    """Check for blank/null entries in pools table."""
    try:
        # Connect to the database
        conn = sqlite3.connect('gecko_data.db')
        cursor = conn.cursor()
        
        # Check for blank/null entries in pools table
        cursor.execute('''
            SELECT id, address, name, dex_id, base_token_id, quote_token_id 
            FROM pools 
            WHERE id IS NULL OR id = '' 
               OR address IS NULL OR address = ''
               OR name IS NULL OR name = ''
               OR dex_id IS NULL OR dex_id = ''
            LIMIT 10
        ''')
        
        blank_entries = cursor.fetchall()
        
        if blank_entries:
            print('Found blank entries in pools table:')
            for entry in blank_entries:
                print(f'ID: {entry[0]}, Address: {entry[1]}, Name: {entry[2]}, DEX: {entry[3]}, Base Token: {entry[4]}, Quote Token: {entry[5]}')
        else:
            print('No blank entries found in pools table')
        
        # Count total pools
        cursor.execute('SELECT COUNT(*) FROM pools')
        total_count = cursor.fetchone()[0]
        print(f'Total pools in database: {total_count}')
        
        # Check for pools with empty names specifically
        cursor.execute('''
            SELECT COUNT(*) FROM pools 
            WHERE name IS NULL OR name = '' OR TRIM(name) = ''
        ''')
        empty_names = cursor.fetchone()[0]
        print(f'Pools with empty names: {empty_names}')
        
        conn.close()
        
    except Exception as e:
        print(f'Error: {e}')
        return False
    
    return True

if __name__ == "__main__":
    check_blank_pools()