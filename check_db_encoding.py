#!/usr/bin/env python3
"""
Check PostgreSQL database encoding and provide fix instructions.
"""
import os
from sqlalchemy import create_engine, text

# Get database URL from environment
db_url = os.getenv('GECKO_DB_URL') or os.getenv('POSTGRES_URL')

if not db_url:
    print("❌ No database URL found in environment variables")
    print("   Set GECKO_DB_URL or POSTGRES_URL")
    exit(1)

print(f"🔍 Checking database encoding for: {db_url.split('@')[1] if '@' in db_url else db_url}")

try:
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Check database encoding
        result = conn.execute(text("""
            SELECT 
                datname as database,
                pg_encoding_to_char(encoding) as encoding,
                datcollate as collate,
                datctype as ctype
            FROM pg_database 
            WHERE datname = current_database()
        """))
        
        row = result.fetchone()
        
        print(f"\n📊 Current Database Configuration:")
        print(f"   Database: {row[0]}")
        print(f"   Encoding: {row[1]}")
        print(f"   Collate:  {row[2]}")
        print(f"   Ctype:    {row[3]}")
        
        if row[1] != 'UTF8':
            print(f"\n⚠️  Database encoding is {row[1]}, not UTF8!")
            print(f"\n🔧 To fix this, you need to recreate the database with UTF8 encoding:")
            print(f"\n   1. Backup your data first:")
            print(f"      pg_dump -U gecko_collector -d {row[0]} > backup.sql")
            print(f"\n   2. Drop and recreate the database:")
            print(f"      DROP DATABASE {row[0]};")
            print(f"      CREATE DATABASE {row[0]} WITH ENCODING 'UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8';")
            print(f"\n   3. Restore your data:")
            print(f"      psql -U gecko_collector -d {row[0]} < backup.sql")
            print(f"\n   Or use the fix script: python fix_db_encoding.py")
        else:
            print(f"\n✅ Database encoding is already UTF8 - good to go!")
            
except Exception as e:
    print(f"\n❌ Error checking database: {e}")
    print(f"\n   Make sure PostgreSQL is running and credentials are correct")
