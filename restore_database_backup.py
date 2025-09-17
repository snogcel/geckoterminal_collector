#!/usr/bin/env python3
"""
Database restore script for GeckoTerminal Collector backups.
"""

import os
import sys
import asyncio
import logging
import subprocess
import json
import gzip
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseRestoreManager:
    """Manages database restoration from backups."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize restore manager."""
        self.config_path = config_path
        
    async def restore_backup(self, backup_path: str, verify: bool = True, overwrite: bool = False) -> bool:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup directory
            verify: Whether to verify backup before restoring
            overwrite: Whether to overwrite existing data
            
        Returns:
            True if restore was successful
        """
        try:
            backup_dir = Path(backup_path)
            
            if not backup_dir.exists():
                raise FileNotFoundError(f"Backup directory not found: {backup_path}")
            
            print(f"🔄 Restoring database from backup...")
            print(f"📁 Backup location: {backup_path}")
            print("-" * 60)
            
            # Load backup metadata
            metadata = await self._load_backup_metadata(backup_dir)
            
            if verify:
                print("🔍 Verifying backup integrity...")
                if not await self._verify_backup(backup_dir, metadata):
                    raise RuntimeError("Backup verification failed")
                print("✅ Backup verification passed")
            
            # Load current configuration
            from gecko_terminal_collector.config.loader import ConfigLoader
            config_loader = ConfigLoader()
            config = config_loader.load_config(self.config_path)
            
            # Parse database info
            db_info = self._parse_database_url(config.database.url)
            
            # Confirm restore operation
            if not overwrite:
                print(f"\n⚠️  WARNING: This will restore data to database:")
                print(f"   Database: {db_info.get('database', db_info.get('path'))}")
                print(f"   Host: {db_info.get('host', 'local file')}")
                
                response = input("\nDo you want to continue? (yes/no): ").lower().strip()
                if response not in ['yes', 'y']:
                    print("Restore cancelled by user.")
                    return False
            
            # Perform restore based on database type
            if db_info['type'] == 'postgresql':
                await self._restore_postgresql(backup_dir, db_info, metadata, overwrite)
            elif db_info['type'] == 'sqlite':
                await self._restore_sqlite(backup_dir, db_info, metadata, overwrite)
            else:
                raise ValueError(f"Unsupported database type: {db_info['type']}")
            
            print(f"\n✅ Database restore completed successfully!")
            print(f"📊 Restored from backup created: {metadata.get('backup_info', {}).get('created_at', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise
    
    async def _load_backup_metadata(self, backup_dir: Path) -> Dict:
        """Load backup metadata."""
        metadata_file = backup_dir / 'backup_metadata.json'
        
        if not metadata_file.exists():
            logger.warning("No metadata file found, proceeding without verification")
            return {}
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        print(f"📋 Backup Information:")
        backup_info = metadata.get('backup_info', {})
        print(f"  Created: {backup_info.get('created_at', 'unknown')}")
        print(f"  Database: {backup_info.get('database_name', 'unknown')}")
        print(f"  Type: {backup_info.get('database_type', 'unknown')}")
        
        return metadata
    
    async def _verify_backup(self, backup_dir: Path, metadata: Dict) -> bool:
        """Verify backup integrity."""
        try:
            # Check for required files
            required_files = ['schema.sql', 'full_backup.sql']
            
            for file_name in required_files:
                file_path = backup_dir / file_name
                compressed_path = backup_dir / f"{file_name}.gz"
                
                if not file_path.exists() and not compressed_path.exists():
                    logger.warning(f"Missing backup file: {file_name}")
                    return False
            
            # Verify table data files exist
            table_stats = metadata.get('table_statistics', {})
            for table_name in table_stats.keys():
                table_file = backup_dir / f"{table_name}_data.sql"
                compressed_table_file = backup_dir / f"{table_name}_data.sql.gz"
                
                if not table_file.exists() and not compressed_table_file.exists():
                    logger.warning(f"Missing table data file: {table_name}_data.sql")
            
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    async def _restore_postgresql(self, backup_dir: Path, db_info: Dict, metadata: Dict, overwrite: bool):
        """Restore PostgreSQL database."""
        
        print("🐘 Restoring PostgreSQL database...")
        
        # Set environment variables
        env = os.environ.copy()
        env['PGPASSWORD'] = db_info['password']
        
        # Drop and recreate database if overwrite is True
        if overwrite:
            print("  🗑️  Dropping existing database...")
            
            # Connect to postgres database to drop the target database
            drop_cmd = [
                'psql',
                '-h', db_info['host'],
                '-p', str(db_info['port']),
                '-U', db_info['username'],
                '-d', 'postgres',
                '-c', f"DROP DATABASE IF EXISTS {db_info['database']}"
            ]
            
            result = subprocess.run(drop_cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"Failed to drop database: {result.stderr}")
            
            # Create new database
            print("  🏗️  Creating new database...")
            create_cmd = [
                'psql',
                '-h', db_info['host'],
                '-p', str(db_info['port']),
                '-U', db_info['username'],
                '-d', 'postgres',
                '-c', f"CREATE DATABASE {db_info['database']}"
            ]
            
            result = subprocess.run(create_cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create database: {result.stderr}")
        
        # Restore from full backup
        full_backup_file = backup_dir / 'full_backup.sql'
        compressed_backup_file = backup_dir / 'full_backup.sql.gz'
        
        if compressed_backup_file.exists():
            print("  📦 Decompressing backup file...")
            with gzip.open(compressed_backup_file, 'rb') as f_in:
                with open(full_backup_file, 'wb') as f_out:
                    f_out.write(f_in.read())
        
        if full_backup_file.exists():
            print("  🔄 Restoring database from full backup...")
            
            restore_cmd = [
                'psql',
                '-h', db_info['host'],
                '-p', str(db_info['port']),
                '-U', db_info['username'],
                '-d', db_info['database'],
                '-f', str(full_backup_file)
            ]
            
            result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Database restore failed: {result.stderr}")
            
            # Clean up decompressed file
            if compressed_backup_file.exists():
                full_backup_file.unlink()
        else:
            raise FileNotFoundError("No backup file found to restore from")
    
    async def _restore_sqlite(self, backup_dir: Path, db_info: Dict, metadata: Dict, overwrite: bool):
        """Restore SQLite database."""
        
        print("🗃️  Restoring SQLite database...")
        
        db_file = Path(db_info['path'])
        
        # Backup existing database if it exists
        if db_file.exists() and not overwrite:
            backup_existing = db_file.with_suffix('.bak')
            print(f"  💾 Backing up existing database to: {backup_existing}")
            import shutil
            shutil.copy2(db_file, backup_existing)
        elif db_file.exists() and overwrite:
            print("  🗑️  Removing existing database...")
            db_file.unlink()
        
        # Restore from backup
        backup_db_file = backup_dir / 'database.sqlite'
        compressed_db_file = backup_dir / 'database.sqlite.gz'
        
        if compressed_db_file.exists():
            print("  📦 Decompressing database file...")
            with gzip.open(compressed_db_file, 'rb') as f_in:
                with open(backup_db_file, 'wb') as f_out:
                    f_out.write(f_in.read())
        
        if backup_db_file.exists():
            print("  📁 Copying database file...")
            import shutil
            shutil.copy2(backup_db_file, db_file)
            
            # Clean up decompressed file
            if compressed_db_file.exists():
                backup_db_file.unlink()
        else:
            # Try SQL dump restore
            sql_dump_file = backup_dir / 'database_dump.sql'
            compressed_dump_file = backup_dir / 'database_dump.sql.gz'
            
            if compressed_dump_file.exists():
                print("  📦 Decompressing SQL dump...")
                with gzip.open(compressed_dump_file, 'rb') as f_in:
                    with open(sql_dump_file, 'wb') as f_out:
                        f_out.write(f_in.read())
            
            if sql_dump_file.exists():
                print("  🔄 Restoring from SQL dump...")
                import sqlite3
                
                with sqlite3.connect(db_file) as conn:
                    with open(sql_dump_file) as f:
                        conn.executescript(f.read())
                
                # Clean up decompressed file
                if compressed_dump_file.exists():
                    sql_dump_file.unlink()
            else:
                raise FileNotFoundError("No backup file found to restore from")
    
    def _parse_database_url(self, url: str) -> Dict:
        """Parse database URL into components."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme == 'postgresql':
            return {
                'type': 'postgresql',
                'username': parsed.username,
                'password': parsed.password,
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/')
            }
        elif parsed.scheme == 'sqlite':
            return {
                'type': 'sqlite',
                'path': parsed.path
            }
        else:
            raise ValueError(f"Unsupported database scheme: {parsed.scheme}")


async def main():
    """Main restore script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Restore database from backup")
    parser.add_argument('backup_path', type=str, help='Path to backup directory')
    parser.add_argument('--no-verify', action='store_true', help='Skip backup verification')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing database')
    parser.add_argument('--config', type=str, default='config.yaml', help='Configuration file path')
    
    args = parser.parse_args()
    
    restore_manager = DatabaseRestoreManager(args.config)
    
    try:
        success = await restore_manager.restore_backup(
            backup_path=args.backup_path,
            verify=not args.no_verify,
            overwrite=args.overwrite
        )
        
        if success:
            print(f"\n🎉 Database restore completed successfully!")
            print(f"📁 Restored from: {args.backup_path}")
        else:
            print(f"\n❌ Database restore failed or was cancelled.")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())