#!/usr/bin/env python3
"""
Fix PostgreSQL database encoding by recreating with UTF8.
WARNING: This will backup, drop, and recreate your database!
"""
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# Get database URL from environment
db_url = os.getenv('GECKO_DB_URL') or os.getenv('POSTGRES_URL')

if not db_url:
    print("❌ No database URL found in environment variables")
    print("   Set GECKO_DB_URL or POSTGRES_URL")
    exit(1)

# Parse database name from URL
db_name = db_url.split('/')[-1].split('?')[0]
base_url = db_url.rsplit('/', 1)[0]

print(f"⚠️  WARNING: This will recreate the database '{db_name}' with UTF8 encoding")
print(f"   All existing data will be backed up first")
print(f"\n   Database: {db_name}")
print(f"   URL: {base_url}/...")

response = input("\n❓ Do you want to continue? (yes/no): ")
if response.lower() != 'yes':
    print("❌ Aborted")
    exit(0)

try:
    # Connect to postgres database (not the target database)
    postgres_url = f"{base_url}/postgres"
    engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    
    print(f"\n📦 Step 1: Backing up database...")
    backup_file = f"backup_{db_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    
    # Use pg_dump for backup
    import subprocess
    
    # Extract connection details
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    
    pg_dump_cmd = [
        'pg_dump',
        '-h', parsed.hostname or 'localhost',
        '-p', str(parsed.port or 5432),
        '-U', parsed.username,
        '-d', db_name,
        '-f', backup_file
    ]
    
    # Set password in environment
    env = os.environ.copy()
    if parsed.password:
        env['PGPASSWORD'] = parsed.password
    
    result = subprocess.run(pg_dump_cmd, env=env, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Backup failed: {result.stderr}")
        exit(1)
    
    print(f"✅ Backup saved to: {backup_file}")
    
    print(f"\n🗑️  Step 2: Dropping old database...")
    with engine.connect() as conn:
        # Terminate existing connections
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{db_name}'
            AND pid <> pg_backend_pid()
        """))
        
        # Drop database
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    
    print(f"✅ Old database dropped")
    
    print(f"\n🔨 Step 3: Creating new database with UTF8 encoding...")
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE DATABASE {db_name}
            WITH ENCODING 'UTF8'
            LC_COLLATE='en_US.UTF-8'
            LC_CTYPE='en_US.UTF-8'
            TEMPLATE=template0
        """))
    
    print(f"✅ New database created with UTF8 encoding")
    
    print(f"\n📥 Step 4: Restoring data from backup...")
    
    psql_cmd = [
        'psql',
        '-h', parsed.hostname or 'localhost',
        '-p', str(parsed.port or 5432),
        '-U', parsed.username,
        '-d', db_name,
        '-f', backup_file
    ]
    
    result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"⚠️  Restore had some warnings: {result.stderr}")
        print(f"   Check the backup file: {backup_file}")
    else:
        print(f"✅ Data restored successfully")
    
    print(f"\n✅ Database encoding fix complete!")
    print(f"   Backup file: {backup_file}")
    print(f"   You can delete the backup once you verify everything works")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print(f"\n   If the database was dropped, restore from backup:")
    print(f"   psql -U {parsed.username} -d {db_name} < {backup_file}")
    sys.exit(1)
