#!/usr/bin/env python3
"""
Comprehensive database backup script for GeckoTerminal Collector.
Creates full database backups with compression and metadata.
"""

import os
import sys
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import json
import gzip
import shutil
from typing import Dict, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """Manages database backups with multiple strategies."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize backup manager with configuration."""
        self.config_path = config_path
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
        
    async def create_full_backup(self, backup_name: Optional[str] = None, compress: bool = True) -> str:
        """
        Create a full database backup.
        
        Args:
            backup_name: Custom backup name (optional)
            compress: Whether to compress the backup
            
        Returns:
            Path to the created backup
        """
        try:
            from gecko_terminal_collector.config.loader import ConfigLoader
            
            # Load configuration
            config_loader = ConfigLoader()
            config = config_loader.load_config(self.config_path)
            
            # Generate backup name
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"gecko_db_backup_{timestamp}"
            
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            print(f"🗄️  Creating database backup: {backup_name}")
            print(f"📁 Backup directory: {backup_path}")
            print("-" * 60)
            
            # Parse database URL
            db_url = config.database.url
            db_info = self._parse_database_url(db_url)
            
            if db_info['type'] == 'postgresql':
                await self._create_postgresql_backup(db_info, backup_path, compress)
            elif db_info['type'] == 'sqlite':
                await self._create_sqlite_backup(db_info, backup_path, compress)
            else:
                raise ValueError(f"Unsupported database type: {db_info['type']}")
            
            # Create backup metadata
            await self._create_backup_metadata(backup_path, db_info, config)
            
            # Create backup summary
            backup_size = self._get_directory_size(backup_path)
            
            print(f"✅ Backup completed successfully!")
            print(f"📊 Backup size: {self._format_size(backup_size)}")
            print(f"📁 Location: {backup_path.absolute()}")
            
            return str(backup_path.absolute())
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise
    
    async def _create_postgresql_backup(self, db_info: Dict, backup_path: Path, compress: bool):
        """Create PostgreSQL backup using pg_dump."""
        
        print("🐘 Creating PostgreSQL backup...")
        
        # Set environment variables for pg_dump
        env = os.environ.copy()
        env['PGPASSWORD'] = db_info['password']
        
        # Create schema backup
        schema_file = backup_path / 'schema.sql'
        print("  📋 Backing up database schema...")
        
        schema_cmd = [
            'pg_dump',
            '-h', db_info['host'],
            '-p', str(db_info['port']),
            '-U', db_info['username'],
            '-d', db_info['database'],
            '--schema-only',
            '--no-owner',
            '--no-privileges',
            '-f', str(schema_file)
        ]
        
        result = subprocess.run(schema_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Schema backup failed: {result.stderr}")
        
        # Compress schema if requested
        if compress:
            await self._compress_file(schema_file)
        
        # Create data backup for each table
        tables = await self._get_postgresql_tables(db_info)
        
        for table in tables:
            print(f"  📊 Backing up table: {table}")
            
            table_file = backup_path / f'{table}_data.sql'
            
            data_cmd = [
                'pg_dump',
                '-h', db_info['host'],
                '-p', str(db_info['port']),
                '-U', db_info['username'],
                '-d', db_info['database'],
                '--data-only',
                '--no-owner',
                '--no-privileges',
                '-t', table,
                '-f', str(table_file)
            ]
            
            result = subprocess.run(data_cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"Failed to backup table {table}: {result.stderr}")
                continue
            
            # Compress table data if requested
            if compress:
                await self._compress_file(table_file)
        
        # Create full backup as well
        print("  🗄️  Creating complete database dump...")
        full_backup_file = backup_path / 'full_backup.sql'
        
        full_cmd = [
            'pg_dump',
            '-h', db_info['host'],
            '-p', str(db_info['port']),
            '-U', db_info['username'],
            '-d', db_info['database'],
            '--no-owner',
            '--no-privileges',
            '-f', str(full_backup_file)
        ]
        
        result = subprocess.run(full_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Full backup failed: {result.stderr}")
        elif compress:
            await self._compress_file(full_backup_file)
    
    async def _create_sqlite_backup(self, db_info: Dict, backup_path: Path, compress: bool):
        """Create SQLite backup."""
        
        print("🗃️  Creating SQLite backup...")
        
        db_file = Path(db_info['path'])
        if not db_file.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_file}")
        
        # Copy the database file
        backup_file = backup_path / 'database.sqlite'
        shutil.copy2(db_file, backup_file)
        
        print(f"  📁 Copied database file: {backup_file}")
        
        # Compress if requested
        if compress:
            await self._compress_file(backup_file)
        
        # Also create SQL dump for portability
        sql_dump_file = backup_path / 'database_dump.sql'
        
        try:
            import sqlite3
            
            with sqlite3.connect(db_file) as conn:
                with open(sql_dump_file, 'w') as f:
                    for line in conn.iterdump():
                        f.write(f'{line}\n')
            
            print(f"  📄 Created SQL dump: {sql_dump_file}")
            
            if compress:
                await self._compress_file(sql_dump_file)
                
        except Exception as e:
            logger.warning(f"Failed to create SQL dump: {e}")
    
    async def _get_postgresql_tables(self, db_info: Dict) -> List[str]:
        """Get list of tables in PostgreSQL database."""
        try:
            from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
            from gecko_terminal_collector.config.models import DatabaseConfig
            
            # Create database config
            db_config = DatabaseConfig(
                url=f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['host']}:{db_info['port']}/{db_info['database']}"
            )
            
            # Initialize database manager
            db_manager = SQLAlchemyDatabaseManager(db_config)
            await db_manager.initialize()
            
            # Get table names
            with db_manager.connection.get_session() as session:
                result = session.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in result.fetchall()]
            
            await db_manager.close()
            return tables
            
        except Exception as e:
            logger.warning(f"Failed to get table list: {e}")
            # Return common tables as fallback
            return [
                'dexes', 'tokens', 'pools', 'trades', 'ohlcv_data',
                'watchlist', 'collection_metadata', 'discovery_metadata',
                'new_pools_history'
            ]
    
    async def _create_backup_metadata(self, backup_path: Path, db_info: Dict, config):
        """Create backup metadata file."""
        
        metadata = {
            'backup_info': {
                'created_at': datetime.now().isoformat(),
                'backup_type': 'full_database',
                'database_type': db_info['type'],
                'database_name': db_info.get('database', db_info.get('path')),
                'host': db_info.get('host'),
                'port': db_info.get('port')
            },
            'system_info': {
                'python_version': sys.version,
                'platform': sys.platform,
                'backup_script_version': '1.0.0'
            },
            'config_snapshot': {
                'collection_intervals': config.intervals.__dict__ if hasattr(config, 'intervals') else {},
                'new_pools_config': config.new_pools.__dict__ if hasattr(config, 'new_pools') else {},
                'database_config': {
                    'pool_size': config.database.pool_size,
                    'timeout': config.database.timeout
                }
            }
        }
        
        # Get table statistics if possible
        try:
            table_stats = await self._get_table_statistics(db_info)
            metadata['table_statistics'] = table_stats
        except Exception as e:
            logger.warning(f"Failed to get table statistics: {e}")
        
        metadata_file = backup_path / 'backup_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        print(f"  📋 Created metadata file: {metadata_file}")
    
    async def _get_table_statistics(self, db_info: Dict) -> Dict:
        """Get table row counts and sizes."""
        try:
            from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
            from gecko_terminal_collector.config.models import DatabaseConfig
            
            # Create database config
            db_config = DatabaseConfig(
                url=f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['host']}:{db_info['port']}/{db_info['database']}"
            )
            
            # Initialize database manager
            db_manager = SQLAlchemyDatabaseManager(db_config)
            await db_manager.initialize()
            
            stats = {}
            
            with db_manager.connection.get_session() as session:
                # Get table sizes and row counts
                result = session.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        attname,
                        n_distinct,
                        correlation
                    FROM pg_stats 
                    WHERE schemaname = 'public'
                    ORDER BY tablename, attname
                """)
                
                # Get row counts for each table
                tables = await self._get_postgresql_tables(db_info)
                for table in tables:
                    try:
                        count_result = session.execute(f"SELECT COUNT(*) FROM {table}")
                        row_count = count_result.scalar()
                        stats[table] = {'row_count': row_count}
                    except Exception as e:
                        logger.warning(f"Failed to count rows in {table}: {e}")
                        stats[table] = {'row_count': 'unknown'}
            
            await db_manager.close()
            return stats
            
        except Exception as e:
            logger.warning(f"Failed to get table statistics: {e}")
            return {}
    
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
    
    async def _compress_file(self, file_path: Path):
        """Compress a file using gzip."""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove original file
        file_path.unlink()
        
        print(f"    🗜️  Compressed: {compressed_path.name}")
    
    def _get_directory_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total_size = 0
        for file_path in path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    async def list_backups(self) -> List[Dict]:
        """List available backups with metadata."""
        backups = []
        
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / 'backup_metadata.json'
                
                backup_info = {
                    'name': backup_dir.name,
                    'path': str(backup_dir.absolute()),
                    'created_at': 'unknown',
                    'size': self._format_size(self._get_directory_size(backup_dir))
                }
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                        backup_info.update(metadata.get('backup_info', {}))
                    except Exception as e:
                        logger.warning(f"Failed to read metadata for {backup_dir.name}: {e}")
                
                backups.append(backup_info)
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return backups


async def main():
    """Main backup script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create database backup for GeckoTerminal Collector")
    parser.add_argument('--name', type=str, help='Custom backup name')
    parser.add_argument('--no-compress', action='store_true', help='Disable compression')
    parser.add_argument('--config', type=str, default='config.yaml', help='Configuration file path')
    parser.add_argument('--list', action='store_true', help='List existing backups')
    
    args = parser.parse_args()
    
    backup_manager = DatabaseBackupManager(args.config)
    
    if args.list:
        print("📋 Available Backups")
        print("=" * 60)
        
        backups = await backup_manager.list_backups()
        
        if not backups:
            print("No backups found.")
            return
        
        for backup in backups:
            print(f"Name: {backup['name']}")
            print(f"  Created: {backup.get('created_at', 'unknown')}")
            print(f"  Size: {backup['size']}")
            print(f"  Path: {backup['path']}")
            print()
        
        return
    
    try:
        backup_path = await backup_manager.create_full_backup(
            backup_name=args.name,
            compress=not args.no_compress
        )
        
        print(f"\n🎉 Backup completed successfully!")
        print(f"📁 Backup location: {backup_path}")
        print(f"\n💡 To restore this backup later, use:")
        print(f"   gecko-cli restore {backup_path}")
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())