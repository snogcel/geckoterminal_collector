#!/usr/bin/env python3
"""
Quick backup script - creates a timestamped backup of the database.
"""

import asyncio
import sys
from datetime import datetime
from create_database_backup import DatabaseBackupManager


async def create_quick_backup():
    """Create a quick timestamped backup."""
    
    print("🚀 Quick Database Backup")
    print("=" * 40)
    
    try:
        # Initialize backup manager
        backup_manager = DatabaseBackupManager('config.yaml')
        
        # Generate timestamped backup name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"quick_backup_{timestamp}"
        
        print(f"📅 Creating backup: {backup_name}")
        print("⏳ This may take a few minutes...")
        print()
        
        # Create backup
        backup_path = await backup_manager.create_full_backup(
            backup_name=backup_name,
            compress=True
        )
        
        print(f"\n🎉 Quick backup completed!")
        print(f"📁 Location: {backup_path}")
        print(f"\n💾 Backup includes:")
        print("  • Complete database schema")
        print("  • All table data (compressed)")
        print("  • Backup metadata and statistics")
        print("  • System configuration snapshot")
        
        print(f"\n🔄 To restore this backup:")
        print(f"   python restore_database_backup.py {backup_path}")
        print(f"   # OR")
        print(f"   gecko-cli restore {backup_path}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return 1


if __name__ == "__main__":
    print("Starting quick backup...")
    exit_code = asyncio.run(create_quick_backup())
    sys.exit(exit_code)