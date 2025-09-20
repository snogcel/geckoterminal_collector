#!/usr/bin/env python3

import psycopg2

def fix_pools_schema():
    """Fix the pools table schema to match the model definition."""
    
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
        print("Fixing pools table schema...")
        
        # 1. Add metadata_json column
        print("1. Adding metadata_json column...")
        cur.execute("""
            ALTER TABLE pools 
            ADD COLUMN metadata_json JSONB 
            DEFAULT '{}';
        """)
        
        # 2. Update timestamp columns to use timezone
        print("2. Updating timestamp columns to use timezone...")
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
            USING created_at AT TIME ZONE 'UTC';
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN last_updated TYPE TIMESTAMP WITH TIME ZONE 
            USING last_updated AT TIME ZONE 'UTC';
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN auto_discovered_at TYPE TIMESTAMP WITH TIME ZONE 
            USING auto_discovered_at AT TIME ZONE 'UTC';
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN last_activity_check TYPE TIMESTAMP WITH TIME ZONE 
            USING last_activity_check AT TIME ZONE 'UTC';
        """)
        
        # 3. Set default values
        print("3. Setting default values...")
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN created_at SET DEFAULT NOW();
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN last_updated SET DEFAULT NOW();
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN reserve_usd SET DEFAULT 0;
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN discovery_source SET DEFAULT 'manual';
        """)
        
        cur.execute("""
            ALTER TABLE pools 
            ALTER COLUMN collection_priority SET DEFAULT 'normal';
        """)
        
        # Commit all changes
        conn.commit()
        print("✅ Pools schema updated successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_pools_schema()