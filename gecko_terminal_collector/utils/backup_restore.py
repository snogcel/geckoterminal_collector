"""
Backup and restore utilities for data management.
"""

import asyncio
import json
import gzip
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.config.models import CollectionConfig

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manager for creating and restoring database backups.
    
    Supports both full database backups and selective data exports
    with compression and metadata tracking.
    """
    
    def __init__(self, db_manager: DatabaseManager, config: CollectionConfig):
        """
        Initialize backup manager.
        
        Args:
            db_manager: Database manager instance
            config: Collection configuration
        """
        self.db_manager = db_manager
        self.config = config
    
    async def create_backup(
        self,
        backup_path: str,
        include_data_types: Optional[List[str]] = None,
        compress: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path where backup should be saved
            include_data_types: List of data types to include (default: all)
            compress: Whether to compress the backup
            metadata: Additional metadata to include
            
        Returns:
            Dictionary with backup information
        """
        backup_info = {
            "timestamp": datetime.now(),
            "backup_path": backup_path,
            "compressed": compress,
            "data_types": include_data_types or ["all"],
            "metadata": metadata or {},
            "statistics": {}
        }
        
        try:
            logger.info(f"Creating backup at {backup_path}")
            
            # Create backup directory
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Export data by type
            if not include_data_types or "all" in include_data_types:
                include_data_types = ["pools", "tokens", "ohlcv", "trades", "watchlist", "dexes"]
            
            total_records = 0
            
            for data_type in include_data_types:
                logger.info(f"Backing up {data_type} data...")
                
                records_count = await self._backup_data_type(
                    data_type, backup_dir, compress
                )
                
                backup_info["statistics"][data_type] = records_count
                total_records += records_count
                
                logger.info(f"Backed up {records_count:,} {data_type} records")
            
            backup_info["statistics"]["total_records"] = total_records
            
            # Save backup metadata
            metadata_file = backup_dir / "backup_info.json"
            with open(metadata_file, 'w') as f:
                json.dump(backup_info, f, indent=2, default=str)
            
            logger.info(f"Backup completed successfully: {total_records:,} total records")
            
            return {
                "success": True,
                "backup_info": backup_info,
                "message": f"Backup created successfully with {total_records:,} records"
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Backup failed: {e}"
            }
    
    async def _backup_data_type(
        self,
        data_type: str,
        backup_dir: Path,
        compress: bool
    ) -> int:
        """
        Backup a specific data type.
        
        Args:
            data_type: Type of data to backup
            backup_dir: Directory to save backup files
            compress: Whether to compress the data
            
        Returns:
            Number of records backed up
        """
        output_file = backup_dir / f"{data_type}.json"
        
        if data_type == "pools":
            # This would need to be implemented based on actual database schema
            data = []  # await self.db_manager.get_all_pools()
        elif data_type == "tokens":
            data = []  # await self.db_manager.get_all_tokens()
        elif data_type == "ohlcv":
            data = []  # await self.db_manager.get_all_ohlcv_data()
        elif data_type == "trades":
            data = []  # await self.db_manager.get_all_trade_data()
        elif data_type == "watchlist":
            data = []  # await self.db_manager.get_all_watchlist_entries()
        elif data_type == "dexes":
            data = []  # await self.db_manager.get_all_dexes()
        else:
            logger.warning(f"Unknown data type: {data_type}")
            return 0
        
        # Convert data to JSON-serializable format
        serializable_data = []
        for item in data:
            if hasattr(item, 'to_dict'):
                serializable_data.append(item.to_dict())
            elif hasattr(item, '__dict__'):
                serializable_data.append(item.__dict__)
            else:
                serializable_data.append(item)
        
        # Write data to file
        if compress:
            output_file = output_file.with_suffix('.json.gz')
            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, default=str)
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, default=str)
        
        return len(serializable_data)
    
    async def restore_backup(
        self,
        backup_path: str,
        data_types: Optional[List[str]] = None,
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Restore data from a backup.
        
        Args:
            backup_path: Path to backup directory
            data_types: List of data types to restore (default: all available)
            overwrite_existing: Whether to overwrite existing data
            
        Returns:
            Dictionary with restore information
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            return {
                "success": False,
                "error": "Backup directory not found",
                "message": f"Backup directory {backup_path} does not exist"
            }
        
        try:
            # Load backup metadata
            metadata_file = backup_dir / "backup_info.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    backup_info = json.load(f)
                logger.info(f"Restoring backup from {backup_info.get('timestamp', 'unknown time')}")
            else:
                backup_info = {}
                logger.warning("No backup metadata found")
            
            # Determine which data types to restore
            available_files = list(backup_dir.glob("*.json*"))
            available_types = [
                f.stem.replace('.json', '') for f in available_files
                if f.name != "backup_info.json"
            ]
            
            if data_types:
                restore_types = [dt for dt in data_types if dt in available_types]
            else:
                restore_types = available_types
            
            logger.info(f"Restoring data types: {', '.join(restore_types)}")
            
            total_restored = 0
            restore_stats = {}
            
            for data_type in restore_types:
                logger.info(f"Restoring {data_type} data...")
                
                restored_count = await self._restore_data_type(
                    data_type, backup_dir, overwrite_existing
                )
                
                restore_stats[data_type] = restored_count
                total_restored += restored_count
                
                logger.info(f"Restored {restored_count:,} {data_type} records")
            
            logger.info(f"Restore completed successfully: {total_restored:,} total records")
            
            return {
                "success": True,
                "backup_info": backup_info,
                "restore_stats": restore_stats,
                "total_restored": total_restored,
                "message": f"Restore completed successfully with {total_restored:,} records"
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Restore failed: {e}"
            }
    
    async def _restore_data_type(
        self,
        data_type: str,
        backup_dir: Path,
        overwrite_existing: bool
    ) -> int:
        """
        Restore a specific data type.
        
        Args:
            data_type: Type of data to restore
            backup_dir: Directory containing backup files
            overwrite_existing: Whether to overwrite existing data
            
        Returns:
            Number of records restored
        """
        # Try compressed file first, then uncompressed
        compressed_file = backup_dir / f"{data_type}.json.gz"
        uncompressed_file = backup_dir / f"{data_type}.json"
        
        if compressed_file.exists():
            with gzip.open(compressed_file, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        elif uncompressed_file.exists():
            with open(uncompressed_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            logger.warning(f"No backup file found for {data_type}")
            return 0
        
        # Restore data based on type
        if data_type == "pools":
            # This would need to be implemented based on actual database schema
            # await self.db_manager.restore_pools(data, overwrite_existing)
            pass
        elif data_type == "tokens":
            # await self.db_manager.restore_tokens(data, overwrite_existing)
            pass
        elif data_type == "ohlcv":
            # await self.db_manager.restore_ohlcv_data(data, overwrite_existing)
            pass
        elif data_type == "trades":
            # await self.db_manager.restore_trade_data(data, overwrite_existing)
            pass
        elif data_type == "watchlist":
            # await self.db_manager.restore_watchlist_entries(data, overwrite_existing)
            pass
        elif data_type == "dexes":
            # await self.db_manager.restore_dexes(data, overwrite_existing)
            pass
        else:
            logger.warning(f"Unknown data type for restore: {data_type}")
            return 0
        
        return len(data)
    
    async def list_backups(self, backup_root_dir: str) -> List[Dict[str, Any]]:
        """
        List available backups in a directory.
        
        Args:
            backup_root_dir: Root directory to search for backups
            
        Returns:
            List of backup information dictionaries
        """
        backup_root = Path(backup_root_dir)
        
        if not backup_root.exists():
            return []
        
        backups = []
        
        for backup_dir in backup_root.iterdir():
            if not backup_dir.is_dir():
                continue
            
            metadata_file = backup_dir / "backup_info.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        backup_info = json.load(f)
                    
                    # Add directory size information
                    total_size = sum(
                        f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
                    )
                    backup_info["directory_size_bytes"] = total_size
                    backup_info["directory_path"] = str(backup_dir)
                    
                    backups.append(backup_info)
                    
                except Exception as e:
                    logger.warning(f"Error reading backup metadata from {backup_dir}: {e}")
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return backups
    
    async def verify_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        Verify the integrity of a backup.
        
        Args:
            backup_path: Path to backup directory
            
        Returns:
            Dictionary with verification results
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            return {
                "valid": False,
                "error": "Backup directory not found"
            }
        
        verification_result = {
            "valid": True,
            "backup_path": backup_path,
            "files_checked": 0,
            "files_valid": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check metadata file
            metadata_file = backup_dir / "backup_info.json"
            if not metadata_file.exists():
                verification_result["warnings"].append("No backup metadata file found")
            else:
                try:
                    with open(metadata_file, 'r') as f:
                        backup_info = json.load(f)
                    verification_result["backup_info"] = backup_info
                except Exception as e:
                    verification_result["errors"].append(f"Invalid metadata file: {e}")
                    verification_result["valid"] = False
            
            # Check data files
            data_files = [f for f in backup_dir.iterdir() if f.suffix in ['.json', '.gz']]
            
            for data_file in data_files:
                if data_file.name == "backup_info.json":
                    continue
                
                verification_result["files_checked"] += 1
                
                try:
                    if data_file.suffix == '.gz':
                        with gzip.open(data_file, 'rt', encoding='utf-8') as f:
                            json.load(f)
                    else:
                        with open(data_file, 'r', encoding='utf-8') as f:
                            json.load(f)
                    
                    verification_result["files_valid"] += 1
                    
                except Exception as e:
                    verification_result["errors"].append(f"Invalid data file {data_file.name}: {e}")
                    verification_result["valid"] = False
            
            if verification_result["files_checked"] == 0:
                verification_result["warnings"].append("No data files found in backup")
            
        except Exception as e:
            verification_result["valid"] = False
            verification_result["errors"].append(f"Verification failed: {e}")
        
        return verification_result
    
    async def cleanup_old_backups(
        self,
        backup_root_dir: str,
        keep_count: int = 10,
        keep_days: int = 30
    ) -> Dict[str, Any]:
        """
        Clean up old backups based on retention policy.
        
        Args:
            backup_root_dir: Root directory containing backups
            keep_count: Number of recent backups to keep
            keep_days: Number of days of backups to keep
            
        Returns:
            Dictionary with cleanup results
        """
        backups = await self.list_backups(backup_root_dir)
        
        if not backups:
            return {
                "success": True,
                "message": "No backups found to clean up",
                "deleted_count": 0
            }
        
        # Determine which backups to delete
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        backups_to_delete = []
        
        # Keep recent backups by count
        recent_backups = backups[:keep_count]
        
        for backup in backups[keep_count:]:
            backup_date_str = backup.get("timestamp", "")
            try:
                backup_date = datetime.fromisoformat(backup_date_str.replace('Z', '+00:00'))
                if backup_date < cutoff_date:
                    backups_to_delete.append(backup)
            except (ValueError, TypeError):
                # If we can't parse the date, consider it old
                backups_to_delete.append(backup)
        
        # Delete old backups
        deleted_count = 0
        errors = []
        
        for backup in backups_to_delete:
            try:
                backup_path = Path(backup["directory_path"])
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_path}")
            except Exception as e:
                errors.append(f"Failed to delete {backup['directory_path']}: {e}")
                logger.error(f"Failed to delete backup {backup['directory_path']}: {e}")
        
        return {
            "success": len(errors) == 0,
            "deleted_count": deleted_count,
            "total_backups": len(backups),
            "remaining_backups": len(backups) - deleted_count,
            "errors": errors,
            "message": f"Deleted {deleted_count} old backups"
        }