#!/usr/bin/env python3
"""
Simplified migration script to move from SQLite to PostgreSQL.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleDatabaseMigrator:
    """Simple database migrator using direct SQLAlchemy."""
    
    def __init__(self, sqlite_path: str, postgresql_url: str):
        """Initialize the migrator."""
        self.sqlite_path = sqlite_path
        self.postgresql_url = postgresql_url
        
        # Initialize engines
        self.sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
        self.postgresql_engine = create_engine(postgresql_url)
        
        # Session factories
        self.sqlite_session = sessionmaker(bind=self.sqlite_engine)
        self.postgresql_session = sessionmaker(bind=self.postgresql_engine)
        
        # Migration statistics
        self.migration_stats = {
            'start_time': None,
            'end_time': None,
            'tables_migrated': 0,
            'total_records': 0,
            'errors': []
        }
    
    def verify_postgresql_connection(self) -> bool:
        """Verify PostgreSQL connection."""
        try:
            with self.postgresql_engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"✓ PostgreSQL connection verified: {version}")
                return True
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            return False
    
    def analyze_sqlite_data(self) -> Dict[str, int]:
        """Analyze SQLite database."""
        logger.info("Analyzing SQLite database...")
        
        table_counts = {}
        
        with self.sqlite_engine.connect() as conn:
            # Get all table names
            tables_result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """))
            
            tables = [row[0] for row in tables_result]
            
            for table in tables:
                try:
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.fetchone()[0]
                    table_counts[table] = count
                    logger.info(f"  {table}: {count:,} records")
                except Exception as e:
                    logger.warning(f"Could not count {table}: {e}")
                    table_counts[table] = 0
        
        total_records = sum(table_counts.values())
        logger.info(f"Total records to migrate: {total_records:,}")
        
        return table_counts
    
    def create_postgresql_schema(self) -> bool:
        """Create PostgreSQL schema by copying from SQLite with type conversions."""
        try:
            logger.info("Creating PostgreSQL schema...")
            
            # Reflect SQLite schema
            sqlite_metadata = MetaData()
            sqlite_metadata.reflect(bind=self.sqlite_engine)
            
            # Define table creation order based on dependencies
            # Tables without foreign keys first, then tables that depend on them
            table_creation_order = [
                'alembic_version',
                'collection_metadata', 
                'discovery_metadata',
                'execution_history',
                'performance_metrics',
                'system_alerts',
                'dexes',           # No foreign keys
                'tokens',          # No foreign keys  
                'pools',           # Depends on dexes and tokens
                'watchlist',       # Depends on pools
                'new_pools_history', # Depends on pools
                'trades',          # Depends on pools
                'ohlcv_data'       # Depends on pools
            ]
            
            # Create tables directly with SQL to avoid SQLAlchemy issues
            with self.postgresql_engine.begin() as conn:
                # First, create tables in dependency order
                created_tables = set()
                
                for table_name in table_creation_order:
                    if table_name in sqlite_metadata.tables:
                        self._create_single_table(conn, table_name, created_tables)
                
                # Then create any remaining tables not in the predefined order
                for table_name in sqlite_metadata.tables:
                    if table_name not in created_tables:
                        self._create_single_table(conn, table_name, created_tables)
            
            logger.info("✓ PostgreSQL schema created with type conversions")
            return True
            
        except Exception as e:
            logger.error(f"❌ Schema creation failed: {e}")
            return False
    
    def _create_single_table(self, conn, table_name: str, created_tables: set):
        """Create a single table in PostgreSQL."""
        try:
            # Get the CREATE TABLE statement from SQLite
            with self.sqlite_engine.connect() as sqlite_conn:
                create_sql_result = sqlite_conn.execute(text(f"""
                    SELECT sql FROM sqlite_master 
                    WHERE type='table' AND name='{table_name}'
                """))
                
                create_sql_row = create_sql_result.fetchone()
                if not create_sql_row:
                    return
                    
                create_sql = create_sql_row[0]
                
                # Convert SQLite SQL to PostgreSQL SQL
                pg_sql = self._convert_sqlite_to_postgresql_sql(create_sql)
                
                conn.execute(text(pg_sql))
                created_tables.add(table_name)
                logger.info(f"  Created table: {table_name}")
                
        except Exception as e:
            logger.warning(f"  Failed to create {table_name}: {e}")
            # Don't add to created_tables if it failed
    
    def _convert_sqlite_to_postgresql_sql(self, sqlite_sql: str) -> str:
        """Convert SQLite CREATE TABLE SQL to PostgreSQL."""
        # Basic conversions
        pg_sql = sqlite_sql
        
        # Convert data types
        pg_sql = pg_sql.replace('DATETIME', 'TIMESTAMP')
        pg_sql = pg_sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
        # Handle IF NOT EXISTS
        if 'CREATE TABLE' in pg_sql and 'IF NOT EXISTS' not in pg_sql:
            pg_sql = pg_sql.replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS')
        
        return pg_sql
    
    def migrate_table_data(self, table_name: str, batch_size: int = 1000) -> int:
        """Migrate data from a specific table."""
        logger.info(f"Migrating {table_name} data...")
        
        migrated_count = 0
        
        try:
            # Get table metadata
            sqlite_metadata = MetaData()
            sqlite_metadata.reflect(bind=self.sqlite_engine)
            table = sqlite_metadata.tables[table_name]
            
            with self.sqlite_engine.connect() as sqlite_conn:
                # Count total records
                total_count = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()[0]
                
                if total_count == 0:
                    logger.info(f"  No data to migrate for {table_name}")
                    return 0
                
                # Migrate in batches
                for offset in range(0, total_count, batch_size):
                    # Fetch batch from SQLite
                    batch_result = sqlite_conn.execute(
                        text(f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}")
                    )
                    
                    batch_data = []
                    for row in batch_result:
                        # Convert row to dict
                        row_dict = dict(row._mapping)
                        batch_data.append(row_dict)
                    
                    if batch_data:
                        # Insert batch into PostgreSQL
                        with self.postgresql_engine.begin() as pg_conn:
                            # Use PostgreSQL UPSERT if table has primary key
                            if table.primary_key:
                                # Use UPSERT for tables with primary keys
                                stmt = postgresql_insert(table).values(batch_data)
                                
                                # Get primary key columns
                                pk_columns = [col.name for col in table.primary_key.columns]
                                
                                # Create update dict (all columns except primary key)
                                update_dict = {
                                    col.name: stmt.excluded[col.name] 
                                    for col in table.columns 
                                    if col.name not in pk_columns
                                }
                                
                                if update_dict:
                                    stmt = stmt.on_conflict_do_update(
                                        index_elements=pk_columns,
                                        set_=update_dict
                                    )
                                else:
                                    stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)
                            else:
                                # Simple insert for tables without primary keys
                                stmt = table.insert().values(batch_data)
                            
                            pg_conn.execute(stmt)
                            migrated_count += len(batch_data)
                    
                    if migrated_count % 10000 == 0 and migrated_count > 0:
                        logger.info(f"  Migrated {migrated_count:,} / {total_count:,} records...")
            
            logger.info(f"✓ Migrated {migrated_count:,} records from {table_name}")
            return migrated_count
            
        except Exception as e:
            error_msg = f"Error migrating {table_name}: {e}"
            logger.error(error_msg)
            self.migration_stats['errors'].append(error_msg)
            return 0
    
    def verify_migration(self) -> Dict[str, Any]:
        """Verify migration by comparing record counts."""
        logger.info("Verifying migration...")
        
        verification_results = {
            'success': True,
            'table_comparisons': {},
            'total_sqlite_records': 0,
            'total_postgresql_records': 0,
        }
        
        # Get table names from SQLite
        with self.sqlite_engine.connect() as conn:
            tables_result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """))
            tables = [row[0] for row in tables_result]
        
        for table in tables:
            try:
                # Count SQLite records
                with self.sqlite_engine.connect() as sqlite_conn:
                    sqlite_count = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                
                # Count PostgreSQL records
                with self.postgresql_engine.connect() as pg_conn:
                    postgresql_count = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                
                verification_results['table_comparisons'][table] = {
                    'sqlite': sqlite_count,
                    'postgresql': postgresql_count,
                    'match': sqlite_count == postgresql_count
                }
                
                verification_results['total_sqlite_records'] += sqlite_count
                verification_results['total_postgresql_records'] += postgresql_count
                
                if sqlite_count != postgresql_count:
                    verification_results['success'] = False
                    logger.warning(f"❌ {table}: SQLite={sqlite_count:,}, PostgreSQL={postgresql_count:,}")
                else:
                    logger.info(f"✓ {table}: {sqlite_count:,} records match")
                    
            except Exception as e:
                logger.error(f"Error verifying {table}: {e}")
                verification_results['success'] = False
        
        return verification_results
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        self.migration_stats['start_time'] = datetime.now()
        
        try:
            logger.info("=== Starting PostgreSQL Migration ===")
            
            # Verify PostgreSQL connection
            if not self.verify_postgresql_connection():
                return False
            
            # Analyze SQLite data
            table_counts = self.analyze_sqlite_data()
            
            # Create PostgreSQL schema
            if not self.create_postgresql_schema():
                return False
            
            # Migrate data table by table
            total_migrated = 0
            
            # Define migration order (dependencies first) - same as table creation order
            migration_order = [
                'alembic_version',
                'collection_metadata', 
                'discovery_metadata',
                'execution_history',
                'performance_metrics',
                'system_alerts',
                'dexes',           # No foreign keys
                'tokens',          # No foreign keys  
                'pools',           # Depends on dexes and tokens
                'watchlist',       # Depends on pools
                'new_pools_history', # Depends on pools
                'trades',          # Depends on pools
                'ohlcv_data'       # Depends on pools
            ]
            
            # Add any other tables not in the predefined order
            all_tables = set(table_counts.keys())
            ordered_tables = [t for t in migration_order if t in all_tables]
            remaining_tables = all_tables - set(ordered_tables)
            final_order = ordered_tables + list(remaining_tables)
            
            for table in final_order:
                if table_counts.get(table, 0) > 0:
                    migrated = self.migrate_table_data(table)
                    total_migrated += migrated
                    self.migration_stats['tables_migrated'] += 1
                else:
                    logger.info(f"Skipping {table} (no data)")
            
            self.migration_stats['total_records'] = total_migrated
            
            # Verify migration
            verification = self.verify_migration()
            
            if verification['success']:
                logger.info("✓ Migration completed successfully!")
                logger.info(f"  Total records migrated: {total_migrated:,}")
                logger.info(f"  Tables migrated: {self.migration_stats['tables_migrated']}")
                return True
            else:
                logger.error("❌ Migration verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.migration_stats['errors'].append(str(e))
            return False
        
        finally:
            self.migration_stats['end_time'] = datetime.now()
    
    def print_migration_summary(self):
        """Print migration summary."""
        logger.info("\n=== Migration Summary ===")
        
        if self.migration_stats['start_time'] and self.migration_stats['end_time']:
            duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
            logger.info(f"Duration: {duration}")
        
        logger.info(f"Tables migrated: {self.migration_stats['tables_migrated']}")
        logger.info(f"Total records: {self.migration_stats['total_records']:,}")
        
        if self.migration_stats['errors']:
            logger.info(f"Errors encountered: {len(self.migration_stats['errors'])}")
            for error in self.migration_stats['errors']:
                logger.error(f"  - {error}")


def main():
    """Main migration function."""
    if len(sys.argv) < 3:
        print("Usage: python simple_migrate_to_postgresql.py <sqlite_path> <postgresql_url>")
        print("Example: python simple_migrate_to_postgresql.py gecko_data.db postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector")
        sys.exit(1)
    
    sqlite_path = sys.argv[1]
    postgresql_url = sys.argv[2]
    
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    logger.info(f"Migrating from SQLite: {sqlite_path}")
    logger.info(f"Migrating to PostgreSQL: {postgresql_url}")
    
    # Confirm migration
    try:
        confirm = input("Are you sure you want to proceed with migration? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Migration cancelled")
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        logger.info("Migration cancelled")
        sys.exit(0)
    
    # Run migration
    migrator = SimpleDatabaseMigrator(sqlite_path, postgresql_url)
    
    success = migrator.run_migration()
    migrator.print_migration_summary()
    
    if success:
        logger.info("\n🎉 Migration completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Update your configuration to use PostgreSQL")
        logger.info("2. Test your collectors with the new database")
        logger.info("3. Monitor performance improvements")
        sys.exit(0)
    else:
        logger.error("\n❌ Migration failed!")
        logger.error("Please check the errors above and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()