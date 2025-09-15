"""
Migration utilities for standardizing pool ID formats.

This module provides utilities to migrate existing data to use consistent
pool ID formats with network prefixes.
"""

import logging
from typing import List, Dict, Any
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.pool_id_utils import PoolIDUtils

logger = logging.getLogger(__name__)


class PoolIDMigration:
    """Utilities for migrating pool IDs to consistent format."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def analyze_pool_id_formats(self) -> Dict[str, Any]:
        """
        Analyze existing pool IDs to understand current format distribution.
        
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            'total_pools': 0,
            'with_network_prefix': 0,
            'without_network_prefix': 0,
            'network_distribution': {},
            'invalid_formats': [],
            'sample_ids': []
        }
        
        try:
            with self.db_manager.connection.get_session() as session:
                from gecko_terminal_collector.database.models import Pool
                
                pools = session.query(Pool).all()
                analysis['total_pools'] = len(pools)
                
                for pool in pools:
                    pool_id = pool.id
                    analysis['sample_ids'].append(pool_id)
                    
                    if not PoolIDUtils.is_valid_pool_id_format(pool_id):
                        analysis['invalid_formats'].append(pool_id)
                        continue
                    
                    network = PoolIDUtils.get_network_from_pool_id(pool_id)
                    if network:
                        analysis['with_network_prefix'] += 1
                        analysis['network_distribution'][network] = \
                            analysis['network_distribution'].get(network, 0) + 1
                    else:
                        analysis['without_network_prefix'] += 1
                
                # Limit sample size for readability
                analysis['sample_ids'] = analysis['sample_ids'][:10]
                
        except Exception as e:
            logger.error(f"Error analyzing pool ID formats: {e}")
            
        return analysis
    
    async def migrate_pool_ids_to_standard_format(
        self, 
        default_network: str = "solana",
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Migrate pool IDs to standard format with network prefixes.
        
        Args:
            default_network: Network to use for IDs without network prefix
            dry_run: If True, only analyze what would be changed
            
        Returns:
            Dictionary with migration results
        """
        results = {
            'total_processed': 0,
            'migrations_needed': 0,
            'migrations_applied': 0,
            'errors': [],
            'changes': []
        }
        
        try:
            with self.db_manager.connection.get_session() as session:
                from gecko_terminal_collector.database.models import Pool
                
                pools = session.query(Pool).all()
                results['total_processed'] = len(pools)
                
                for pool in pools:
                    old_id = pool.id
                    new_id = PoolIDUtils.normalize_pool_id(old_id, default_network)
                    
                    if old_id != new_id:
                        results['migrations_needed'] += 1
                        change_info = {
                            'old_id': old_id,
                            'new_id': new_id,
                            'pool_name': pool.name
                        }
                        results['changes'].append(change_info)
                        
                        if not dry_run:
                            try:
                                # Check if new ID already exists
                                existing = session.query(Pool).filter_by(id=new_id).first()
                                if existing and existing.id != old_id:
                                    error_msg = f"Cannot migrate {old_id} to {new_id}: ID already exists"
                                    results['errors'].append(error_msg)
                                    continue
                                
                                # Update the pool ID
                                pool.id = new_id
                                session.commit()
                                results['migrations_applied'] += 1
                                
                            except Exception as e:
                                session.rollback()
                                error_msg = f"Error migrating {old_id} to {new_id}: {e}"
                                results['errors'].append(error_msg)
                                logger.error(error_msg)
                
        except Exception as e:
            error_msg = f"Error during pool ID migration: {e}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    async def validate_pool_id_consistency(self) -> Dict[str, Any]:
        """
        Validate that pool IDs are consistent across all tables.
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            'pools_table': {'total': 0, 'valid': 0, 'invalid': []},
            'watchlist_table': {'total': 0, 'valid_refs': 0, 'invalid_refs': []},
            'ohlcv_table': {'total': 0, 'valid_refs': 0, 'invalid_refs': []},
            'trades_table': {'total': 0, 'valid_refs': 0, 'invalid_refs': []},
            'orphaned_references': []
        }
        
        try:
            with self.db_manager.connection.get_session() as session:
                from gecko_terminal_collector.database.models import (
                    Pool, WatchlistEntry, OHLCVData, Trade
                )
                
                # Validate pools table
                pools = session.query(Pool).all()
                validation['pools_table']['total'] = len(pools)
                valid_pool_ids = set()
                
                for pool in pools:
                    if PoolIDUtils.is_valid_pool_id_format(pool.id):
                        validation['pools_table']['valid'] += 1
                        valid_pool_ids.add(pool.id)
                    else:
                        validation['pools_table']['invalid'].append(pool.id)
                
                # Validate watchlist references
                watchlist_entries = session.query(WatchlistEntry).all()
                validation['watchlist_table']['total'] = len(watchlist_entries)
                
                for entry in watchlist_entries:
                    if entry.pool_id in valid_pool_ids:
                        validation['watchlist_table']['valid_refs'] += 1
                    else:
                        validation['watchlist_table']['invalid_refs'].append(entry.pool_id)
                        validation['orphaned_references'].append({
                            'table': 'watchlist',
                            'pool_id': entry.pool_id,
                            'record_id': entry.id
                        })
                
                # Similar validation for other tables...
                # (Add OHLCV and Trades validation as needed)
                
        except Exception as e:
            logger.error(f"Error validating pool ID consistency: {e}")
            
        return validation


async def create_migration_report(db_manager: DatabaseManager) -> str:
    """
    Create a comprehensive migration report for pool ID standardization.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Formatted report string
    """
    migration = PoolIDMigration(db_manager)
    
    analysis = await migration.analyze_pool_id_formats()
    dry_run_results = await migration.migrate_pool_ids_to_standard_format(dry_run=True)
    validation = await migration.validate_pool_id_consistency()
    
    report = f"""
Pool ID Migration Analysis Report
================================

Current State:
- Total pools: {analysis['total_pools']}
- With network prefix: {analysis['with_network_prefix']}
- Without network prefix: {analysis['without_network_prefix']}
- Invalid formats: {len(analysis['invalid_formats'])}

Network Distribution:
{chr(10).join(f"- {net}: {count}" for net, count in analysis['network_distribution'].items())}

Migration Requirements:
- Pools needing migration: {dry_run_results['migrations_needed']}
- Potential errors: {len(dry_run_results['errors'])}

Sample Changes Needed:
{chr(10).join(f"- {change['old_id']} -> {change['new_id']}" for change in dry_run_results['changes'][:5])}

Validation Issues:
- Invalid pool IDs: {len(validation['pools_table']['invalid'])}
- Orphaned references: {len(validation['orphaned_references'])}

Recommendations:
1. {'✅ No migration needed' if dry_run_results['migrations_needed'] == 0 else '⚠️  Migration recommended'}
2. {'✅ No validation issues' if len(validation['orphaned_references']) == 0 else '⚠️  Fix orphaned references'}
3. {'✅ All formats valid' if len(analysis['invalid_formats']) == 0 else '⚠️  Fix invalid formats'}
"""
    
    return report