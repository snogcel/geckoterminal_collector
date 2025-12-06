#!/usr/bin/env python3
"""
Add signal analysis fields to new_pools_history table (SQLite version).
"""
import sqlite3
import sys
from pathlib import Path

def migrate_sqlite_database(db_path: str):
    """
    Add signal analysis fields to SQLite database.
    
    Args:
        db_path: Path to SQLite database file
    """
    print(f"🔄 Migrating SQLite database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='new_pools_history'
        """)
        
        if not cursor.fetchone():
            print("❌ Table 'new_pools_history' does not exist")
            return False
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(new_pools_history)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        columns_to_add = [
            ('signal_score', 'NUMERIC(10, 4)'),
            ('volume_trend', 'VARCHAR(20)'),
            ('liquidity_trend', 'VARCHAR(20)'),
            ('momentum_indicator', 'NUMERIC(10, 4)'),
            ('activity_score', 'NUMERIC(10, 4)'),
            ('volatility_score', 'NUMERIC(10, 4)')
        ]
        
        added_count = 0
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"  Adding column: {column_name}")
                cursor.execute(f"""
                    ALTER TABLE new_pools_history 
                    ADD COLUMN {column_name} {column_type}
                """)
                added_count += 1
            else:
                print(f"  ✓ Column already exists: {column_name}")
        
        # Create indexes
        indexes = [
            ('idx_new_pools_history_signal_score', 'signal_score'),
            ('idx_new_pools_history_volume_trend', 'volume_trend'),
            ('idx_new_pools_history_activity_score', 'activity_score')
        ]
        
        for index_name, column_name in indexes:
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON new_pools_history ({column_name})
                """)
                print(f"  ✓ Created index: {index_name}")
            except sqlite3.Error as e:
                print(f"  ⚠️  Index {index_name} may already exist: {e}")
        
        conn.commit()
        conn.close()
        
        if added_count > 0:
            print(f"✅ Migration complete! Added {added_count} columns")
        else:
            print(f"✅ All columns already exist, no changes needed")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default to common SQLite database locations
        possible_paths = [
            "gecko_data.db",
            "data/gecko_data.db",
            "test_nautilus.db"
        ]
        
        db_path = None
        for path in possible_paths:
            if Path(path).exists():
                db_path = path
                break
        
        if not db_path:
            print("❌ No database file found. Usage: python add_signal_fields_sqlite.py <db_path>")
            sys.exit(1)
    
    success = migrate_sqlite_database(db_path)
    sys.exit(0 if success else 1)
