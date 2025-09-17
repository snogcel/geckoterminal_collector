#!/usr/bin/env python3
"""
Simple database backup script that works without external tools.
Creates SQL dumps using Python database connections.
"""

import asyncio
import sys
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SimpleDatabaseBackup:
    """Simple database backup using Python database connections."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize backup manager."""
        self.config_path = config_path
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
        
    async def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Create a simple database backup."""
        try:
            from gecko_terminal_collector.config.manager import ConfigManager
            from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
            
            # Load configuration
            config_manager = ConfigManager(self.config_path)
            config = config_manager.load_config()
            
            # Generate backup name
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"simple_backup_{timestamp}"
            
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            print(f"🗄️  Creating simple database backup: {backup_name}")
            print(f"📁 Backup directory: {backup_path}")
            print("-" * 60)
            
            # Initialize database manager
            db_manager = SQLAlchemyDatabaseManager(config.database)
            await db_manager.initialize()
            
            # Get table information
            tables_info = await self._get_table_info(db_manager)
            
            # Create backup metadata
            metadata = {
                'backup_info': {
                    'created_at': datetime.now().isoformat(),
                    'backup_type': 'simple_python_backup',
                    'database_type': 'postgresql' if 'postgresql' in config.database.url else 'sqlite',
                    'tables_backed_up': list(tables_info.keys())
                },
                'table_statistics': tables_info
            }
            
            # Save table data as JSON
            total_records = 0
            for table_name, info in tables_info.items():
                if info['row_count'] > 0:
                    print(f"  📊 Backing up table: {table_name} ({info['row_count']} records)")
                    
                    # Export table data
                    table_data = await self._export_table_data(db_manager, table_name)
                    
                    # Save as compressed JSON
                    table_file = backup_path / f"{table_name}_data.json.gz"
                    with gzip.open(table_file, 'wt', encoding='utf-8') as f:
                        json.dump(table_data, f, indent=2, default=str)
                    
                    total_records += len(table_data)
                else:
                    print(f"  📊 Skipping empty table: {table_name}")
            
            # Save metadata
            metadata_file = backup_path / 'backup_metadata.json'
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            await db_manager.close()
            
            # Calculate backup size
            backup_size = self._get_directory_size(backup_path)
            
            print(f"\n✅ Backup completed successfully!")
            print(f"📊 Total records backed up: {total_records:,}")
            print(f"📁 Backup size: {self._format_size(backup_size)}")
            print(f"📁 Location: {backup_path.absolute()}")
            
            return str(backup_path.absolute())
            
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            raise
    
    async def _get_table_info(self, db_manager) -> Dict:
        """Get information about database tables."""
        tables_info = {}
        
        # List of tables to backup
        table_names = [
            'dexes', 'tokens', 'pools', 'trades', 'ohlcv_data',
            'watchlist', 'collection_metadata', 'discovery_metadata',
            'new_pools_history'
        ]
        
        with db_manager.connection.get_session() as session:
            for table_name in table_names:
                try:
                    from sqlalchemy import text
                    # Get row count
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    row_count = result.scalar()
                    
                    tables_info[table_name] = {
                        'row_count': row_count,
                        'backed_up': row_count > 0
                    }
                    
                except Exception as e:
                    print(f"  ⚠️  Could not access table {table_name}: {e}")
                    tables_info[table_name] = {
                        'row_count': 0,
                        'backed_up': False,
                        'error': str(e)
                    }
        
        return tables_info
    
    async def _export_table_data(self, db_manager, table_name: str) -> List[Dict]:
        """Export table data as list of dictionaries."""
        with db_manager.connection.get_session() as session:
            try:
                from sqlalchemy import text
                # Get all records from table
                result = session.execute(text(f"SELECT * FROM {table_name}"))
                
                # Convert to list of dictionaries
                columns = result.keys()
                rows = result.fetchall()
                
                table_data = []
                for row in rows:
                    row_dict = {}
                    for i, column in enumerate(columns):
                        value = row[i]
                        # Convert special types to strings for JSON serialization
                        if hasattr(value, 'isoformat'):  # datetime
                            value = value.isoformat()
                        elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                            value = str(value)
                        row_dict[column] = value
                    table_data.append(row_dict)
                
                return table_data
                
            except Exception as e:
                print(f"  ❌ Error exporting {table_name}: {e}")
                return []
    
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
        """List available backups."""
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
                        print(f"Warning: Could not read metadata for {backup_dir.name}: {e}")
                
                backups.append(backup_info)
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return backups


async def main():
    """Main backup script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create simple database backup")
    parser.add_argument('--name', type=str, help='Custom backup name')
    parser.add_argument('--list', action='store_true', help='List existing backups')
    parser.add_argument('--config', type=str, default='config.yaml', help='Configuration file path')
    
    args = parser.parse_args()
    
    backup_manager = SimpleDatabaseBackup(args.config)
    
    if args.list:
        print("📋 Available Simple Backups")
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
        backup_path = await backup_manager.create_backup(backup_name=args.name)
        
        print(f"\n🎉 Simple backup completed successfully!")
        print(f"📁 Backup location: {backup_path}")
        print(f"\n💡 This backup contains JSON exports of all table data.")
        print(f"   It can be used for data recovery and analysis.")
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())