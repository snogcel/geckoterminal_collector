"""
Migration script to upgrade from basic new_pools_history to enhanced version
with QLib integration and predictive modeling capabilities.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from gecko_terminal_collector.database.manager import DatabaseManager
from enhanced_new_pools_history_model import Base, EnhancedNewPoolsHistory, PoolFeatureVector, QLibDataExport

logger = logging.getLogger(__name__)


class HistoryTableMigration:
    """
    Migrate existing new_pools_history data to enhanced format.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.engine = db_manager.connection.engine
        self.Session = sessionmaker(bind=self.engine)
    
    async def run_migration(self, backup_existing: bool = True) -> Dict:
        """
        Run the complete migration process.
        
        Args:
            backup_existing: Whether to backup existing data before migration
            
        Returns:
            Migration result dictionary
        """
        migration_start = datetime.now()
        results = {
            'success': False,
            'start_time': migration_start,
            'steps_completed': [],
            'errors': [],
            'records_migrated': 0,
            'backup_created': False
        }
        
        try:
            logger.info("Starting new pools history table migration")
            
            # Step 1: Backup existing data
            if backup_existing:
                backup_result = await self._backup_existing_data()
                results['backup_created'] = backup_result['success']
                results['steps_completed'].append('backup')
                
                if not backup_result['success']:
                    results['errors'].append(f"Backup failed: {backup_result['error']}")
                    return results
            
            # Step 2: Create new enhanced tables
            create_result = await self._create_enhanced_tables()
            results['steps_completed'].append('create_tables')
            
            if not create_result['success']:
                results['errors'].append(f"Table creation failed: {create_result['error']}")
                return results
            
            # Step 3: Migrate existing data
            migrate_result = await self._migrate_existing_data()
            results['records_migrated'] = migrate_result['records_migrated']
            results['steps_completed'].append('migrate_data')
            
            if not migrate_result['success']:
                results['errors'].append(f"Data migration failed: {migrate_result['error']}")
                return results
            
            # Step 4: Create indexes and constraints
            index_result = await self._create_indexes()
            results['steps_completed'].append('create_indexes')
            
            if not index_result['success']:
                results['errors'].append(f"Index creation failed: {index_result['error']}")
                return results
            
            # Step 5: Validate migration
            validation_result = await self._validate_migration()
            results['steps_completed'].append('validate')
            
            if not validation_result['success']:
                results['errors'].append(f"Validation failed: {validation_result['error']}")
                return results
            
            results['success'] = True
            results['end_time'] = datetime.now()
            results['duration'] = results['end_time'] - migration_start
            
            logger.info(f"Migration completed successfully in {results['duration']}")
            return results
            
        except Exception as e:
            error_msg = f"Migration failed with error: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            results['end_time'] = datetime.now()
            return results
    
    async def _backup_existing_data(self) -> Dict:
        """Backup existing new_pools_history data."""
        try:
            backup_table_name = f"new_pools_history_backup_{int(datetime.now().timestamp())}"
            
            with self.Session() as session:
                # Check if original table exists
                check_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'new_pools_history'
                    )
                """)
                
                table_exists = session.execute(check_query).scalar()
                
                if not table_exists:
                    logger.info("Original new_pools_history table does not exist, skipping backup")
                    return {'success': True, 'backup_table': None}
                
                # Create backup table
                backup_query = text(f"""
                    CREATE TABLE {backup_table_name} AS 
                    SELECT * FROM new_pools_history
                """)
                
                session.execute(backup_query)
                session.commit()
                
                # Get record count
                count_query = text(f"SELECT COUNT(*) FROM {backup_table_name}")
                record_count = session.execute(count_query).scalar()
                
                logger.info(f"Backed up {record_count} records to {backup_table_name}")
                
                return {
                    'success': True,
                    'backup_table': backup_table_name,
                    'record_count': record_count
                }
                
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _create_enhanced_tables(self) -> Dict:
        """Create enhanced table structures."""
        try:
            logger.info("Creating enhanced table structures")
            
            # Create all tables defined in the enhanced model
            Base.metadata.create_all(self.engine)
            
            logger.info("Enhanced tables created successfully")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Table creation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _migrate_existing_data(self) -> Dict:
        """Migrate data from old format to enhanced format."""
        try:
            logger.info("Starting data migration")
            
            with self.Session() as session:
                # Check if old table exists
                check_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'new_pools_history'
                    )
                """)
                
                old_table_exists = session.execute(check_query).scalar()
                
                if not old_table_exists:
                    logger.info("No existing data to migrate")
                    return {'success': True, 'records_migrated': 0}
                
                # Get existing data
                select_query = text("""
                    SELECT 
                        pool_id,
                        type,
                        name,
                        base_token_price_usd,
                        base_token_price_native_currency,
                        quote_token_price_usd,
                        quote_token_price_native_currency,
                        address,
                        reserve_in_usd,
                        pool_created_at,
                        fdv_usd,
                        market_cap_usd,
                        price_change_percentage_h1,
                        price_change_percentage_h24,
                        transactions_h1_buys,
                        transactions_h1_sells,
                        transactions_h24_buys,
                        transactions_h24_sells,
                        volume_usd_h24,
                        dex_id,
                        base_token_id,
                        quote_token_id,
                        network_id,
                        collected_at,
                        signal_score,
                        volume_trend,
                        liquidity_trend,
                        momentum_indicator,
                        activity_score,
                        volatility_score
                    FROM new_pools_history
                    ORDER BY collected_at
                """)
                
                old_records = session.execute(select_query).fetchall()
                
                if not old_records:
                    logger.info("No records found in existing table")
                    return {'success': True, 'records_migrated': 0}
                
                logger.info(f"Found {len(old_records)} records to migrate")
                
                # Migrate records in batches
                batch_size = 1000
                migrated_count = 0
                
                for i in range(0, len(old_records), batch_size):
                    batch = old_records[i:i + batch_size]
                    batch_records = []
                    
                    for record in batch:
                        # Convert old record to enhanced format
                        enhanced_record = self._convert_to_enhanced_format(record)
                        if enhanced_record:
                            batch_records.append(enhanced_record)
                    
                    # Insert batch
                    if batch_records:
                        session.add_all(batch_records)
                        session.commit()
                        migrated_count += len(batch_records)
                        
                        logger.info(f"Migrated batch: {migrated_count}/{len(old_records)} records")
                
                logger.info(f"Migration completed: {migrated_count} records migrated")
                
                return {
                    'success': True,
                    'records_migrated': migrated_count,
                    'total_found': len(old_records)
                }
                
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            return {'success': False, 'error': str(e), 'records_migrated': 0}
    
    def _convert_to_enhanced_format(self, old_record) -> Optional[EnhancedNewPoolsHistory]:
        """Convert old record format to enhanced format."""
        try:
            # Extract timestamp from collected_at
            collected_at = old_record.collected_at
            timestamp = int(collected_at.timestamp()) if collected_at else int(datetime.now().timestamp())
            
            # Create enhanced record with available data
            enhanced_record = EnhancedNewPoolsHistory(
                pool_id=old_record.pool_id,
                timestamp=timestamp,
                datetime=collected_at or datetime.now(),
                collection_interval='1h',  # Default interval
                
                # Basic information
                type=old_record.type,
                name=old_record.name,
                address=old_record.address,
                network_id=old_record.network_id,
                dex_id=old_record.dex_id,
                base_token_id=old_record.base_token_id,
                quote_token_id=old_record.quote_token_id,
                
                # Price data (use current price for all OHLC initially)
                open_price_usd=old_record.base_token_price_usd,
                high_price_usd=old_record.base_token_price_usd,
                low_price_usd=old_record.base_token_price_usd,
                close_price_usd=old_record.base_token_price_usd,
                
                # Volume and liquidity
                volume_usd_h24=old_record.volume_usd_h24,
                reserve_in_usd=old_record.reserve_in_usd,
                
                # Market metrics
                market_cap_usd=old_record.market_cap_usd,
                fdv_usd=old_record.fdv_usd,
                
                # Price changes
                price_change_percentage_h1=old_record.price_change_percentage_h1,
                price_change_percentage_h24=old_record.price_change_percentage_h24,
                
                # Trading activity
                transactions_h1_buys=old_record.transactions_h1_buys,
                transactions_h1_sells=old_record.transactions_h1_sells,
                transactions_h24_buys=old_record.transactions_h24_buys,
                transactions_h24_sells=old_record.transactions_h24_sells,
                
                # Signal analysis (existing fields)
                signal_score=old_record.signal_score,
                volume_trend=old_record.volume_trend,
                liquidity_trend=old_record.liquidity_trend,
                momentum_indicator=old_record.momentum_indicator,
                activity_score=old_record.activity_score,
                volatility_score=old_record.volatility_score,
                
                # Pool lifecycle
                pool_created_at=old_record.pool_created_at,
                pool_age_hours=self._calculate_pool_age_hours(old_record.pool_created_at, collected_at),
                is_new_pool=True,  # Assume all migrated records are new pools
                
                # Data quality and metadata
                data_quality_score=75.0,  # Default quality score for migrated data
                collection_source='migration_from_basic',
                
                # QLib integration
                qlib_symbol=self._generate_qlib_symbol(old_record.pool_id, old_record.name, old_record.network_id),
                
                # Timestamps
                collected_at=collected_at,
                processed_at=None
            )
            
            return enhanced_record
            
        except Exception as e:
            logger.error(f"Error converting record {old_record.pool_id}: {e}")
            return None
    
    def _calculate_pool_age_hours(self, pool_created_at, collected_at) -> Optional[int]:
        """Calculate pool age in hours."""
        try:
            if not pool_created_at or not collected_at:
                return None
            
            age_delta = collected_at - pool_created_at
            return int(age_delta.total_seconds() / 3600)
            
        except Exception as e:
            logger.error(f"Error calculating pool age: {e}")
            return None
    
    def _generate_qlib_symbol(self, pool_id: str, name: str, network_id: str) -> str:
        """Generate QLib symbol for migrated data."""
        try:
            if name and '/' in name:
                symbol = name.replace('/', '_').upper()
            else:
                symbol = f"POOL_{pool_id[:8].upper()}"
            
            return f"{symbol}_{network_id.upper()}"
            
        except Exception as e:
            logger.error(f"Error generating QLib symbol: {e}")
            return f"UNKNOWN_{pool_id[:8]}"
    
    async def _create_indexes(self) -> Dict:
        """Create additional indexes for performance."""
        try:
            logger.info("Creating performance indexes")
            
            with self.Session() as session:
                # Additional custom indexes beyond what's defined in the model
                custom_indexes = [
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_enhanced_pools_history_qlib_export
                    ON new_pools_history_enhanced (qlib_symbol, timestamp, data_quality_score)
                    WHERE data_quality_score >= 70
                    """,
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_enhanced_pools_history_ml_features
                    ON new_pools_history_enhanced (pool_id, timestamp, signal_score, activity_score, volatility_score)
                    WHERE signal_score IS NOT NULL
                    """,
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_enhanced_pools_history_time_series
                    ON new_pools_history_enhanced (collection_interval, timestamp, pool_id)
                    """,
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feature_vectors_ml_ready
                    ON pool_feature_vectors (feature_set_version, timestamp, pool_id)
                    """
                ]
                
                for index_sql in custom_indexes:
                    try:
                        session.execute(text(index_sql))
                        session.commit()
                    except Exception as e:
                        logger.warning(f"Index creation warning: {e}")
                        session.rollback()
                        continue
                
                logger.info("Performance indexes created")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _validate_migration(self) -> Dict:
        """Validate the migration results."""
        try:
            logger.info("Validating migration")
            
            with self.Session() as session:
                # Count records in enhanced table
                enhanced_count_query = text("SELECT COUNT(*) FROM new_pools_history_enhanced")
                enhanced_count = session.execute(enhanced_count_query).scalar()
                
                # Check if old table exists and count records
                old_table_exists_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'new_pools_history'
                    )
                """)
                
                old_table_exists = session.execute(old_table_exists_query).scalar()
                old_count = 0
                
                if old_table_exists:
                    old_count_query = text("SELECT COUNT(*) FROM new_pools_history")
                    old_count = session.execute(old_count_query).scalar()
                
                # Validate data integrity
                validation_queries = [
                    ("Non-null pool_id count", "SELECT COUNT(*) FROM new_pools_history_enhanced WHERE pool_id IS NOT NULL"),
                    ("Valid timestamp count", "SELECT COUNT(*) FROM new_pools_history_enhanced WHERE timestamp > 0"),
                    ("QLib symbol count", "SELECT COUNT(*) FROM new_pools_history_enhanced WHERE qlib_symbol IS NOT NULL"),
                    ("Quality score range", "SELECT COUNT(*) FROM new_pools_history_enhanced WHERE data_quality_score BETWEEN 0 AND 100")
                ]
                
                validation_results = {}
                for desc, query in validation_queries:
                    count = session.execute(text(query)).scalar()
                    validation_results[desc] = count
                
                logger.info(f"Migration validation - Enhanced: {enhanced_count}, Original: {old_count}")
                logger.info(f"Validation results: {validation_results}")
                
                # Check if migration was successful
                success = (
                    enhanced_count > 0 and
                    validation_results["Non-null pool_id count"] == enhanced_count and
                    validation_results["Valid timestamp count"] == enhanced_count
                )
                
                return {
                    'success': success,
                    'enhanced_count': enhanced_count,
                    'original_count': old_count,
                    'validation_results': validation_results
                }
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {'success': False, 'error': str(e)}


# CLI function for running migration
async def run_migration_cli(
    db_manager: DatabaseManager,
    backup: bool = True,
    dry_run: bool = False
) -> Dict:
    """CLI function to run the migration."""
    try:
        if dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            # In dry run, just validate current state
            migration = HistoryTableMigration(db_manager)
            
            with migration.Session() as session:
                # Check current state
                old_table_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'new_pools_history'
                    )
                """)
                
                enhanced_table_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'new_pools_history_enhanced'
                    )
                """)
                
                old_exists = session.execute(old_table_query).scalar()
                enhanced_exists = session.execute(enhanced_table_query).scalar()
                
                old_count = 0
                enhanced_count = 0
                
                if old_exists:
                    old_count = session.execute(text("SELECT COUNT(*) FROM new_pools_history")).scalar()
                
                if enhanced_exists:
                    enhanced_count = session.execute(text("SELECT COUNT(*) FROM new_pools_history_enhanced")).scalar()
                
                print(f"📊 Current state:")
                print(f"   - Old table exists: {old_exists} ({old_count} records)")
                print(f"   - Enhanced table exists: {enhanced_exists} ({enhanced_count} records)")
                
                if old_exists and not enhanced_exists:
                    print("✅ Ready for migration")
                elif enhanced_exists:
                    print("⚠️  Enhanced table already exists")
                else:
                    print("ℹ️  No data to migrate")
                
                return {'success': True, 'dry_run': True}
        
        print("🚀 Starting new pools history migration...")
        
        migration = HistoryTableMigration(db_manager)
        result = await migration.run_migration(backup_existing=backup)
        
        if result['success']:
            print("✅ Migration completed successfully!")
            print(f"📊 Records migrated: {result['records_migrated']}")
            print(f"⏱️  Duration: {result.get('duration', 'N/A')}")
            print(f"🔧 Steps completed: {', '.join(result['steps_completed'])}")
            
            if result['backup_created']:
                print("💾 Backup created successfully")
        else:
            print("❌ Migration failed!")
            for error in result['errors']:
                print(f"   - {error}")
        
        return result
        
    except Exception as e:
        error_msg = f"Migration CLI error: {e}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}


if __name__ == "__main__":
    import sys
    import argparse
    
    # Simple CLI for running migration
    parser = argparse.ArgumentParser(description='Migrate new pools history to enhanced format')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    # This would need to be adapted to your specific database setup
    print("Migration script ready. Import and run with your DatabaseManager instance.")
    print("Example usage:")
    print("  result = await run_migration_cli(db_manager, backup=True, dry_run=False)")