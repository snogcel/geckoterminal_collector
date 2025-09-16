#!/usr/bin/env python3

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def recreate_database_schema():
    """Recreate the database schema from scratch using the PostgreSQL models."""
    
    # Database connection details from config.yaml
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="gecko_terminal_collector",
        user="gecko_collector",
        password="12345678!"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cur = conn.cursor()
    
    try:
        print("🗑️  Dropping all existing tables...")
        
        # Drop all tables in the correct order (respecting foreign keys)
        tables_to_drop = [
            'collection_metadata',
            'discovery_metadata', 
            'new_pools_history',
            'watchlist',
            'ohlcv_data',
            'trades',
            'pools',
            'tokens',
            'dexes'
        ]
        
        for table in tables_to_drop:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"  ✅ Dropped {table}")
            except Exception as e:
                print(f"  ⚠️  Could not drop {table}: {e}")
        
        # Drop sequences if they exist
        sequences_to_drop = [
            'watchlist_id_seq',
            'collection_metadata_id_seq',
            'discovery_metadata_id_seq',
            'new_pools_history_id_seq'
        ]
        
        for seq in sequences_to_drop:
            try:
                cur.execute(f"DROP SEQUENCE IF EXISTS {seq} CASCADE;")
                print(f"  ✅ Dropped sequence {seq}")
            except Exception as e:
                print(f"  ⚠️  Could not drop sequence {seq}: {e}")
        
        print("\n🏗️  Creating tables using SQLAlchemy models...")
        
        # Now use SQLAlchemy to create all tables properly
        from gecko_terminal_collector.database.connection import DatabaseConnection
        from gecko_terminal_collector.config.models import DatabaseConfig
        
        # Create database config
        db_config = DatabaseConfig(
            url="postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector"
        )
        
        # Create connection and tables
        db_connection = DatabaseConnection(db_config)
        db_connection.initialize()
        db_connection.create_tables()
        
        print("✅ All tables created successfully!")
        
        # Verify the watchlist table has proper auto-increment
        cur.execute("""
            SELECT column_name, column_default, is_nullable, data_type
            FROM information_schema.columns 
            WHERE table_name = 'watchlist' AND column_name = 'id';
        """)
        id_info = cur.fetchone()
        print(f"\n📋 Watchlist ID column: {id_info}")
        
        # Check if sequence exists
        cur.execute("""
            SELECT sequence_name
            FROM information_schema.sequences 
            WHERE sequence_name LIKE '%watchlist%';
        """)
        sequences = cur.fetchall()
        print(f"📋 Watchlist sequences: {sequences}")
        
        db_connection.close()
        
    except Exception as e:
        print(f"❌ Error recreating schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    recreate_database_schema()