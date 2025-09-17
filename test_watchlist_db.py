#!/usr/bin/env python3
"""
Comprehensive watchlist database test suite including:
- Database connection and schema validation
- CRUD operations testing
- Watchlist integration with new pools
- Performance testing
- Data integrity validation
- CLI command testing
- Auto-watchlist functionality
"""

import asyncio
import subprocess
import sys
import yaml
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TestResult:
    """Test result data structure."""
    name: str
    success: bool
    message: str
    execution_time: float
    details: Optional[Dict] = None


class WatchlistTestSuite:
    """Comprehensive watchlist testing suite."""
    
    def __init__(self):
        self.db_manager = None
        self.test_results: List[TestResult] = []
        self.test_pool_ids = []  # Track test data for cleanup
        
    async def initialize(self):
        """Initialize database connection."""
        try:
            # Load config
            with open('config.yaml', 'r') as f:
                config_dict = yaml.safe_load(f)
            
            from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
            from gecko_terminal_collector.config.models import DatabaseConfig
            
            # Convert dict to DatabaseConfig object
            db_config = DatabaseConfig(**config_dict['database'])
            self.db_manager = SQLAlchemyDatabaseManager(db_config)
            await self.db_manager.initialize()
            return True
        except Exception as e:
            print(f"❌ Failed to initialize database: {e}")
            return False
    
    async def cleanup(self):
        """Clean up test data and close connections."""
        if self.db_manager:
            # Clean up test entries
            for pool_id in self.test_pool_ids:
                try:
                    await self.db_manager.remove_watchlist_entry(pool_id)
                except:
                    pass  # Ignore cleanup errors
            
            await self.db_manager.close()
    
    def run_cli_command(self, command_args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
        """Run a CLI command and return the result."""
        try:
            cmd = ["python", "gecko_terminal_collector/cli.py"] + command_args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return -1, "", str(e)
    
    async def test_database_connection(self) -> TestResult:
        """Test database connection and basic functionality."""
        start_time = datetime.now()
        
        try:
            # Test basic connection
            if not self.db_manager:
                return TestResult(
                    name="Database Connection",
                    success=False,
                    message="Database manager not initialized",
                    execution_time=0.0
                )
            
            # Test basic query
            from sqlalchemy import text
            with self.db_manager.connection.get_session() as session:
                result = session.execute(text("SELECT 1"))
                test_value = result.scalar()
                
                if test_value != 1:
                    raise Exception("Basic query test failed")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return TestResult(
                name="Database Connection",
                success=True,
                message="Database connection successful",
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Database Connection",
                success=False,
                message=f"Database connection failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_schema_validation(self) -> TestResult:
        """Test watchlist table schema and constraints."""
        start_time = datetime.now()
        
        try:
            from sqlalchemy import text
            
            # Check if watchlist table exists with correct schema
            schema_query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'watchlist'
            ORDER BY ordinal_position
            """
            
            with self.db_manager.connection.get_session() as session:
                result = session.execute(text(schema_query))
                columns = result.fetchall()
            
            if not columns:
                raise Exception("watchlist table not found")
            
            # Expected columns
            expected_columns = {
                'id', 'pool_id', 'token_symbol', 'token_name', 
                'network_address', 'is_active', 'created_at'
            }
            
            actual_columns = {col[0] for col in columns}
            
            missing_columns = expected_columns - actual_columns
            if missing_columns:
                raise Exception(f"Missing columns: {missing_columns}")
            
            # Check constraints
            constraints_query = """
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'watchlist'
            """
            
            with self.db_manager.connection.get_session() as session:
                result = session.execute(text(constraints_query))
                constraints = result.fetchall()
            
            constraint_types = {constraint[1] for constraint in constraints}
            
            details = {
                'columns_found': len(columns),
                'expected_columns': len(expected_columns),
                'constraints': list(constraint_types),
                'schema_valid': len(missing_columns) == 0
            }
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return TestResult(
                name="Watchlist Schema Validation",
                success=len(missing_columns) == 0,
                message=f"Schema validation {'passed' if len(missing_columns) == 0 else 'failed'}",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist Schema Validation",
                success=False,
                message=f"Schema validation failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_crud_operations(self) -> TestResult:
        """Test Create, Read, Update, Delete operations for watchlist."""
        start_time = datetime.now()
        
        try:
            # Generate unique test data
            test_id = str(uuid.uuid4())[:8]
            test_pool_id = f"test_pool_{test_id}"
            test_symbol = f"TEST{test_id}"
            test_name = f"Test Token {test_id}"
            
            self.test_pool_ids.append(test_pool_id)
            
            # First create a pool entry (required for foreign key constraint)
            from gecko_terminal_collector.database.postgresql_models import Pool, DEX, Token
            
            # Create test DEX and tokens first
            test_dex_id = f"test_dex_{test_id}"
            test_base_token_id = f"test_base_{test_id}"
            test_quote_token_id = f"test_quote_{test_id}"
            
            with self.db_manager.connection.get_session() as session:
                # Create test DEX
                test_dex = DEX(
                    id=test_dex_id,
                    name=f"Test DEX {test_id}",
                    network_id="test_network"
                )
                session.merge(test_dex)
                
                # Create test tokens
                test_base_token = Token(
                    id=test_base_token_id,
                    address=f"test_base_address_{test_id}",
                    name=f"Test Base Token {test_id}",
                    symbol=f"BASE{test_id}",
                    network_id="test_network"
                )
                session.merge(test_base_token)
                
                test_quote_token = Token(
                    id=test_quote_token_id,
                    address=f"test_quote_address_{test_id}",
                    name=f"Test Quote Token {test_id}",
                    symbol=f"QUOTE{test_id}",
                    network_id="test_network"
                )
                session.merge(test_quote_token)
                
                # Create test pool
                test_pool = Pool(
                    id=test_pool_id,
                    address=f"test_pool_address_{test_id}",
                    name=f"Test Pool {test_id}",
                    dex_id=test_dex_id,
                    base_token_id=test_base_token_id,
                    quote_token_id=test_quote_token_id
                )
                session.merge(test_pool)
                session.commit()
            
            # Test CREATE watchlist entry
            watchlist_data = {
                'pool_id': test_pool_id,
                'token_symbol': test_symbol,
                'token_name': test_name,
                'network_address': f"test_address_{test_id}",
                'is_active': True
            }
            await self.db_manager.add_to_watchlist(watchlist_data)
            
            # Test READ - Get all entries
            all_entries = await self.db_manager.get_all_watchlist_entries()
            test_entry = None
            for entry in all_entries:
                if entry.pool_id == test_pool_id:
                    test_entry = entry
                    break
            
            if not test_entry:
                raise Exception("Failed to create watchlist entry")
            
            # Test READ - Get active entries
            active_entries = await self.db_manager.get_active_watchlist_entries()
            test_entry_active = any(entry.pool_id == test_pool_id for entry in active_entries)
            
            if not test_entry_active:
                raise Exception("Test entry not found in active entries")
            
            # Test UPDATE - Deactivate entry
            await self.db_manager.update_watchlist_entry_status(test_pool_id, False)
            
            # Verify update
            updated_entries = await self.db_manager.get_active_watchlist_entries()
            still_active = any(entry.pool_id == test_pool_id for entry in updated_entries)
            
            if still_active:
                raise Exception("Failed to deactivate watchlist entry")
            
            # Test DELETE
            await self.db_manager.remove_watchlist_entry(test_pool_id)
            
            # Verify deletion
            final_entries = await self.db_manager.get_all_watchlist_entries()
            still_exists = any(entry.pool_id == test_pool_id for entry in final_entries)
            
            if still_exists:
                raise Exception("Failed to delete watchlist entry")
            
            # Clean up test pool and related data
            from sqlalchemy import text
            with self.db_manager.connection.get_session() as session:
                session.execute(text(f"DELETE FROM pools WHERE id = '{test_pool_id}'"))
                session.execute(text(f"DELETE FROM dexes WHERE id = '{test_dex_id}'"))
                session.execute(text(f"DELETE FROM tokens WHERE id = '{test_base_token_id}'"))
                session.execute(text(f"DELETE FROM tokens WHERE id = '{test_quote_token_id}'"))
                session.commit()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'create_success': True,
                'read_success': True,
                'update_success': True,
                'delete_success': True,
                'test_pool_id': test_pool_id
            }
            
            return TestResult(
                name="Watchlist CRUD Operations",
                success=True,
                message="All CRUD operations successful",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist CRUD Operations",
                success=False,
                message=f"CRUD operations failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_data_integrity(self) -> TestResult:
        """Test data integrity and constraints."""
        start_time = datetime.now()
        
        try:
            issues = []
            
            # Test 1: Check for duplicate pool_ids
            from sqlalchemy import text
            with self.db_manager.connection.get_session() as session:
                duplicate_query = """
                SELECT pool_id, COUNT(*) as count
                FROM watchlist
                GROUP BY pool_id
                HAVING COUNT(*) > 1
                """
                result = session.execute(text(duplicate_query))
                duplicates = result.fetchall()
                
                if duplicates:
                    issues.append(f"Found {len(duplicates)} duplicate pool_ids")
            
            # Test 2: Check for null required fields
            with self.db_manager.connection.get_session() as session:
                null_check_query = """
                SELECT COUNT(*) as null_pool_ids
                FROM watchlist
                WHERE pool_id IS NULL OR pool_id = ''
                """
                result = session.execute(text(null_check_query))
                null_count = result.scalar()
                
                if null_count > 0:
                    issues.append(f"Found {null_count} entries with null/empty pool_ids")
            
            # Test 3: Check data consistency
            with self.db_manager.connection.get_session() as session:
                consistency_query = """
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN token_symbol IS NOT NULL AND token_symbol != '' THEN 1 END) as has_symbol,
                    COUNT(CASE WHEN is_active IS NOT NULL THEN 1 END) as has_active_flag,
                    COUNT(CASE WHEN created_at IS NOT NULL THEN 1 END) as has_created_at
                FROM watchlist
                """
                result = session.execute(text(consistency_query))
                stats = result.fetchone()
                
                total = stats[0]
                if total > 0:
                    symbol_pct = (stats[1] / total) * 100
                    active_pct = (stats[2] / total) * 100
                    created_pct = (stats[3] / total) * 100
                    
                    if symbol_pct < 90:
                        issues.append(f"Only {symbol_pct:.1f}% of entries have token symbols")
                    if active_pct < 100:
                        issues.append(f"Only {active_pct:.1f}% of entries have active flags")
                    if created_pct < 100:
                        issues.append(f"Only {created_pct:.1f}% of entries have creation dates")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'issues_found': len(issues),
                'issues': issues,
                'integrity_score': max(0, 100 - len(issues) * 20)
            }
            
            return TestResult(
                name="Watchlist Data Integrity",
                success=len(issues) == 0,
                message=f"Data integrity {'passed' if len(issues) == 0 else 'issues found'}",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist Data Integrity",
                success=False,
                message=f"Data integrity test failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_cli_commands(self) -> TestResult:
        """Test watchlist CLI commands."""
        start_time = datetime.now()
        
        try:
            cli_tests = []
            
            # Test 1: List watchlist
            returncode, stdout, stderr = self.run_cli_command(['list-watchlist', '--format', 'json'])
            cli_tests.append({
                'command': 'list-watchlist',
                'success': returncode == 0,
                'error': stderr if returncode != 0 else None
            })
            
            # Test 2: List active watchlist
            returncode, stdout, stderr = self.run_cli_command(['list-watchlist', '--active-only'])
            cli_tests.append({
                'command': 'list-watchlist --active-only',
                'success': returncode == 0,
                'error': stderr if returncode != 0 else None
            })
            
            # Test 3: Add watchlist entry (with cleanup)
            test_id = str(uuid.uuid4())[:8]
            test_pool_id = f"cli_test_{test_id}"
            self.test_pool_ids.append(test_pool_id)
            
            returncode, stdout, stderr = self.run_cli_command([
                'add-watchlist',
                '--pool-id', test_pool_id,
                '--symbol', f'CLITEST{test_id}',
                '--name', f'CLI Test Token {test_id}'
            ])
            cli_tests.append({
                'command': 'add-watchlist',
                'success': returncode == 0,
                'error': stderr if returncode != 0 else None
            })
            
            # Test 4: Update watchlist entry
            if returncode == 0:  # Only if add succeeded
                returncode, stdout, stderr = self.run_cli_command([
                    'update-watchlist',
                    '--pool-id', test_pool_id,
                    '--active', 'false'
                ])
                cli_tests.append({
                    'command': 'update-watchlist',
                    'success': returncode == 0,
                    'error': stderr if returncode != 0 else None
                })
                
                # Test 5: Remove watchlist entry
                returncode, stdout, stderr = self.run_cli_command([
                    'remove-watchlist',
                    '--pool-id', test_pool_id,
                    '--force'
                ])
                cli_tests.append({
                    'command': 'remove-watchlist',
                    'success': returncode == 0,
                    'error': stderr if returncode != 0 else None
                })
            
            successful_tests = sum(1 for test in cli_tests if test['success'])
            total_tests = len(cli_tests)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'total_cli_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': total_tests - successful_tests,
                'test_results': cli_tests
            }
            
            return TestResult(
                name="Watchlist CLI Commands",
                success=successful_tests == total_tests,
                message=f"CLI tests: {successful_tests}/{total_tests} passed",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist CLI Commands",
                success=False,
                message=f"CLI command tests failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_auto_watchlist_integration(self) -> TestResult:
        """Test auto-watchlist functionality with new pools."""
        start_time = datetime.now()
        
        try:
            # Get initial watchlist count
            initial_entries = await self.db_manager.get_all_watchlist_entries()
            initial_count = len(initial_entries)
            
            # Test collect-new-pools with auto-watchlist (dry run first)
            returncode, stdout, stderr = self.run_cli_command([
                'collect-new-pools',
                '--network', 'solana',
                '--auto-watchlist',
                '--min-liquidity', '1000',
                '--min-volume', '100',
                '--min-activity-score', '60',
                '--dry-run'
            ], timeout=60)
            
            dry_run_success = returncode == 0
            
            # Check if we can run a real collection (optional, might hit rate limits)
            real_collection_attempted = False
            if dry_run_success:
                # Only attempt real collection if dry run succeeded
                returncode, stdout, stderr = self.run_cli_command([
                    'collect-new-pools',
                    '--network', 'solana',
                    '--auto-watchlist',
                    '--min-liquidity', '5000',  # Higher threshold to avoid too many additions
                    '--min-volume', '1000',
                    '--min-activity-score', '70'
                ], timeout=120)
                
                real_collection_attempted = True
                real_collection_success = returncode == 0
            else:
                real_collection_success = False
            
            # Check if any new entries were added
            final_entries = await self.db_manager.get_all_watchlist_entries()
            final_count = len(final_entries)
            entries_added = final_count - initial_count
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'dry_run_success': dry_run_success,
                'real_collection_attempted': real_collection_attempted,
                'real_collection_success': real_collection_success if real_collection_attempted else None,
                'initial_watchlist_count': initial_count,
                'final_watchlist_count': final_count,
                'entries_added': entries_added
            }
            
            # Consider test successful if dry run worked
            success = dry_run_success
            message = f"Auto-watchlist test: dry-run {'passed' if dry_run_success else 'failed'}"
            if real_collection_attempted:
                message += f", real collection {'passed' if real_collection_success else 'failed'}"
            message += f", {entries_added} entries added"
            
            return TestResult(
                name="Auto-Watchlist Integration",
                success=success,
                message=message,
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Auto-Watchlist Integration",
                success=False,
                message=f"Auto-watchlist test failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_performance(self) -> TestResult:
        """Test watchlist query performance."""
        start_time = datetime.now()
        
        try:
            performance_metrics = {}
            
            # Test 1: Get all watchlist entries performance
            query_start = datetime.now()
            all_entries = await self.db_manager.get_all_watchlist_entries()
            all_entries_time = (datetime.now() - query_start).total_seconds()
            performance_metrics['get_all_entries'] = all_entries_time
            
            # Test 2: Get active entries performance
            query_start = datetime.now()
            active_entries = await self.db_manager.get_active_watchlist_entries()
            active_entries_time = (datetime.now() - query_start).total_seconds()
            performance_metrics['get_active_entries'] = active_entries_time
            
            # Test 3: Check if pool is in watchlist performance
            if all_entries:
                test_pool_id = all_entries[0].pool_id
                query_start = datetime.now()
                is_in_watchlist = await self.db_manager.is_pool_in_watchlist(test_pool_id)
                check_membership_time = (datetime.now() - query_start).total_seconds()
                performance_metrics['check_membership'] = check_membership_time
            
            # Test 4: Complex query performance
            from sqlalchemy import text
            query_start = datetime.now()
            with self.db_manager.connection.get_session() as session:
                complex_query = """
                SELECT w.*, COUNT(h.id) as history_count
                FROM watchlist w
                LEFT JOIN new_pools_history h ON w.pool_id = h.pool_id
                WHERE w.is_active = true
                GROUP BY w.id, w.pool_id, w.token_symbol, w.token_name, w.network_address, w.is_active, w.created_at
                ORDER BY w.created_at DESC
                """
                result = session.execute(text(complex_query))
                complex_result = result.fetchall()
            complex_query_time = (datetime.now() - query_start).total_seconds()
            performance_metrics['complex_query'] = complex_query_time
            
            # Evaluate performance
            slow_queries = []
            if all_entries_time > 1.0:
                slow_queries.append(f"get_all_entries: {all_entries_time:.2f}s")
            if active_entries_time > 1.0:
                slow_queries.append(f"get_active_entries: {active_entries_time:.2f}s")
            if 'check_membership' in performance_metrics and performance_metrics['check_membership'] > 0.5:
                slow_queries.append(f"check_membership: {performance_metrics['check_membership']:.2f}s")
            if complex_query_time > 2.0:
                slow_queries.append(f"complex_query: {complex_query_time:.2f}s")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'performance_metrics': performance_metrics,
                'slow_queries': slow_queries,
                'total_entries_tested': len(all_entries),
                'active_entries_tested': len(active_entries)
            }
            
            return TestResult(
                name="Watchlist Performance",
                success=len(slow_queries) == 0,
                message=f"Performance test: {len(slow_queries)} slow queries detected",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist Performance",
                success=False,
                message=f"Performance test failed: {str(e)}",
                execution_time=execution_time
            )
    
    async def test_watchlist_new_pools_integration(self) -> TestResult:
        """Test integration between watchlist and new pools history."""
        start_time = datetime.now()
        
        try:
            # Check for watchlist entries that have corresponding new pools history
            from sqlalchemy import text
            with self.db_manager.connection.get_session() as session:
                integration_query = """
                SELECT 
                    w.pool_id,
                    w.token_symbol,
                    w.is_active,
                    COUNT(h.id) as history_records,
                    MAX(h.collected_at) as latest_collection,
                    AVG(h.signal_score) as avg_signal_score
                FROM watchlist w
                LEFT JOIN new_pools_history h ON w.pool_id = h.pool_id
                GROUP BY w.pool_id, w.token_symbol, w.is_active
                ORDER BY history_records DESC
                """
                result = session.execute(text(integration_query))
                integration_data = result.fetchall()
            
            # Analyze integration quality
            total_watchlist_entries = len(integration_data)
            entries_with_history = sum(1 for row in integration_data if row[3] > 0)
            # Fix timezone comparison issue
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            entries_with_recent_history = sum(1 for row in integration_data 
                                            if row[4] and row[4] > now_utc - timedelta(days=7))
            
            # Check for orphaned history records (pools in history but not in watchlist)
            with self.db_manager.connection.get_session() as session:
                orphaned_query = """
                SELECT COUNT(DISTINCT h.pool_id)
                FROM new_pools_history h
                LEFT JOIN watchlist w ON h.pool_id = w.pool_id
                WHERE w.pool_id IS NULL
                AND h.collected_at > NOW() - INTERVAL '7 days'
                """
                result = session.execute(text(orphaned_query))
                orphaned_count = result.scalar()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            details = {
                'total_watchlist_entries': total_watchlist_entries,
                'entries_with_history': entries_with_history,
                'entries_with_recent_history': entries_with_recent_history,
                'orphaned_history_records': orphaned_count,
                'integration_score': (entries_with_history / total_watchlist_entries * 100) if total_watchlist_entries > 0 else 0
            }
            
            # Consider integration good if most watchlist entries have some history
            integration_quality = (entries_with_history / total_watchlist_entries) if total_watchlist_entries > 0 else 0
            success = integration_quality >= 0.5 or total_watchlist_entries == 0  # 50% threshold or no entries
            
            return TestResult(
                name="Watchlist-NewPools Integration",
                success=success,
                message=f"Integration: {entries_with_history}/{total_watchlist_entries} entries have history",
                execution_time=execution_time,
                details=details
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TestResult(
                name="Watchlist-NewPools Integration",
                success=False,
                message=f"Integration test failed: {str(e)}",
                execution_time=execution_time
            )
    
    def print_test_result(self, result: TestResult):
        """Print formatted test result."""
        status = "✅" if result.success else "❌"
        print(f"{status} {result.name:<35} ({result.execution_time:.2f}s)")
        print(f"   {result.message}")
        
        if result.details:
            for key, value in result.details.items():
                if isinstance(value, list) and value:
                    print(f"   📋 {key}: {len(value)} items")
                    for item in value[:3]:  # Show first 3 items
                        print(f"      • {item}")
                    if len(value) > 3:
                        print(f"      ... and {len(value) - 3} more")
                elif isinstance(value, dict):
                    print(f"   📊 {key}:")
                    for k, v in value.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"   📊 {key}: {value}")
        print()
    
    def generate_summary_report(self):
        """Generate comprehensive test summary."""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE WATCHLIST TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests
        
        print(f"\n📈 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result.success:
                    print(f"   • {result.name}: {result.message}")
        
        # Performance summary
        total_time = sum(result.execution_time for result in self.test_results)
        avg_time = total_time / total_tests if total_tests > 0 else 0
        print(f"\n⚡ Performance Summary:")
        print(f"   Total Execution Time: {total_time:.2f}s")
        print(f"   Average Test Time: {avg_time:.2f}s")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        if passed_tests == total_tests:
            print("   🎉 All tests passed! Watchlist system is working excellently.")
        elif passed_tests / total_tests >= 0.8:
            print("   ✅ Most tests passed. Address any failed tests for optimal performance.")
            print("   🔧 Review failed tests and consider system optimizations.")
        else:
            print("   ⚠️  Multiple test failures detected. System needs attention.")
            print("   🚨 Review database configuration and watchlist implementation.")
        
        print(f"\n🔧 Next Steps:")
        print("   1. Review any failed tests and their error messages")
        print("   2. Monitor watchlist performance for large datasets")
        print("   3. Verify auto-watchlist integration is working as expected")
        print("   4. Set up regular monitoring of watchlist operations")
        print("   5. Consider adding more comprehensive integration tests")
    
    async def run_comprehensive_tests(self):
        """Run all comprehensive watchlist tests."""
        print("🧪 COMPREHENSIVE WATCHLIST DATABASE TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now()}")
        print()
        
        # Initialize
        if not await self.initialize():
            print("❌ Failed to initialize test suite")
            return
        
        try:
            # Run all tests
            tests = [
                self.test_database_connection(),
                self.test_watchlist_schema_validation(),
                self.test_watchlist_crud_operations(),
                self.test_watchlist_data_integrity(),
                self.test_watchlist_cli_commands(),
                self.test_auto_watchlist_integration(),
                self.test_watchlist_performance(),
                self.test_watchlist_new_pools_integration()
            ]
            
            for test_coro in tests:
                result = await test_coro
                self.test_results.append(result)
                self.print_test_result(result)
            
            # Generate summary
            self.generate_summary_report()
            
        finally:
            await self.cleanup()
        
        print(f"\n🏁 Testing completed at: {datetime.now()}")


async def main():
    """Main test runner."""
    test_suite = WatchlistTestSuite()
    await test_suite.run_comprehensive_tests()


if __name__ == "__main__":
    asyncio.run(main())