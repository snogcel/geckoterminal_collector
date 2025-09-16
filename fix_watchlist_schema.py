#!/usr/bin/env python3

import psycopg2

def fix_watchlist_schema():
    """Fix the watchlist table schema to match the model definition."""
    
    # Database connection details from config.yaml
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="gecko_terminal_collector",
        user="gecko_collector",
        password="12345678!"
    )
    
    cur = conn.cursor()
    
    try:
        print("Fixing watchlist table schema...")
        
        # 1. Rename added_at to created_at
        print("1. Renaming added_at column to created_at...")
        cur.execute("ALTER TABLE watchlist RENAME COLUMN added_at TO created_at;")
        
        # 2. Add updated_at column
        print("2. Adding updated_at column...")
        cur.execute("""
            ALTER TABLE watchlist 
            ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE 
            DEFAULT NOW();
        """)
        
        # 3. Add metadata_json column
        print("3. Adding metadata_json column...")
        cur.execute("""
            ALTER TABLE watchlist 
            ADD COLUMN metadata_json JSONB 
            DEFAULT '{}';
        """)
        
        # 4. Update created_at to use timezone
        print("4. Updating created_at to use timezone...")
        cur.execute("""
            ALTER TABLE watchlist 
            ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
            USING created_at AT TIME ZONE 'UTC';
        """)
        
        # 5. Set default values for created_at
        print("5. Setting default for created_at...")
        cur.execute("""
            ALTER TABLE watchlist 
            ALTER COLUMN created_at SET DEFAULT NOW();
        """)
        
        # 6. Update is_active to have proper default
        print("6. Setting default for is_active...")
        cur.execute("""
            ALTER TABLE watchlist 
            ALTER COLUMN is_active SET DEFAULT TRUE;
        """)
        
        # 7. Update existing NULL values
        print("7. Updating NULL values...")
        cur.execute("""
            UPDATE watchlist 
            SET created_at = NOW() 
            WHERE created_at IS NULL;
        """)
        
        cur.execute("""
            UPDATE watchlist 
            SET updated_at = NOW() 
            WHERE updated_at IS NULL;
        """)
        
        cur.execute("""
            UPDATE watchlist 
            SET is_active = TRUE 
            WHERE is_active IS NULL;
        """)
        
        # Commit all changes
        conn.commit()
        print("✅ Watchlist schema updated successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_watchlist_schema()