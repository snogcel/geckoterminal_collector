"""
Database migration utilities for the GeckoTerminal collector.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from gecko_terminal_collector.config.models import DatabaseConfig

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Database migration manager using Alembic.
    
    Provides utilities for running database migrations,
    checking migration status, and managing schema versions.
    """
    
    def __init__(self, config: DatabaseConfig, alembic_ini_path: Optional[str] = None):
        """
        Initialize migration manager.
        
        Args:
            config: Database configuration
            alembic_ini_path: Path to alembic.ini file (optional)
        """
        self.config = config
        self.alembic_ini_path = alembic_ini_path or "alembic.ini"
        self.alembic_config = None
        
    def _get_alembic_config(self) -> Config:
        """Get Alembic configuration object."""
        if self.alembic_config is None:
            if not os.path.exists(self.alembic_ini_path):
                raise FileNotFoundError(f"Alembic configuration file not found: {self.alembic_ini_path}")
            
            self.alembic_config = Config(self.alembic_ini_path)
            # Override database URL from config
            self.alembic_config.set_main_option("sqlalchemy.url", self.config.url)
        
        return self.alembic_config
    
    def run_migrations(self, revision: str = "head") -> None:
        """
        Run database migrations to specified revision.
        
        Args:
            revision: Target revision (default: "head" for latest)
        """
        try:
            alembic_cfg = self._get_alembic_config()
            command.upgrade(alembic_cfg, revision)
            logger.info(f"Successfully migrated database to revision: {revision}")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
    
    def downgrade_migrations(self, revision: str) -> None:
        """
        Downgrade database to specified revision.
        
        Args:
            revision: Target revision to downgrade to
        """
        try:
            alembic_cfg = self._get_alembic_config()
            command.downgrade(alembic_cfg, revision)
            logger.info(f"Successfully downgraded database to revision: {revision}")
        except Exception as e:
            logger.error(f"Downgrade failed: {e}")
            raise
    
    def get_current_revision(self) -> Optional[str]:
        """
        Get current database revision.
        
        Returns:
            Current revision string or None if no migrations applied
        """
        try:
            engine = create_engine(self.config.url)
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None
    
    def get_head_revision(self) -> Optional[str]:
        """
        Get head (latest) revision from migration scripts.
        
        Returns:
            Head revision string or None if no migrations found
        """
        try:
            alembic_cfg = self._get_alembic_config()
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            return script_dir.get_current_head()
        except Exception as e:
            logger.error(f"Failed to get head revision: {e}")
            return None
    
    def is_database_up_to_date(self) -> bool:
        """
        Check if database is up to date with latest migrations.
        
        Returns:
            True if database is up to date, False otherwise
        """
        current = self.get_current_revision()
        head = self.get_head_revision()
        
        if current is None and head is None:
            # No migrations exist
            return True
        
        return current == head
    
    def create_migration(self, message: str, autogenerate: bool = True) -> None:
        """
        Create a new migration script.
        
        Args:
            message: Migration message/description
            autogenerate: Whether to auto-generate migration from model changes
        """
        try:
            alembic_cfg = self._get_alembic_config()
            if autogenerate:
                command.revision(alembic_cfg, message=message, autogenerate=True)
            else:
                command.revision(alembic_cfg, message=message)
            logger.info(f"Created new migration: {message}")
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise
    
    def show_migration_history(self) -> None:
        """Show migration history."""
        try:
            alembic_cfg = self._get_alembic_config()
            command.history(alembic_cfg, verbose=True)
        except Exception as e:
            logger.error(f"Failed to show migration history: {e}")
            raise
    
    def initialize_database(self) -> None:
        """
        Initialize database with latest schema.
        
        This method will:
        1. Check if database exists and has migrations
        2. Run migrations if needed
        3. Create initial schema if no migrations exist
        """
        try:
            current_revision = self.get_current_revision()
            head_revision = self.get_head_revision()
            
            if current_revision is None and head_revision is not None:
                # Database exists but no migrations applied
                logger.info("Initializing database with migrations")
                self.run_migrations()
            elif current_revision != head_revision:
                # Database needs to be updated
                logger.info("Updating database to latest schema")
                self.run_migrations()
            else:
                logger.info("Database is up to date")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise


def create_migration_manager(config: DatabaseConfig) -> MigrationManager:
    """
    Factory function to create a migration manager.
    
    Args:
        config: Database configuration
        
    Returns:
        Configured MigrationManager instance
    """
    return MigrationManager(config)